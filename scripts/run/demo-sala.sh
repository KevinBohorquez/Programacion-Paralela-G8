#!/usr/bin/env bash
# Responsable: Miguel | Lanzador de la sala de control (equivalente a demo-sala.ps1, para Linux y macOS).
#
# Uso: scripts/run/demo-sala.sh <accion> [--simular] [--parar] [--nombre N] [--velocidad V]
#   preparar  construye pp-g8 si falta, compila build/docker (Release, MPI) y lista los contenedores
#   iniciar   levanta el contenedor pp-sala con el servidor en el puerto 8765 y espera a que responda
#   detener   detiene el contenedor pp-sala
#   grabar    POST /api/grabar (con --parar, termina la grabación)
#   replay    POST /api/replay con la grabación --nombre (por defecto «ensayo»)
#   estado    indica si el contenedor corre y si el servidor responde
# --simular solo imprime los comandos. Contrato del servidor: docs/contrato-sala-control.md.
set -euo pipefail

RAIZ="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
IMAGEN="${PP_IMAGEN:-pp-g8}"
CONTENEDOR="pp-sala"
PUERTO="${PP_PUERTO:-8765}"
URL="http://localhost:${PUERTO}"
ESPERA=60
SIMULAR=0
PARAR=0
NOMBRE="ensayo"
VELOCIDAD="1.0"
export MSYS_NO_PATHCONV=1   # Git Bash: no traducir /work a una ruta de Windows

uso() { sed -n '4,11p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit "${1:-1}"; }

[ $# -ge 1 ] || uso
ACCION="$1"; shift
while [ $# -gt 0 ]; do
    case "$1" in
        --simular)   SIMULAR=1 ;;
        --parar)     PARAR=1 ;;
        --nombre)    NOMBRE="$2"; shift ;;
        --velocidad) VELOCIDAD="$2"; shift ;;
        -h|--help)   uso 0 ;;
        *) echo "opción desconocida: $1" >&2; uso ;;
    esac
    shift
done

ejecutar() {
    if [ "$SIMULAR" -eq 1 ]; then
        printf '[simular]'; printf ' %q' "$@"; printf '\n'
    else
        "$@"
    fi
}

llamar_api() {   # $1 = ruta, $2 = cuerpo JSON
    if [ "$SIMULAR" -eq 1 ]; then
        echo "[simular] curl -fsS -X POST ${URL}$1 -H 'Content-Type: application/json' -d '$2'"
    else
        curl -fsS -X POST "${URL}$1" -H 'Content-Type: application/json' -d "$2"; echo
    fi
}

servidor_responde() { curl -fsS -o /dev/null --max-time 2 "${URL}/" 2>/dev/null; }
contenedor_corre() { [ -n "$(docker ps -q --filter "name=^${CONTENEDOR}\$" 2>/dev/null)" ]; }

paso_preparar() {
    if [ "$SIMULAR" -eq 0 ] && docker image inspect "$IMAGEN" >/dev/null 2>&1; then
        echo "Imagen $IMAGEN ya construida."
    else
        [ "$SIMULAR" -eq 1 ] && echo "(solo si falta la imagen)"
        (cd "$RAIZ" && ejecutar docker build -t "$IMAGEN" -f docker/Dockerfile .)
    fi
    ejecutar docker run --rm --shm-size=1g -v "${RAIZ}:/work" -w /work "$IMAGEN" \
        bash -c 'cmake -S . -B build/docker -DCMAKE_BUILD_TYPE=Release -DPP_BUILD_MPI=ON && cmake --build build/docker --parallel'
    echo "Contenedores en marcha (cierre los que no sean de la demo para no cargar la CPU):"
    ejecutar docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}'
}

paso_iniciar() {
    if [ "$SIMULAR" -eq 0 ] && contenedor_corre; then
        echo "El contenedor $CONTENEDOR ya corre: $URL"; return
    fi
    local commit
    commit="$(cd "$RAIZ" && git rev-parse --short=12 HEAD 2>/dev/null || true)"
    ejecutar docker run -d --rm --name "$CONTENEDOR" -p "${PUERTO}:8765" --shm-size=1g \
        -v "${RAIZ}:/work" -w /work -e "PP_COMMIT=${commit}" "$IMAGEN" \
        python3 scripts/demo/sala_control.py --puerto 8765 --build-dir build/docker
    if [ "$SIMULAR" -eq 1 ]; then
        echo "[simular] esperar a que ${URL}/ responda (hasta ${ESPERA} s)"
        echo "Sala de control en $URL"; return
    fi
    local fin=$((SECONDS + ESPERA))
    until servidor_responde; do
        if [ "$SECONDS" -ge "$fin" ]; then
            echo "el servidor no respondió en ${ESPERA} s; revise: docker logs $CONTENEDOR" >&2; exit 1
        fi
        if ! contenedor_corre; then
            echo "el contenedor $CONTENEDOR terminó; ejecute 'preparar' y vuelva a intentar" >&2; exit 1
        fi
        sleep 0.5
    done
    echo "Sala de control en $URL  (registro: docker logs -f $CONTENEDOR)"
}

paso_detener() { ejecutar docker stop "$CONTENEDOR"; }

paso_grabar() {
    if [ "$PARAR" -eq 1 ]; then
        llamar_api /api/grabar "{\"activo\": false, \"nombre\": \"${NOMBRE}\"}"
        echo "Grabación detenida: results/demo/sala/${NOMBRE}.jsonl"
    else
        llamar_api /api/grabar "{\"activo\": true, \"nombre\": \"${NOMBRE}\"}"
        echo "Grabando en results/demo/sala/${NOMBRE}.jsonl (termine con: grabar --parar)"
    fi
}

paso_replay() {
    llamar_api /api/replay "{\"nombre\": \"${NOMBRE}\", \"velocidad\": ${VELOCIDAD}}"
    echo "Reproduciendo ${NOMBRE} en $URL (distintivo REPLAY en la interfaz)"
}

paso_estado() {
    if [ "$SIMULAR" -eq 1 ]; then
        echo "[simular] docker ps -q --filter name=^${CONTENEDOR}\$"
        echo "[simular] curl -fsS -o /dev/null --max-time 2 ${URL}/"; return
    fi
    if contenedor_corre; then echo "Contenedor ${CONTENEDOR}: en marcha"; else echo "Contenedor ${CONTENEDOR}: detenido"; fi
    if servidor_responde; then echo "Servidor ${URL}: responde"; else echo "Servidor ${URL}: no responde"; fi
}

case "$ACCION" in
    preparar) paso_preparar ;;
    iniciar)  paso_iniciar ;;
    detener)  paso_detener ;;
    grabar)   paso_grabar ;;
    replay)   paso_replay ;;
    estado)   paso_estado ;;
    *) echo "acción desconocida: $ACCION" >&2; uso ;;
esac
