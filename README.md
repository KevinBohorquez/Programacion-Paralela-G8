# Simulación paralela del riesgo de inundación urbana

Proyecto 8 del curso Programación Concurrente y Paralela, UNMSM 2026-II. El simulador estima con Monte Carlo la probabilidad de que el agua acumulada supere un umbral durante una temporada de lluvias, con backends **secuencial, OpenMP, MPI estático, MPI dinámico (maestro–trabajador) e híbrido MPI + OpenMP**, todos sobre el mismo núcleo y con resultados idénticos bit a bit (V1). La extensión CUDA (EXT1: kernel en GPU validado con V2/V8; EXT2: GPU como trabajador MPI) está diseñada y en desarrollo; todavía no tiene kernels implementados (ver [docs/decision-cuda.md](docs/decision-cuda.md)).

## Propósito

La precipitación diaria se genera con una cadena de Markov (ocurrencia) y montos gamma, calibrados con series SENAMHI por estación y régimen (normal / El Niño); un balance hídrico simplificado compara el agua acumulada con la capacidad de drenaje y el umbral. Cada escenario usa un índice global `c*N + j` y Philox, así que el resultado no depende del número de hilos o procesos.

La definición y los criterios de aceptación están en [docs/definicion-proyecto.docx](docs/definicion-proyecto.docx). El estado de las tareas se registra en [cronograma/cronograma-interno.xlsx](cronograma/cronograma-interno.xlsx) y el resumen de entregables en [cronograma/cronograma-presentacion.xlsx](cronograma/cronograma-presentacion.xlsx). La [revisión interna de la definición](docs/acta-revision-definicion.md) registra las decisiones vigentes y las aprobaciones individuales que faltan para acreditar T01.

Para ejecutar las pruebas, las mediciones y las corridas científicas en otro equipo (a mano o con un agente de código), seguir [AGENTS.md](AGENTS.md): orden de pasos, reglas de medición y qué entregar.

Los [contratos de CLI, configuración y CSV (T02)](docs/contratos.md) fijan el índice global, la semilla, el acumulador y el formato de salida que comparten todos los backends.

## Qué hay implementado

| Pieza | Dónde | Evidencia |
| --- | --- | --- |
| Núcleo (Philox, Markov-gamma, balance) | `src/core/`, `include/` | `smoke`, V7 analítica |
| Secuencial y OpenMP | `src/backends/serial/`, `src/backends/openmp/` | V1 (`v1_equivalencia_openmp`), V5 con Archer |
| MPI estático, dinámico e híbrido | `src/backends/mpi/`, `src/backends/hybrid/` (`-DPP_BUILD_MPI=ON`) | `ctest` con 1–16 procesos |
| Datos SENAMHI y calibración (T06–T10) | `data/raw/`, `data/processed/`, `scripts/run/` | [auditoria-datos.md](docs/auditoria-datos.md), [criterio-seleccion-estaciones.md](docs/criterio-seleccion-estaciones.md) |
| Configuraciones por estación y régimen | `config/<estacion>_<regimen>.yaml` (5 estaciones × 2 regímenes) | `generar_configs.py` |
| Línea base y barrido OpenMP (T14, T16, T18) | `results/bench/`, `results/figures/` | [protocolo-graficos-openmp.md](docs/protocolo-graficos-openmp.md) |
| Mediciones MPI, híbrido y barridos X1–X3 (T21, T26, T27, T30, T31) | `scripts/bench/medir_mpi.py`, `medir_hibrido.py`, `ejecutar_barridos.py` | [guia-reproduccion.md §6](docs/guia-reproduccion.md) |
| Corridas científicas X6, bootstrap y X7 (T34, T35, T42) | `scripts/run/corrida-oficial.py`, `analizar-riesgo.py`, `sensibilidad.py` | [guia-reproduccion.md §7](docs/guia-reproduccion.md) |
| Análisis de rendimiento y figuras finales (T33, T45) | `scripts/bench/analizar-rendimiento.py`, `graficar-final.py` | `tests/unit/test_analizar_rendimiento.py`, `test_graficar_final.py` |
| Compose y Swarm (T22, T25) | `docker/compose.yaml`, `docker/swarm-stack.yaml`, `scripts/deploy/desplegar_swarm.ps1` | [docker/README.md](docker/README.md) |
| Validación V1, V5, V6, V7 | `tests/`, `results/validacion/` | ver la sección «Pruebas» |
| Demo web de la exposición | `scripts/demo/servidor_demo.py` | — |

