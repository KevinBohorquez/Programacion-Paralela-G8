# T51 | Responsable: Miguel | Demostración en clúster con salida precalculada de respaldo.
<#
.SYNOPSIS
  Demostración de la exposición: demo web y corrida MPI E1/E2 en el clúster de contenedores, con un
  respaldo precalculado en results/demo/ por si la corrida en vivo falla.

.DESCRIPTION
  Pasos (cada uno es una -Accion; todos los que cambian algo respetan -WhatIf y -Confirm):
    web       levanta la demo web (scripts/demo/servidor_demo.py) en un contenedor pp-g8
    cluster   corre E1 (pp_mpi_estatico) y E2 (pp_mpi_dinamico) en el -Destino elegido:
                compose    docker/compose.yaml en este equipo (tres contenedores)
                swarm-sim  docker/swarm-stack.yaml en este equipo (desplegar_swarm.ps1 -Accion simular)
                swarm      el Swarm real de tres equipos (desplegar_swarm.ps1 -Accion todo)
    respaldo  copia los CSV, resúmenes y logs del -Destino a <Respaldo>/<Destino>/ con un manifiesto
    mostrar   imprime el respaldo (manifiesto y resumen E1 frente a E2); no ejecuta nada
    detener   detiene la demo web
    ensayo    cluster + respaldo: el ensayo del día anterior, que deja lista la salida de respaldo
    todo      web + cluster + respaldo; si la corrida en vivo falla, muestra el respaldo existente

  Requisitos: la imagen pp-g8 construida y, para la demo web, build/docker y build/docker-mpi
  compilados con MPI (docs/guia-reproduccion.md §3 y §9). Para -Destino swarm, los requisitos de
  scripts/deploy/desplegar_swarm.ps1 (mismo camino -Repo y mismo commit en los tres equipos).
  El commit se pasa a los contenedores como GIT_COMMIT y PP_COMMIT (en un worktree, git no resuelve
  el repositorio dentro del contenedor). Los .log de results/demo/ están en .gitignore: para
  versionar el respaldo, agréguelos con `git add -f`.

.EXAMPLE
  .\scripts\run\demo-cluster.ps1 -Accion ensayo -Destino compose -WhatIf
.EXAMPLE
  .\scripts\run\demo-cluster.ps1 -Accion todo -Destino compose -N 2000000 -Procesos 2,3
.EXAMPLE
  .\scripts\run\demo-cluster.ps1 -Accion todo -Destino swarm -Nodos pc-miguel,pc-lita,pc-david -Repo /srv/pp-g8 -HostsMpi nodo1:8,nodo2:4,nodo3:4 -Procesos 4,8,16
.EXAMPLE
  .\scripts\run\demo-cluster.ps1 -Accion mostrar -Destino compose
#>
[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'Medium')]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('web', 'cluster', 'respaldo', 'mostrar', 'detener', 'ensayo', 'todo')]
    [string]$Accion,
    [ValidateSet('compose', 'swarm-sim', 'swarm')]
    [string]$Destino = 'compose',
    [long]$N = 2000000,
    [string]$Procesos = '2,3',
    [int]$Slots = 1,                   # compose: rangos por contenedor
    [int]$Reps = 1,
    [string]$HostsMpi = 'nodo1:2,nodo2:2,nodo3:2',
    [string[]]$Nodos = @(),            # swarm: hostnames de docker node ls (equipo 1, 2, 3)
    [string]$Repo = '',                # swarm: camino absoluto del repositorio, igual en los tres equipos
    [int]$Nucleos = 0,                 # swarm: núcleos físicos totales del clúster
    [string]$Imagen = 'pp-g8',
    [int]$Puerto = 8000,
    [string]$Contenedor = 'pp-g8-demo',
    [string]$Respaldo = ''             # def. <raíz>/results/demo/respaldo
)

$ErrorActionPreference = 'Stop'
$RaizLocal = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$Compose = Join-Path $RaizLocal 'docker\compose.yaml'
$Swarm = Join-Path $RaizLocal 'scripts\deploy\desplegar_swarm.ps1'
$DirRespaldo = if ($Respaldo) { $Respaldo } else { Join-Path $RaizLocal 'results\demo\respaldo' }

function Invocar([string]$Descripcion, [scriptblock]$Bloque) {
    if ($PSCmdlet.ShouldProcess($Descripcion)) {
        $global:LASTEXITCODE = 0
        & $Bloque
        if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) { throw "falló: $Descripcion (código $LASTEXITCODE)" }
    }
}

function Requerir([string]$Nombre, $Valor) {
    if (-not $Valor) { throw "-Destino $Destino necesita -$Nombre" }
}

function Fijar-Commit {
    $commit = (git -C $RaizLocal rev-parse --short=12 HEAD 2>$null)
    $env:GIT_COMMIT = if ($commit) { $commit } else { 'desconocido' }
    $env:PP_COMMIT = if ($commit) { $commit } else { '' }
    $env:PP_IMAGEN = $Imagen
}

function Dir-Resultados {
    switch ($Destino) {
        'compose'   { return Join-Path $RaizLocal 'results\compose' }
        'swarm-sim' { return Join-Path $RaizLocal 'results\swarm-sim' }
        'swarm'     { if ($Repo) { return "$Repo/results/swarm" } else { return Join-Path $RaizLocal 'results\swarm' } }
    }
}

