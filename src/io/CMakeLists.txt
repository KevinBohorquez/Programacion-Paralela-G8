# T12 | Responsable: Ashley | Fuentes de entrada y salida (configuración y CSV).
add_library(pp_io STATIC configuracion.cpp resultados_csv.cpp progreso.cpp)
# progreso.hpp vive junto a su fuente: lo usan todos los backends a través de pp_io.
target_include_directories(pp_io PUBLIC ${PROJECT_SOURCE_DIR}/include ${CMAKE_CURRENT_SOURCE_DIR})
target_link_libraries(pp_io PUBLIC pp_stats pp_core)
# Commit para los metadatos del CSV (se puede sobrescribir en ejecución con PP_COMMIT).
find_package(Git QUIET)
if(GIT_FOUND)
  execute_process(COMMAND ${GIT_EXECUTABLE} rev-parse --short=12 HEAD
                  WORKING_DIRECTORY ${PROJECT_SOURCE_DIR}
                  OUTPUT_VARIABLE PP_GIT_COMMIT OUTPUT_STRIP_TRAILING_WHITESPACE ERROR_QUIET)
endif()
if(PP_GIT_COMMIT)
  target_compile_definitions(pp_io PRIVATE PP_COMMIT_GIT="${PP_GIT_COMMIT}")
endif()
