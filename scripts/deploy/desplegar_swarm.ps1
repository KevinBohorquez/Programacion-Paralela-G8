# T25 | Responsable: Miguel | Despliegue y comprobación de Swarm.
<#
.SYNOPSIS
  Despliega docker/swarm-stack.yaml en tres equipos (Docker Swarm) y recoge los CSV de E1/E2.

.DESCRIPTION
  Pasos (cada uno es una -Accion; todos los que cambian algo respetan -WhatIf y -Confirm):
    iniciar     docker swarm init en el equipo 1 (manager) e imprime el comando de unión
    unir        imprime el comando 'docker swarm join' que deben ejecutar los equipos 2 y 3
    etiquetar   docker node update --label-add pp_nodo=1|2|3 sobre -Nodos (en orden)
    imagen      construye pp-g8 y la distribuye: -Registro (push) o -SshDestinos (save/scp/load)
    desplegar   docker stack deploy -c docker/swarm-stack.yaml <Pila>
    ejecutar    espera a que termine el lanzador (pp_nodo1) mostrando su estado
    recolectar  guarda los logs del lanzador junto a los CSV de -Resultados
    retirar     docker stack rm <Pila> (y docker swarm leave --force con -SalirDelSwarm)
    simular     el mismo stack en UN anfitrión con docker compose (red bridge, sin Swarm)
    todo        etiquetar + desplegar + ejecutar + recolectar

  Requisitos del clúster real: los tres equipos con el repositorio clonado en el MISMO camino
  absoluto (-Repo) y en el mismo commit, la imagen pp-g8 en cada uno y los puertos de Swarm
  abiertos entre ellos (2377/tcp, 7946/tcp+udp, 4789/udp). Ver docker/README.md.

.EXAMPLE
  .\scripts\deploy\desplegar_swarm.ps1 -Accion simular -N 200000 -Procesos 3,6 -Reps 1
.EXAMPLE
  .\scripts\deploy\desplegar_swarm.ps1 -Accion iniciar -IpManager 192.168.1.10
.EXAMPLE
  .\scripts\deploy\desplegar_swarm.ps1 -Accion todo -Nodos pc-miguel,pc-lita,pc-david -Repo /srv/pp-g8 -WhatIf
#>
[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'Medium')]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('iniciar', 'unir', 'etiquetar', 'imagen', 'desplegar', 'ejecutar', 'recolectar', 'retirar', 'simular', 'todo')]
    [string]$Accion,
    [string]$IpManager = '',
    [string[]]$Nodos = @(),            # hostnames de Swarm (docker node ls) en orden: equipo 1, 2, 3
    [string[]]$SshDestinos = @(),      # usuario@equipo2, usuario@equipo3 para distribuir la imagen sin registro
    [string]$Registro = '',            # p. ej. 192.168.1.10:5000 (opcional)
    [string]$Imagen = 'pp-g8',
    [string]$Pila = 'pp',
    [string]$Repo = '',                # camino absoluto del repositorio, igual en los tres equipos
    [string]$Resultados = '',          # carpeta de resultados en el equipo 1 (def. <Repo>/results/swarm)
    [string]$HostsMpi = 'nodo1:4,nodo2:4,nodo3:4',
    [string]$Procesos = '4,8,12',
    [long]$N = 20000000,
    [int]$Reps = 5,
    [int]$Lote = 0,
    [int]$Nucleos = 0,                 # núcleos físicos totales del clúster (0 = estimación del lanzador)
    [string]$Subred = '10.77.0.0/24',
    [int]$EsperaMin = 240,
    [switch]$SalirDelSwarm
)

$ErrorActionPreference = 'Stop'
$RaizLocal = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$Stack = Join-Path $RaizLocal 'docker\swarm-stack.yaml'

function Invocar([string]$Descripcion, [scriptblock]$Bloque) {
    if ($PSCmdlet.ShouldProcess($Descripcion)) {
        $global:LASTEXITCODE = 0
        & $Bloque
        if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) { throw "falló: $Descripcion (código $LASTEXITCODE)" }
    }
}

function Fijar-Entorno {
    $commit = (git -C $RaizLocal rev-parse --short=12 HEAD 2>$null)
    $env:GIT_COMMIT = if ($commit) { $commit } else { 'desconocido' }
    $env:PP_IMAGEN = if ($Registro) { "$Registro/$Imagen" } else { $Imagen }
    $env:PP_HOSTS = $HostsMpi
    $env:PP_PROCESOS = $Procesos
    $env:PP_N = "$N"
    $env:PP_REPS = "$Reps"
    $env:PP_LOTE = "$Lote"
    $env:PP_NUCLEOS = if ($Nucleos -gt 0) { "$Nucleos" } else { '' }
    $env:PP_SUBRED = $Subred
}

function Requerir([string]$Nombre, $Valor) {
    if (-not $Valor) { throw "la acción '$Accion' necesita -$Nombre" }
}

function Paso-Iniciar {
    Requerir 'IpManager' $IpManager
    Invocar "docker swarm init --advertise-addr $IpManager (cambia este Docker a modo Swarm)" {
        docker swarm init --advertise-addr $IpManager
    }
    Paso-Unir
}

function Paso-Unir {
    Write-Host 'Ejecute en los equipos 2 y 3 el comando que imprime:' -ForegroundColor Cyan
    if ($WhatIfPreference) { Write-Host 'WhatIf: docker swarm join-token worker'; return }
    docker swarm join-token worker
}