function Paso-Web {
    Fijar-Commit
    foreach ($exe in 'build\docker\src\backends\serial\pp_serial', 'build\docker-mpi\src\backends\mpi\pp_mpi_estatico') {
        if (-not (Test-Path (Join-Path $RaizLocal $exe))) {
            Write-Warning "falta ${exe}: compile build/docker y build/docker-mpi (docs/guia-reproduccion.md §3)"
        }
    }
    Invocar "docker rm -f $Contenedor (demo anterior, si existe)" {
        docker rm -f $Contenedor *> $null
        $global:LASTEXITCODE = 0
    }
    Invocar "docker run -d --name $Contenedor -p ${Puerto}:8000 $Imagen python3 -u scripts/demo/servidor_demo.py" {
        docker run -d --name $Contenedor -p "${Puerto}:8000" -v "${RaizLocal}:/work" -w /work `
            -e "GIT_COMMIT=$env:GIT_COMMIT" -e "PP_COMMIT=$env:PP_COMMIT" $Imagen python3 -u scripts/demo/servidor_demo.py
    }
    Write-Host "Demo web en http://127.0.0.1:$Puerto  (registro: docker logs -f $Contenedor)" -ForegroundColor Cyan
}

function Paso-Detener {
    Invocar "docker rm -f $Contenedor" { docker rm -f $Contenedor }
}

function Paso-Cluster {
    Fijar-Commit
    switch ($Destino) {
        'compose' {
            $env:PP_N = "$N"; $env:PP_PROCESOS = $Procesos; $env:PP_SLOTS = "$Slots"; $env:PP_REPS = "$Reps"
            Write-Host "Compose: N=$N procesos=$Procesos slots=$Slots reps=$Reps commit=$env:GIT_COMMIT"
            Invocar "docker compose -f docker/compose.yaml up (E1/E2 en tres contenedores de este equipo)" {
                docker compose -f $Compose up --abort-on-container-exit --exit-code-from nodo1
                $codigo = $LASTEXITCODE
                docker compose -f $Compose down -v
                $global:LASTEXITCODE = $codigo
            }
        }
        'swarm-sim' {
            & $Swarm -Accion simular -N $N -Procesos $Procesos -Reps $Reps -HostsMpi $HostsMpi -Imagen $Imagen `
                -WhatIf:$WhatIfPreference -Confirm:$false
        }
        'swarm' {
            Requerir 'Repo' $Repo
            if ($Nodos.Count -ne 3) { throw 'use -Nodos equipo1,equipo2,equipo3 (nombres de docker node ls)' }
            & $Swarm -Accion todo -Nodos $Nodos -Repo $Repo -HostsMpi $HostsMpi -Procesos $Procesos -N $N `
                -Reps $Reps -Nucleos $Nucleos -Imagen $Imagen -WhatIf:$WhatIfPreference -Confirm:$false
        }
    }
}

function Paso-Respaldo {
    $origen = Dir-Resultados
    $dest = Join-Path $DirRespaldo $Destino
    if (-not $WhatIfPreference -and -not (Test-Path $origen)) {
        throw "no hay resultados en ${origen}: ejecute antes -Accion cluster -Destino $Destino"
    }
    Invocar "copiar CSV, resúmenes y logs de $origen a $dest" {
        New-Item -ItemType Directory -Force -Path $dest | Out-Null
        $archivos = Get-ChildItem -Path $origen -File | Where-Object { $_.Extension -in '.csv', '.md', '.log' }
        if (-not $archivos) { throw "no hay CSV ni logs en $origen" }
        $archivos | Copy-Item -Destination $dest -Force
        $manifiesto = @(
            "fecha=$(Get-Date -Format s)"
            "destino=$Destino"
            "commit=$(git -C $RaizLocal rev-parse --short=12 HEAD 2>$null)"
            "n=$N procesos=$Procesos reps=$Reps slots=$Slots hosts_mpi=$HostsMpi"
            "origen=$origen"
            "archivos=$(($archivos | ForEach-Object Name) -join ',')"
        )
        Set-Content -Path (Join-Path $dest 'manifiesto.txt') -Value $manifiesto -Encoding utf8
    }
    Write-Host "Respaldo en $dest" -ForegroundColor Cyan
}

function Paso-Mostrar {
    $dest = Join-Path $DirRespaldo $Destino
    if (-not (Test-Path $dest)) { throw "no hay respaldo en ${dest}: ejecute -Accion ensayo -Destino $Destino el día anterior" }
    Write-Host "Respaldo precalculado ($dest):" -ForegroundColor Yellow
    Get-Content (Join-Path $dest 'manifiesto.txt') -ErrorAction SilentlyContinue
    $resumen = Get-ChildItem -Path $dest -Filter '*_resumen.md' -File | Select-Object -First 1
    if ($resumen) { Get-Content $resumen.FullName } else { Get-ChildItem $dest | Format-Table Name, Length, LastWriteTime }
}

switch ($Accion) {
    'web'      { Paso-Web }
    'cluster'  { Paso-Cluster }
    'respaldo' { Paso-Respaldo }
    'mostrar'  { Paso-Mostrar }
    'detener'  { Paso-Detener }
    'ensayo'   { Paso-Cluster; Paso-Respaldo }
    'todo' {
        Paso-Web
        try {
            Paso-Cluster
            Paso-Respaldo
        } catch {
            Write-Warning "la corrida en vivo falló: $($_.Exception.Message). Se muestra el respaldo precalculado."
            Paso-Mostrar
        }
    }
}
