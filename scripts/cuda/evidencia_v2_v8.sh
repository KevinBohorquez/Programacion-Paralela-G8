#!/usr/bin/env bash
# T58 | Responsable: Lita | Regenera la evidencia de V2 y V8 de la extensión CUDA sobre el commit actual:
#   results/validacion/t38_v2_cuda.txt  (V2: pp_v2_cuda 1000000)
#   results/validacion/t39_v8_cuda.txt  (V8: compute-sanitizer con memcheck, racecheck, initcheck y synccheck)
#
#   wsl -d Ubuntu-24.04 -- bash scripts/cuda/evidencia_v2_v8.sh
#
# Exige un árbol de trabajo limpio, para que el commit del encabezado sea exactamente el código medido.
# Compila primero con scripts/cuda/compilar_wsl.sh. Variables: BUILD_DIR (por defecto build/cuda),
# SANITIZER (por defecto /usr/local/cuda/bin/compute-sanitizer).
set -euo pipefail
cd "$(dirname "$0")/../.."

BUILD_DIR="${BUILD_DIR:-build/cuda}"
SANITIZER="${SANITIZER:-/usr/local/cuda/bin/compute-sanitizer}"
OUT=results/validacion

# core.autocrlf=true: en un checkout de Windows (finales CRLF) leído desde WSL, git no debe ver cambios.
if [[ -n "$(git -c core.autocrlf=true status --porcelain --untracked-files=no)" ]]; then
  echo "error: hay cambios sin commit; la evidencia debe corresponder a un commit" >&2
  exit 2
fi
COMMIT="$(git rev-parse --short=12 HEAD)"
RAMA="$(git rev-parse --abbrev-ref HEAD)"
FECHA="$(date '+%Y-%m-%d %H:%M')"

bash scripts/cuda/compilar_wsl.sh
V2="$BUILD_DIR/src/backends/cuda/pp_v2_cuda"
CUDA="$BUILD_DIR/src/backends/cuda/pp_cuda"

# --- V2 ---
{
  echo "# T38/T39/T58 | V2 (equivalencia GPU frente a CPU) | $FECHA | rama $RAMA, commit $COMMIT"
  echo "# Comando: wsl -d Ubuntu-24.04 -- bash scripts/cuda/evidencia_v2_v8.sh (pp_v2_cuda 1000000, -fmad=false)"
  echo "# Criterio: |k_gpu - k_cpu| / k_cpu <= 1e-6 y suma del histograma = n; amax bit a bit es solo diagnóstico"
  echo "# (la igualdad exacta de k y del histograma es un resultado empírico, no una garantía)."
  "$V2" 1000000
} > "$OUT/t38_v2_cuda.txt"
echo "V2 -> $OUT/t38_v2_cuda.txt"

# --- V8 --- (mismos casos que las pruebas v8_* de src/backends/cuda/CMakeLists.txt)
resumen() {  # herramienta, caso, argumentos legibles, comando...
  local herr="$1" caso="$2" desc="$3"; shift 3
  local salida codigo=0
  salida="$("$@" 2>&1)" || codigo=$?
  local linea
  linea="$(grep -E '(ERROR|RACECHECK|LEAK) SUMMARY' <<<"$salida" | tr '\n' ' ' | sed 's/ *$//')"
  echo "[V8] herramienta=$herr caso=$caso ($desc) codigo=$codigo | $linea"
  [[ $codigo -eq 0 ]]
}
ok=1
{
  echo "# T39/T58 | V8 (memoria y carreras en la GPU con compute-sanitizer) | $FECHA | rama $RAMA, commit $COMMIT"
  echo "# GPU: $(nvidia-smi --query-gpu=name,driver_version --format=csv,noheader 2>/dev/null || echo desconocida) · $("$SANITIZER" --version | tail -1)"
  echo "# Criterio: 0 errores en memcheck (con --leak-check full), racecheck, initcheck y synccheck (CTest: ctest -L v8)."
  echo
  for herr in memcheck racecheck initcheck synccheck; do
    extra=()
    [[ $herr == memcheck ]] && extra=(--leak-check full)
    resumen "$herr" auto "--n 20000" "$SANITIZER" --tool "$herr" "${extra[@]}" --error-exitcode 9 \
      "$CUDA" --config config/sintetico.yaml --kappa 2 --n 20000 --silencioso || ok=0
    resumen "$herr" ociosos "--n 777 --bloques 200 --hilos-por-bloque 512" "$SANITIZER" --tool "$herr" "${extra[@]}" \
      --error-exitcode 9 "$CUDA" --config config/sintetico.yaml --kappa 2 --n 777 --bloques 200 \
      --hilos-por-bloque 512 --silencioso || ok=0
  done
  resumen memcheck fallo_reserva "pp_v2_cuda --fallo-reserva, --report-api-errors no" "$SANITIZER" --tool memcheck \
    --leak-check full --report-api-errors no --error-exitcode 9 "$V2" --fallo-reserva || ok=0
  echo
  echo "# Controles negativos: memcheck detecta una escritura fuera de rango y racecheck una lectura de memoria"
  echo "# compartida escrita por otro warp sin __syncthreads() (kernels defectuosos a propósito, fuera del repositorio,"
  echo "# T39). fallo_reserva, con el kernel.cu anterior a T58 (commit 71901c6), informa «LEAK SUMMARY: 4104 bytes"
  echo "# leaked in 2 allocations» (código 9): los buffers del histograma y de k no se liberaban."
} > "$OUT/t39_v8_cuda.txt"
echo "V8 -> $OUT/t39_v8_cuda.txt"
[[ $ok -eq 1 ]] || { echo "V8 con errores" >&2; exit 1; }
