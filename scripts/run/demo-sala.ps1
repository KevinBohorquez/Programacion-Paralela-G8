# Responsable: Miguel | Lanzador de la sala de control de la demo en vivo (docs/demo-sala-control.md).
<#
.SYNOPSIS
  Prepara, inicia, graba y reproduce la sala de control (scripts/demo/sala_control.py), que corre
  dentro de un contenedor pp-g8 publicado en el puerto 8765.

.DESCRIPTION
  Acciones (-Accion):
    preparar  construye la imagen pp-g8 si falta, compila build/docker en Release con MPI y lista
              los contenedores en marcha (para ver si algo más carga la CPU)
    iniciar   levanta el contenedor pp-sala con el servidor y espera a que responda
    detener   detiene el contenedor pp-sala
    grabar    POST /api/grabar: empieza a grabar los eventos en results/demo/sala/<Nombre>.jsonl
              (con -Parar, termina la grabación)
    replay    POST /api/replay: reproduce la grabación <Nombre> con sus tiempos (modo REPLAY)
    estado    indica si el contenedor corre y si el servidor responde

  -Simular solo imprime los comandos, sin ejecutarlos.
  El contrato del servidor (eventos SSE y API) está en docs/contrato-sala-control.md.

.EXAMPLE
  .\scripts\run\demo-sala.ps1 -Accion preparar
.EXAMPLE
  .\scripts\run\demo-sala.ps1 -Accion iniciar -Simular
.EXAMPLE
  .\scripts\run\demo-sala.ps1 -Accion grabar; .\scripts\run\demo-sala.ps1 -Accion grabar -Parar
.EXAMPLE
  .\scripts\run\demo-sala.ps1 -Accion replay -Velocidad 1.5
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('preparar', 'iniciar', 'detener', 'grabar', 'replay', 'estado')]
    [string]$Accion,
    [switch]$Simular,
    [switch]$Parar,                    # grabar: termina la grabación en curso
    [string]$Nombre = 'ensayo',        # grabar/replay: nombre de la grabación
    [double]$Velocidad = 1.0,          # replay: factor de velocidad
    [string]$Imagen = 'pp-g8',
    [string]$Contenedor = 'pp-sala',
    [int]$Puerto = 8765,
    [int]$EsperaSegundos = 60
)

$ErrorActionPreference = 'Stop'
$RaizLocal = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$Url = "http://localhost:$Puerto"

function Texto-Comando([string[]]$Comando) {
    return ($Comando | ForEach-Object { if ($_ -match '\s') { '"' + $_ + '"' } else { $_ } }) -join ' '
}

function Ejecutar([string[]]$Comando) {
    if ($Simular) {
        Write-Host "[simular] $(Texto-Comando $Comando)"
        return
    }
    $global:LASTEXITCODE = 0
    $resto = @()
    if ($Comando.Count -gt 1) { $resto = $Comando[1..($Comando.Count - 1)] }
    & $Comando[0] @resto
    if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) { throw "falló: $(Texto-Comando $Comando) (código $LASTEXITCODE)" }
}

function Llamar-Api([string]$Ruta, [hashtable]$Cuerpo) {
    $json = $Cuerpo | ConvertTo-Json -Compress
    if ($Simular) {
        Write-Host "[simular] Invoke-RestMethod -Method Post -Uri $Url$Ruta -ContentType application/json -Body '$json'"
        return
    }
    $respuesta = Invoke-RestMethod -Method Post -Uri "$Url$Ruta" -ContentType 'application/json' -Body $json
    $respuesta | ConvertTo-Json -Compress | Write-Host
}

function Servidor-Responde {
    try {
        $r = Invoke-WebRequest -Uri "$Url/" -UseBasicParsing -TimeoutSec 2
        return ($r.StatusCode -eq 200)
    } catch {
        return $false
    }
}

function Contenedor-Corre {
    $id = docker ps -q --filter "name=^${Contenedor}$" 2>$null
    return [bool]$id
}

function Commit-Actual {
    $commit = (git -C $RaizLocal rev-parse --short=12 HEAD 2>$null)
    if ($commit) { return $commit } else { return '' }
}

