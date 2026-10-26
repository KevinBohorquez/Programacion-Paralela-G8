#!/usr/bin/env bash
# T22,T25 | Responsable: Miguel | Papel de un nodo en docker/compose.yaml y docker/swarm-stack.yaml.
#   nodo_mpi.sh trabajador   compila (si PP_COMPILAR=1) y deja sshd en primer plano
#   nodo_mpi.sh lanzador     compila, espera a los trabajadores por ssh y mide E1 y E2 con mpirun
# Variables (todas opcionales):
#   PP_BUILD=/opt/pp/build      directorio de compilación (mismo camino en todos los nodos)
#   PP_COMPILAR=1               0 = no compila (Compose: el volumen de binarios es compartido)
#   PP_NODOS=nodo1,nodo2        hosts del mpirun; PP_SLOTS=2 slots (rangos) por host
#   PP_HOSTS=nodo1:8,nodo2:4    alternativa con slots por host (tiene prioridad sobre PP_NODOS)
#   PP_PROCESOS=4               lista de procesos para E1/E2 (p. ej. 2,4,8)
#   PP_N=2000000  PP_REPS=5  PP_LOTE=0  PP_CONFIG=config/sintetico.yaml
#   PP_RED_TCP=eth0             interfaz o CIDR para btl/oob tcp (Swarm: la subred overlay)
#   PP_RESULTADOS=/resultados   dónde quedan e1_estatico.csv, e2_dinamico.csv y la comparación
#   GIT_COMMIT                  commit del anfitrión (dentro del contenedor git no ve el worktree);
#                               lo leen los scripts de medición para su propio CSV
#   PP_COMMIT                   commit que escriben los simuladores pp_* (columna `commit`); si falta,
#                               se toma de GIT_COMMIT. Se reenvía a todos los rangos con `mpirun -x`
set -euo pipefail

ROL=${1:?uso: nodo_mpi.sh trabajador|lanzador}
BUILD=${PP_BUILD:-/opt/pp/build}
SRC=${PP_SRC:-/work}

compilar() {
  echo "[$(hostname)] compilando en $BUILD"
  cmake -S "$SRC" -B "$BUILD" -DCMAKE_BUILD_TYPE=Release -DPP_BUILD_MPI=ON > /dev/null
  cmake --build "$BUILD" --parallel --target pp_serial pp_mpi_estatico pp_mpi_dinamico pp_hibrido > /dev/null
}

if [ "${PP_COMPILAR:-1}" = "1" ]; then
  compilar
fi

if [ "$ROL" = "trabajador" ]; then
  exec /usr/sbin/sshd -D -e
fi
[ "$ROL" = "lanzador" ] || { echo "papel desconocido: $ROL" >&2; exit 64; }

SLOTS=${PP_SLOTS:-2}
if [ -n "${PP_HOSTS:-}" ]; then  # slots distintos por nodo (equipos heterogéneos): nodo1:8,nodo2:4
  HOSTS=$PP_HOSTS
  NODOS=$(echo "$HOSTS" | tr ',' '\n' | cut -d: -f1 | paste -sd, -)
else
  NODOS=${PP_NODOS:-nodo1,nodo2}
  HOSTS=$(echo "$NODOS" | tr ',' '\n' | sed "s/\$/:$SLOTS/" | paste -sd, -)
fi
RES=${PP_RESULTADOS:-/resultados}
mkdir -p "$RES"

# Commit de los simuladores: PP_COMMIT o, si falta, GIT_COMMIT. Con `desconocido` no se exporta y
# cada binario conserva el commit que CMake leyó al configurar.
if [ -z "${PP_COMMIT:-}" ] && [ -n "${GIT_COMMIT:-}" ] && [ "$GIT_COMMIT" != "desconocido" ]; then
  PP_COMMIT=$GIT_COMMIT
fi
MPIRUN_EXTRA=()
if [ -n "${PP_COMMIT:-}" ]; then
  export PP_COMMIT
  # Los rangos remotos (lanzados por ssh) solo heredan las variables pasadas con -x.
  MPIRUN_EXTRA=("--mpirun-extra=-x PP_COMMIT")
fi

# Espera a que cada trabajador acepte ssh (en Swarm, además, a que termine de compilar: sshd arranca después).
for h in ${NODOS//,/ }; do
  [ "$h" = "$(hostname)" ] && continue
  for i in $(seq 1 ${PP_ESPERA_S:-600}); do
    ssh -o ConnectTimeout=2 "$h" test -x "$BUILD/src/backends/mpi/pp_mpi_dinamico" 2>/dev/null && break
    [ "$i" = "${PP_ESPERA_S:-600}" ] && { echo "sin respuesta de $h" >&2; exit 1; }
    sleep 1
  done
  echo "[$(hostname)] $h listo"
done

COMUNES=(--experimento x3 --recursos "${PP_PROCESOS:-4}" --cargas "${PP_N:-2000000}" --reps "${PP_REPS:-5}"
         --hosts "$HOSTS" --red-tcp "${PP_RED_TCP:-eth0}" --build-dir "$BUILD" --config "${PP_CONFIG:-config/sintetico.yaml}"
         --lote "${PP_LOTE:-0}" "${MPIRUN_EXTRA[@]}")
if [ -n "${PP_NUCLEOS:-}" ]; then  # núcleos físicos totales del clúster (marca de sobresuscripción)
  COMUNES+=(--nucleos "$PP_NUCLEOS")
fi

python3 scripts/bench/ejecutar_barridos.py "${COMUNES[@]}" --backend mpi_estatico --salida "$RES/e1_estatico.csv"
python3 scripts/bench/ejecutar_barridos.py "${COMUNES[@]}" --backend mpi_dinamico --salida "$RES/e2_dinamico.csv"
python3 scripts/bench/comparar_mpi_heterogeneo.py --hosts "$HOSTS" \
  --desde-csv "$RES/e1_estatico.csv,$RES/e2_dinamico.csv" --salida "$RES/e1_e2_comparacion.csv"
