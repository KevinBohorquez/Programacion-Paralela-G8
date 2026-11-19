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

# V8 (memoria y carreras en la GPU, T39): compute-sanitizer sobre pp_cuda con cuatro herramientas.
# Cada prueba falla si la herramienta informa cualquier error (--error-exitcode). Se usan N pequeños
# porque los sanitizadores ralentizan el kernel; los casos cubren la grilla automática, bloques y hilos
# sin trabajo (777 escenarios con 200 × 512 hilos) y H5 (kappa = 2).
find_program(PP_COMPUTE_SANITIZER compute-sanitizer HINTS "${CUDAToolkit_BIN_DIR}")
if(PP_COMPUTE_SANITIZER)
  set(V8_CASOS
      "auto|--n,20000"
      "ociosos|--n,777,--bloques,200,--hilos-por-bloque,512")
  foreach(herramienta memcheck racecheck initcheck synccheck)
    set(extra "")
    if(herramienta STREQUAL "memcheck")
      set(extra --leak-check full)
    endif()
    foreach(caso IN LISTS V8_CASOS)
      string(REPLACE "|" ";" partes "${caso}")
      string(REPLACE "," ";" partes "${partes}")
      list(GET partes 0 nombre)
      list(REMOVE_AT partes 0)
      set(args ${partes})
      add_test(NAME v8_${herramienta}_${nombre}
               COMMAND ${PP_COMPUTE_SANITIZER} --tool ${herramienta} ${extra} --error-exitcode 9
                       $<TARGET_FILE:pp_cuda> --config ${PROJECT_SOURCE_DIR}/config/sintetico.yaml --kappa 2
                       ${args} --silencioso)
      set_tests_properties(v8_${herramienta}_${nombre} PROPERTIES LABELS "cuda;v8" TIMEOUT 900)
    endforeach()
  endforeach()
else()
  message(WARNING "No se encontró compute-sanitizer: las pruebas V8 no se registran.")
endif()

# V2 a nivel de ejecutables (T39): pp_cuda frente a pp_serial con las mismas opciones y el mismo CSV.
# tests/concurrency/test_cuda.py corre con pytest o, si no está instalado, con python3 directamente.
find_package(Python3 COMPONENTS Interpreter QUIET)
if(Python3_FOUND)
  add_test(NAME v2_cuda_ejecutables COMMAND ${Python3_EXECUTABLE} ${PROJECT_SOURCE_DIR}/tests/concurrency/test_cuda.py)
  set_tests_properties(v2_cuda_ejecutables PROPERTIES LABELS "cuda" TIMEOUT 900
                       ENVIRONMENT "PP_CUDA_BIN_DIR=${CMAKE_BINARY_DIR}/src/backends")
endif()

# EXT2 (T41): la GPU como trabajador MPI del esquema dinámico E2. Necesita -DPP_BUILD_MPI=ON.
# V1 (bit a bit frente a la referencia secuencial, --verificar) y V3 (suma = N, cobertura de la cola)
# con 2 procesos (maestro + solo GPU), 3 y 4 (maestro + CPU + GPU), y un caso con bloques grandes.
if(TARGET pp_mpi_esquemas)
  add_executable(pp_mpi_dinamico_gpu trabajador_mpi.cpp)
  target_link_libraries(pp_mpi_dinamico_gpu PRIVATE pp_mpi_esquemas pp_cuda_lib)

  set(EXT2_EXTRA "")
  execute_process(COMMAND ${MPIEXEC_EXECUTABLE} --version OUTPUT_VARIABLE EXT2_MPI_VERSION ERROR_QUIET)
  if(EXT2_MPI_VERSION MATCHES "Open MPI|OpenRTE")
    set(EXT2_EXTRA --oversubscribe --bind-to none)
  endif()
  set(EXT2_CASOS
      "np2|2|--n,10007,--dias,30,--lote,100"
      "np3|3|--n,10007,--dias,30,--lote,100,--kappa,2"
      "np4|4|--n,10007,--dias,30,--lote,100,--bloques,4,--hilos-por-bloque,128"
      "np4_lote_grande|4|--n,300007,--lote,62500")
  foreach(caso IN LISTS EXT2_CASOS)
    string(REPLACE "|" ";" partes "${caso}")
    string(REPLACE "," ";" partes "${partes}")
    list(GET partes 0 nombre)
    list(GET partes 1 np)
    list(REMOVE_AT partes 0 1)
    add_test(NAME ext2_${nombre}
             COMMAND ${MPIEXEC_EXECUTABLE} ${MPIEXEC_NUMPROC_FLAG} ${np} ${EXT2_EXTRA}
                     $<TARGET_FILE:pp_mpi_dinamico_gpu> --config ${PROJECT_SOURCE_DIR}/config/sintetico.yaml
                     ${partes} --verificar --silencioso --salida ${CMAKE_BINARY_DIR}/pruebas/ext2_${nombre}.csv)
    set_tests_properties(ext2_${nombre} PROPERTIES LABELS "cuda;ext2" TIMEOUT 300
                         PASS_REGULAR_EXPRESSION "estado=OK.*v1_referencia=OK")
  endforeach()
endif()