function Paso-Preparar {
    $hayImagen = $false
    if (-not $Simular) {
        docker image inspect $Imagen *> $null
        $hayImagen = ($LASTEXITCODE -eq 0)
        $global:LASTEXITCODE = 0
    }
    if ($hayImagen) {
        Write-Host "Imagen $Imagen ya construida." -ForegroundColor Cyan
    } else {
        if ($Simular) { Write-Host '(solo si falta la imagen)' }
        Push-Location $RaizLocal
        try { Ejecutar @('docker', 'build', '-t', $Imagen, '-f', 'docker/Dockerfile', '.') } finally { Pop-Location }
    }
    Ejecutar @('docker', 'run', '--rm', '--shm-size=1g', '-v', "${RaizLocal}:/work", '-w', '/work', $Imagen,
        'bash', '-c', 'cmake -S . -B build/docker -DCMAKE_BUILD_TYPE=Release -DPP_BUILD_MPI=ON && cmake --build build/docker --parallel')
    Write-Host 'Contenedores en marcha (cierre los que no sean de la demo para no cargar la CPU):' -ForegroundColor Yellow
    Ejecutar @('docker', 'ps', '--format', 'table {{.Names}}\t{{.Image}}\t{{.Status}}')
}

function Paso-Iniciar {
    if (-not $Simular -and (Contenedor-Corre)) {
        Write-Host "El contenedor $Contenedor ya corre: $Url" -ForegroundColor Cyan
        return
    }
    $commit = Commit-Actual
    Ejecutar @('docker', 'run', '-d', '--rm', '--name', $Contenedor, '-p', "${Puerto}:8765", '--shm-size=1g',
        '-v', "${RaizLocal}:/work", '-w', '/work', '-e', "PP_COMMIT=$commit", $Imagen,
        'python3', 'scripts/demo/sala_control.py', '--puerto', '8765', '--build-dir', 'build/docker')
    if ($Simular) {
        Write-Host "[simular] esperar a que $Url/ responda (hasta $EsperaSegundos s)"
        Write-Host "Sala de control en $Url"
        return
    }
    $limite = (Get-Date).AddSeconds($EsperaSegundos)
    while (-not (Servidor-Responde)) {
        if ((Get-Date) -gt $limite) {
            throw "el servidor no respondió en $EsperaSegundos s; revise: docker logs $Contenedor"
        }
        if (-not (Contenedor-Corre)) {
            throw "el contenedor $Contenedor terminó; ejecute -Accion preparar y vuelva a intentar"
        }
        Start-Sleep -Milliseconds 500
    }
    Write-Host "Sala de control en $Url  (registro: docker logs -f $Contenedor)" -ForegroundColor Cyan
}

function Paso-Detener {
    Ejecutar @('docker', 'stop', $Contenedor)
}

function Paso-Grabar {
    Llamar-Api '/api/grabar' @{ activo = (-not $Parar); nombre = $Nombre }
    if ($Parar) { Write-Host "Grabación detenida: results/demo/sala/$Nombre.jsonl" -ForegroundColor Cyan }
    else { Write-Host "Grabando en results/demo/sala/$Nombre.jsonl (termine con -Accion grabar -Parar)" -ForegroundColor Cyan }
}

function Paso-Replay {
    Llamar-Api '/api/replay' @{ nombre = $Nombre; velocidad = $Velocidad }
    Write-Host "Reproduciendo $Nombre en $Url (distintivo REPLAY en la interfaz)" -ForegroundColor Cyan
}

function Paso-Estado {
    if ($Simular) {
        Write-Host "[simular] docker ps -q --filter name=^${Contenedor}$"
        Write-Host "[simular] Invoke-WebRequest -Uri $Url/ -UseBasicParsing -TimeoutSec 2"
        return
    }
    $corre = Contenedor-Corre
    $responde = Servidor-Responde
    Write-Host ("Contenedor ${Contenedor}: " + $(if ($corre) { 'en marcha' } else { 'detenido' }))
    Write-Host ("Servidor ${Url}: " + $(if ($responde) { 'responde' } else { 'no responde' }))
}

switch ($Accion) {
    'preparar' { Paso-Preparar }
    'iniciar'  { Paso-Iniciar }
    'detener'  { Paso-Detener }
    'grabar'   { Paso-Grabar }
    'replay'   { Paso-Replay }
    'estado'   { Paso-Estado }
}
