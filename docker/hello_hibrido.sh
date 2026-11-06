#!/usr/bin/env bash
# T05 | Responsable: Miguel | Genera la evidencia del hola híbrido (se ejecuta en el anfitrión:
# Git Bash en Windows o bash en Linux, desde cualquier carpeta del repositorio).
#   bash docker/hello_hibrido.sh
# Escribe results/evidencia/t05_hello_hibrido.log (un contenedor) y
# results/evidencia/t05_hello_dos_contenedores.log (compose-hello.yaml).
set -euo pipefail
export MSYS_NO_PATHCONV=1  # Git Bash: no traducir rutas como /work

RAIZ=$(git rev-parse --show-toplevel)
cd "$RAIZ"
IMAGEN=pp-g8
SALIDA=results/evidencia
mkdir -p "$SALIDA"

cabecera() {  # $1 = comando exacto
  echo "# Comando: $1"
  echo "# Fecha: $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  echo "# Imagen: $IMAGEN $(docker image inspect -f '{{.Id}}' "$IMAGEN")"
  echo "# Commit: $(git rev-parse --short HEAD)$(git diff --quiet HEAD -- 2>/dev/null || echo ' (con cambios sin commit)')"
  echo "# Anfitrión: $(uname -s) | vCPU visibles por Docker: $(docker info -f '{{.NCPU}}')"
  echo
}

# 1) Un contenedor: 2 rangos MPI x 2 hilos OpenMP.
CMD1="docker run --rm --shm-size=1g -v \"\$PWD:/work\" -w /work -e OMP_NUM_THREADS=2 $IMAGEN bash -c 'mpicxx -fopenmp -O2 -o /tmp/hello_hibrido docker/hello_hibrido.cpp && mpirun -np 2 --bind-to none /tmp/hello_hibrido'"
{
  cabecera "$CMD1"
  docker run --rm --shm-size=1g -v "$PWD:/work" -w /work -e OMP_NUM_THREADS=2 "$IMAGEN" \
    bash -c 'mpicxx -fopenmp -O2 -o /tmp/hello_hibrido docker/hello_hibrido.cpp && mpirun -np 2 --bind-to none /tmp/hello_hibrido' 2>&1
} > "$SALIDA/t05_hello_hibrido.log"
echo "Escrito $SALIDA/t05_hello_hibrido.log"

# 2) Dos contenedores: un rango por contenedor, 2 hilos OpenMP cada uno.
COMPOSE="docker compose -f docker/compose-hello.yaml"
CMD2="$COMPOSE --progress quiet run --rm nodo1"
trap '$COMPOSE down -v >/dev/null 2>&1 || true' EXIT
{
  cabecera "$CMD2"
  $COMPOSE --progress quiet run --rm nodo1 2>&1
} > "$SALIDA/t05_hello_dos_contenedores.log"
echo "Escrito $SALIDA/t05_hello_dos_contenedores.log"