## Compilar y probar (Docker)

La cadena de herramientas (CMake, g++, OpenMPI, Python con pytest/numpy/scipy) vive en la imagen `pp-g8` ([docker/](docker/)). Desde la raíz del repositorio (en Git Bash anteponer `MSYS_NO_PATHCONV=1`):

```bash
# Build oficial: núcleo, secuencial, OpenMP, MPI e híbrido en build/docker
# (sin -DPP_BUILD_MPI=ON solo se compilan el secuencial y OpenMP)
docker run --rm --shm-size=1g -v "$PWD:/work" -w /work pp-g8 bash -c \
  "cmake -S . -B build/docker -DCMAKE_BUILD_TYPE=Release -DPP_BUILD_MPI=ON && cmake --build build/docker -j && ctest --test-dir build/docker --output-on-failure"

# Una corrida con una configuración calibrada
docker run --rm -v "$PWD:/work" -w /work pp-g8 \
  build/docker/src/backends/serial/pp_serial --config config/piura_miraflores_el_nino.yaml --n 100000 --salida /tmp/r.csv
```

`build/docker` es el directorio por defecto de `--build-dir` en todos los scripts de medición y de corridas científicas.

Los ejecutables registran el commit desde `PP_COMMIT` si está definida (útil en contenedores o worktrees donde `git` no resuelve el repositorio).

## Pruebas

- `ctest` por defecto: `smoke`, `v6_generador` (V6 del generador frente a sus parámetros), `v1_equivalencia_openmp`, `v7_analitico` y, con MPI, los ejecutables MPI/híbrido con 1–16 procesos.
- `v6_observado` (V6 frente a las series SENAMHI) está registrada con la etiqueta `v6_observado` pero **desactivada** por defecto, porque hoy no cumple el 10 % en los estadísticos de cola (ver `results/validacion/w0_v6_observado.log`). Se ejecuta con `cmake -DPP_V6_OBSERVADO=ON ...` y `ctest -L v6_observado --output-on-failure`.
- Pruebas de scripts y de los binarios, en la imagen `pp-g8` y con un build que incluya MPI:

  ```bash
  PP_BIN_DIR=build/docker/src/backends PP_V6_GENERADOR=build/docker/pp_v6_generador \
    python3 -m pytest -q tests/unit -k "not observado"
  ```

  `-k "not observado"` excluye V6 frente a lo observado, que hoy falla de forma esperada (ver arriba). `PP_BIN_DIR` (carpeta `.../src/backends`) y `PP_V6_GENERADOR` (ruta de `pp_v6_generador`) son necesarias: sin ellas, las pruebas que ejecutan binarios se **omiten en silencio** (`skipped`) y un verde no prueba los ejecutables.
- Commit en worktrees: dentro del contenedor `git` no resuelve un worktree (su `.git` apunta a una ruta de Windows). Pase ambas variables con `-e PP_COMMIT=$(git rev-parse --short=12 HEAD) -e GIT_COMMIT=$(git rev-parse --short=12 HEAD)`: los ejecutables `pp_*` escriben `PP_COMMIT` en la columna `commit` (también la leen `medir_*.py` y los scripts de `scripts/run/`), y `ejecutar_barridos.py`, `comparar_mpi_heterogeneo.py`, Compose y Swarm leen `GIT_COMMIT`. Detalle en la [guía de reproducción](docs/guia-reproduccion.md).

## Datos y calibración (T06–T10)

Las series diarias de `data/raw/` y las salidas de `data/processed/` están versionadas. Para regenerarlas, en la imagen `pp-g8`:

```bash
python3 scripts/run/auditoria_datos.py
python3 scripts/run/clasificar_regimenes.py
python3 scripts/run/calibrar.py --semilla 20261015
python3 scripts/run/generar_configs.py
```

## Equipo

| Rol | Integrante | Responsabilidad principal |
| --- | --- | --- |
| R1 | David | Integración, MPI, coordinación y entregas |
| R2 | Angela | Series SENAMHI, calibración y análisis de riesgo |
| R3 | Ashley | Núcleo secuencial, OpenMP, pruebas y CI |
| R4 | Lita | Pruebas de correctitud, barridos de recursos y extensión CUDA |
| R5 | Miguel | Docker, clúster, automatización y mediciones |
| R6 | Rhamses | Documentación, gráficos, informe y exposición |

