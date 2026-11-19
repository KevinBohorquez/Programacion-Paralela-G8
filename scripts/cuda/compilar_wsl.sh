#!/usr/bin/env bash
# T38 | Responsable: Lita | Configura y compila la extensión CUDA en WSL (Ubuntu-24.04, CUDA 13.3).
# La imagen Docker pp-g8 no trae CUDA (docs/inventario-gpu.md §3), así que EXT1 se compila en WSL nativo.
#
#   wsl -d Ubuntu-24.04 -- bash scripts/cuda/compilar_wsl.sh            # configura y compila build/cuda
#   wsl -d Ubuntu-24.04 -- bash scripts/cuda/compilar_wsl.sh --probar   # además corre V2 (ctest -L cuda)
#
# Variables opcionales: CMAKE (ruta de cmake), NVCC (ruta de nvcc), BUILD_DIR (por defecto build/cuda),
# PP_MPI (ON/OFF; por defecto ON si hay mpicxx: compila pp_mpi_dinamico_gpu de EXT2).
set -euo pipefail
cd "$(dirname "$0")/../.."

CMAKE="${CMAKE:-$(command -v cmake || echo "$HOME/.local/cmake/data/bin/cmake")}"
NVCC="${NVCC:-/usr/local/cuda/bin/nvcc}"
BUILD_DIR="${BUILD_DIR:-build/cuda}"
CTEST="$(dirname "$CMAKE")/ctest"
export PATH="$(dirname "$NVCC"):$PATH"

# MPI (EXT2, T41) se activa si hay mpicxx; se puede forzar con PP_MPI=ON|OFF.
PP_MPI="${PP_MPI:-$(command -v mpicxx >/dev/null && echo ON || echo OFF)}"

"$CMAKE" -S . -B "$BUILD_DIR" -DCMAKE_BUILD_TYPE=Release -DPP_BUILD_CUDA=ON -DCMAKE_CUDA_COMPILER="$NVCC" \
  -DPP_BUILD_MPI="$PP_MPI"
"$CMAKE" --build "$BUILD_DIR" -j "$(nproc)"

if [[ "${1:-}" == "--probar" ]]; then
  "$CTEST" --test-dir "$BUILD_DIR" -L cuda --output-on-failure
fi
