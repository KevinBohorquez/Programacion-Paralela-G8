# T38 | Responsable: Lita | Extensión CUDA EXT1: kernel (un hilo por escenario), ejecutable pp_cuda y V2.
# Se activa con -DPP_BUILD_CUDA=ON; necesita nvcc (CUDA Toolkit). Arquitectura por defecto: 89 (RTX 4060);
# se cambia con -DCMAKE_CUDA_ARCHITECTURES=<cc>. Ver docs/decision-cuda.md y docs/inventario-gpu.md.
if(NOT DEFINED CMAKE_CUDA_ARCHITECTURES)
  set(CMAKE_CUDA_ARCHITECTURES 89)
endif()
enable_language(CUDA)
find_package(CUDAToolkit REQUIRED)

add_library(pp_cuda_lib STATIC kernel.cu)
target_include_directories(pp_cuda_lib PUBLIC ${PROJECT_SOURCE_DIR}/include)
set_target_properties(pp_cuda_lib PROPERTIES CUDA_STANDARD 17 CUDA_STANDARD_REQUIRED ON)
# -fmad=false: sin FMA implícito, como -ffp-contract=off en CPU (contrato V2).
target_compile_options(pp_cuda_lib PRIVATE $<$<COMPILE_LANGUAGE:CUDA>:-fmad=false --expt-relaxed-constexpr -lineinfo>)
target_link_libraries(pp_cuda_lib PUBLIC pp_core pp_stats CUDA::cudart)

add_executable(pp_cuda main.cpp)
target_link_libraries(pp_cuda PRIVATE pp_cuda_lib pp_io pp_stats pp_core)

# V2 (equivalencia GPU frente a CPU, tolerancia relativa 1e-6 en el conteo)
add_executable(pp_v2_cuda ${PROJECT_SOURCE_DIR}/tests/unit/v2_cuda.cpp)
target_link_libraries(pp_v2_cuda PRIVATE pp_cuda_lib pp_io pp_stats pp_core)
add_test(NAME v2_cuda COMMAND pp_v2_cuda 1000000)
set_tests_properties(v2_cuda PROPERTIES LABELS "cuda" TIMEOUT 600)