Los roles se asignaron en el orden en que se proporcionaron los nombres. Cualquier cambio de responsables debe reflejarse en ambos cronogramas y en los planes.

## Flujo de contribución (T03)

Cada integrante trabaja en su rama (`angela`, `ashley`, `lita`, `miguel`, `sevan`, `rhamses`), la sube y abre un pull request hacia `master` con la [plantilla](.github/pull_request_template.md). El revisor es el de la columna «Revisor» del cronograma. Un PR por tarea o grupo corto de tareas; solo se tocan los archivos reservados a la tarea. Los mensajes de commit siguen Conventional Commits en español.

## Plan de trabajo

- [Plan de desarrollo hasta la semana 8](docs/plan-desarrollo-semana-8.md): definición, datos, entorno, referencia secuencial y OpenMP.
- [Plan de desarrollo hasta la semana 15](docs/plan-desarrollo-semana-15.md): MPI, híbrido, campañas de rendimiento y científicas, informe y exposición. La extensión CUDA está en desarrollo.

Las rutas reservadas para programar y los formatos de cada entrega están en las columnas **V–W** de la hoja `Tareas` del [cronograma interno](cronograma/cronograma-interno.xlsx).

## Estructura

| Ruta | Contenido |
| --- | --- |
| `docs/` | Definición vigente, planes, contratos, auditoría de datos y protocolos. |
| `cronograma/` | Cronograma interno con tareas y estado, y cronograma resumido para presentar. |
| `include/` | Interfaces públicas de simulación, parámetros, RNG, configuración y resultados. |
| `src/core/` | Generador Markov + gamma, Philox, balance hídrico y lógica compartida de escenarios. |
| `src/backends/serial/` | Implementación secuencial de referencia. |
| `src/backends/openmp/` | Paralelización por hilos y reducciones. |
| `src/backends/mpi/` | Reparto estático y maestro–trabajador dinámico. |
| `src/backends/hybrid/` | Integración MPI + OpenMP. |
| `src/backends/cuda/` | Marcadores de la extensión CUDA, en desarrollo. |
| `src/io/` | Lectura de configuración y escritura de resultados CSV con metadatos. |
| `src/stats/` | Intervalo de Wilson e histogramas. |
| `tests/unit/` | Pruebas del RNG, estimadores, V6, V7 y scripts. |
| `tests/integration/` | Equivalencia entre versiones (V1). |
| `tests/concurrency/` | Carreras (V5) y comprobaciones de OpenMP/CUDA. |
| `config/` | Configuración sintética y configuraciones calibradas por estación y régimen. |
| `data/raw/` | Series diarias SENAMHI (`fecha,precipitacion_mm`). |
| `data/processed/` | Auditoría, regímenes, parámetros calibrados, bootstrap y estaciones seleccionadas. |
| `data/metadata/` | Inventario y procedencia de las estaciones. |
| `data/external/` | ICEN mensual (ENFEN) para clasificar regímenes. |
| `scripts/run/` | Tubería de datos, calibración y corridas. |
| `scripts/bench/` | Mediciones (calentamiento + cinco repeticiones) y gráficos. |
| `scripts/deploy/` | Preparación y comprobación del clúster. |
| `docker/` | Imagen `pp-g8` y Compose. |
| `results/bench/`, `results/validacion/`, `results/evidencia/` | CSV de mediciones, logs de validación y evidencia de pruebas (versionados). |
| `results/figures/` | Gráficos de rendimiento y riesgo. |
| `reports/` | Informe IEEE, anexos y presentación final. |

## Criterio de comparación de recursos

Se fija el mismo problema y la misma semilla por comparación. Se ejecuta una corrida de calentamiento y cinco repeticiones por punto; se guardan tiempos, resultados, commit y hardware. OpenMP se compara con 2, 4, 8 y 16 hilos; MPI con 2, 4, 8 y 16 procesos; el híbrido con esos presupuestos de núcleos CPU distribuidos entre procesos e hilos. La comparación CUDA por bloques (X5) se realizará cuando la extensión pase V2 y V8; todavía no hay cifras de GPU. Se reportan tiempo, speedup, eficiencia cuando corresponda y throughput tras comprobar la equivalencia de resultados.