function Paso-Etiquetar {
    if ($Nodos.Count -ne 3) { throw 'use -Nodos equipo1,equipo2,equipo3 (nombres de docker node ls)' }
    for ($i = 0; $i -lt 3; $i++) {
        $nodo = $Nodos[$i]; $num = $i + 1
        Invocar "docker node update --label-add pp_nodo=$num $nodo" { docker node update --label-add "pp_nodo=$num" $nodo }
    }
}

function Paso-Imagen {
    Invocar "docker build -t $Imagen (docker/Dockerfile)" {
        docker build -t $Imagen -f (Join-Path $RaizLocal 'docker\Dockerfile') $RaizLocal
    }
    if ($Registro) {
        Invocar "docker push $Registro/$Imagen" {
            docker tag $Imagen "$Registro/$Imagen"
            docker push "$Registro/$Imagen"
        }
    } elseif ($SshDestinos.Count -gt 0) {
        # Ojo: la imagen lleva la clave SSH interna; solo entre los equipos del grupo, nunca en un registro público.
        $tar = Join-Path ([IO.Path]::GetTempPath()) "$Imagen.tar"
        Invocar "docker save $Imagen -o $tar" { docker save $Imagen -o $tar }
        foreach ($d in $SshDestinos) {
            Invocar "scp $tar ${d}: y docker load en $d" {
                scp $tar "${d}:$Imagen.tar"
                ssh $d "docker load -i $Imagen.tar && rm $Imagen.tar"
            }
        }
    } else {
        Write-Warning 'sin -Registro ni -SshDestinos: construya la imagen en cada equipo (docker build -t pp-g8 -f docker/Dockerfile .)'
    }
}

function Paso-Desplegar {
    Requerir 'Repo' $Repo
    Fijar-Entorno
    $env:PP_REPO = $Repo
    $env:PP_RESULTADOS_HOST = if ($Resultados) { $Resultados } else { "$Repo/results/swarm" }
    Write-Host "PP_REPO=$env:PP_REPO resultados=$env:PP_RESULTADOS_HOST imagen=$env:PP_IMAGEN commit=$env:GIT_COMMIT"
    Invocar "crear $env:PP_RESULTADOS_HOST en el equipo 1" {
        New-Item -ItemType Directory -Force -Path $env:PP_RESULTADOS_HOST | Out-Null
    }
    Invocar "docker stack deploy -c docker/swarm-stack.yaml $Pila" {
        docker stack deploy -c $Stack $Pila
    }
}

function Paso-Ejecutar {
    if ($WhatIfPreference) { Write-Host "WhatIf: esperar a que $($Pila)_nodo1 termine (máx. $EsperaMin min)"; return }
    $limite = (Get-Date).AddMinutes($EsperaMin)
    do {
        Start-Sleep -Seconds 15
        $estado = (docker service ps "$($Pila)_nodo1" --no-trunc --format '{{.CurrentState}} {{.Error}}' | Select-Object -First 1)
        Write-Host "$(Get-Date -Format HH:mm:ss) nodo1: $estado"
        if ($estado -match '^(Complete|Failed|Rejected|Shutdown)') { break }
    } while ((Get-Date) -lt $limite)
    docker service ps "$($Pila)_nodo1" "$($Pila)_nodo2" "$($Pila)_nodo3"
    if ($estado -notmatch '^Complete') { throw "el lanzador no terminó bien: $estado (vea docker service logs $($Pila)_nodo1)" }
}

function Paso-Recolectar {
    $dest = if ($Resultados) { $Resultados } elseif ($Repo) { "$Repo/results/swarm" } else { Join-Path $RaizLocal 'results\swarm' }
    Invocar "guardar logs de los servicios en $dest" {
        New-Item -ItemType Directory -Force -Path $dest | Out-Null
        foreach ($s in 'nodo1', 'nodo2', 'nodo3') {
            docker service logs --no-task-ids "$($Pila)_$s" *> (Join-Path $dest "servicio_$s.log")
        }
    }
    if (Test-Path $dest) { Get-ChildItem $dest | Format-Table Name, Length, LastWriteTime }
}

function Paso-Retirar {
    Invocar "docker stack rm $Pila" { docker stack rm $Pila }
    if ($SalirDelSwarm) { Invocar 'docker swarm leave --force (este equipo sale del Swarm)' { docker swarm leave --force } }
}

function Paso-Simular {
    Fijar-Entorno
    $env:PP_RED_DRIVER = 'bridge'
    $env:PP_REPO = '..'
    $env:PP_RESULTADOS_HOST = '../results/swarm-sim'
    if ($HostsMpi -eq 'nodo1:4,nodo2:4,nodo3:4') { $env:PP_HOSTS = 'nodo1:2,nodo2:2,nodo3:2' }
    Invocar "docker compose -f docker/swarm-stack.yaml -p $Pila-swarm-sim up (3 contenedores en este equipo)" {
        docker compose -f $Stack -p "$Pila-swarm-sim" up --abort-on-container-exit --exit-code-from nodo1
        $codigo = $LASTEXITCODE
        docker compose -f $Stack -p "$Pila-swarm-sim" down -v
        $global:LASTEXITCODE = $codigo
    }
    Write-Host "Resultados en $(Join-Path $RaizLocal 'results\swarm-sim')"
}

switch ($Accion) {
    'iniciar'    { Paso-Iniciar }
    'unir'       { Paso-Unir }
    'etiquetar'  { Paso-Etiquetar }
    'imagen'     { Paso-Imagen }
    'desplegar'  { Paso-Desplegar }
    'ejecutar'   { Paso-Ejecutar }
    'recolectar' { Paso-Recolectar }
    'retirar'    { Paso-Retirar }
    'simular'    { Paso-Simular }
    'todo'       { Paso-Etiquetar; Paso-Desplegar; Paso-Ejecutar; Paso-Recolectar }
}
