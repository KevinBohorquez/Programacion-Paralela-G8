# Plan de desarrollo hasta la semana 15

## Alcance

Este plan cubre S09–S15. Cada tarea del cronograma tiene un propietario que produce un artefacto comprobable; la columna «Revisor» de Excel designa a quien revisa el resultado, no a un coautor requerido. Cada integrante puede preparar su artefacto con datos sintéticos y contratos publicados mientras llegan las salidas de otras tareas. Solo la integración final depende de que los contratos se cumplan.

CUDA es una extensión en desarrollo (`docs/decision-cuda.md`): EXT1 (kernel validado con V2/V8) y después EXT2 (GPU como trabajador MPI y ejecutable de tres niveles MPI + OpenMP + CUDA). La extensión es desacoplada: el núcleo CPU y sus experimentos mantienen su alcance aunque la GPU no esté lista.

## Especificación por integrante

Esta sección es la especificación vigente del reparto final y coincide con la hoja `Tareas` de [cronograma-interno.xlsx](../cronograma/cronograma-interno.xlsx), que sigue siendo la fuente principal. Cada tarea se da por terminada cuando su entregable está versionado en `master` y cumple el criterio de aceptación; el revisor de la columna «Revisor» lo comprueba en el pull request. Ninguna tarea tiene el mismo integrante como responsable y revisor.

Las mediciones que se repiten (T14, T30 y T31) se ejecutan en la **PC de referencia** descrita en la [guía de reproducción](guia-reproduccion.md#pc-de-referencia), coordinando el turno con Miguel, y se versionan con el binario del commit vigente.

### David (R1) — integración, MPI, clúster y entregas

| ID | Tarea | Entregable | Criterio de aceptación | Estado |
| --- | --- | --- | --- | --- |
| T19, T20 | MPI E1 estático y E2 dinámico | `src/backends/mpi/` | V1/V3 frente al secuencial y finalización sin bloqueo con 2/4/8/16 procesos. | Completado |
| T24 | Híbrido MPI + OpenMP | `src/backends/hybrid/` | Nivel `MPI_THREAD_FUNNELED` comprobado y V1 igual al secuencial. | Completado |
| T25 | Clúster MPI de 2–3 PC con WSL2 nativo (red *mirrored*, `sshd` en 2222, firewall de Hyper-V, `btl_tcp_if_include`), sin Swarm | `docs/cluster-mpi.md`; logs en `results/bench/` | `mpirun` con *hostfile* ejecuta el híbrido en dos o tres PC distintas; el log muestra el *hostname* de cada rango y el mismo `N` sin escenarios perdidos. | No iniciado |
| T29 | Decisión interna de CUDA | `docs/decision-cuda.md` | Registra la evidencia de E1–E5 que sustenta la decisión, con fecha y enlaces. | En curso |
| T43 | Integración de extensiones | `docs/decision-cuda.md`; `README.md` | Registro de integración de EXT1–EXT3 con CI en verde; `README.md:3` deja de decir «sin kernels». | En curso |
| T44 | Etiqueta y reproducción | etiqueta `entrega-final`; `docs/guia-reproduccion.md` | La etiqueta apunta al commit que T57 dio por verificado. | En curso |
| T49 | Informe final publicado | `reports/` (PDF) | PDF legible generado desde `reports/informe/` y enlazado al commit final. | No iniciado |
| T52 | Paquete final | `docs/manifiesto-entrega.md` | Ruta, hash SHA-256 y versión de cada artefacto. | No iniciado |
| T53 | Exposición | `docs/acta-exposicion-final.md` | Fecha, participantes, demo realizada y preguntas recibidas. | No iniciado |

### Angela (R2) — datos, riesgo y campañas X3, X6 y X8

| ID | Tarea | Entregable | Criterio de aceptación | Estado |
| --- | --- | --- | --- | --- |
| T31 | X3 con cargas 10⁶–10⁹ | `scripts/bench/ejecutar_barridos.py`; `results/bench/x3.csv` | X3 medido de nuevo sin otras cargas en la PC de referencia y versionado con su log. | En curso |
| T34 | Corrida oficial X6 en CPU | `scripts/run/corrida-oficial.py`; `results/cientifico/` | X6 con manifiesto, logs y respaldo. | Completado |
| T35 | Riesgo, IC Wilson y banda bootstrap | `scripts/run/analizar-riesgo.py`; `results/cientifico/tablas*/` | Tablas y curvas versionadas. Pendiente: corregir `results/cientifico/README.md:5-6`, que contradice H5, y validar de nuevo T35. | Completado |
| T42 | Sensibilidad X7 | `scripts/run/sensibilidad.py`; `results/cientifico/x7*.csv` | `U = 30/50/80 mm` y normal/El Niño reproducibles; validar de nuevo tras la corrección de H5. | Completado |
| T56 | Medición X8 de los tres niveles | `scripts/bench/medir_cpu_gpu.py`; `results/bench/x8.csv`; figura en `results/figures/` | Configuraciones (1) MPI solo, (2) MPI + OpenMP, (3) MPI + OpenMP + GPU y (4) las tres en una sola PC; `N` de 10⁷ a 10⁸ con cinco repeticiones; figura de la fracción de bloques por rango y por PC. | No iniciado |

### Ashley (R3) — núcleo, pruebas, imagen Docker y lado CPU de los tres niveles

| ID | Tarea | Entregable | Criterio de aceptación | Estado |
| --- | --- | --- | --- | --- |
| T05 | Imagen Docker base | `docker/Dockerfile` | Imagen `pp-g8` con GCC, Open MPI, Random123 y *hello* híbrido. | Completado |
| T14 | T1 secuencial | `scripts/bench/medir_secuencial.py`; `results/bench/secuencial_t1.csv` | T1 medido de nuevo con el binario actual en la PC de referencia. | En curso |
| T21 | V1/V3/V4 y barrido MPI | `tests/integration/test_mpi.py`; `results/bench/mpi.csv` | Validar de nuevo con el binario actual. | Completado |
| T22 | Compose para MPI E1/E2 | `docker/compose.yaml` | E1 y E2 en contenedores con CSV exportados. | Completado |
| T37 | Documentación de MPI, hilos y afinidad | `docs/arquitectura-paralela.md` | Validar que el diagrama y las rutas siguen el código vigente, incluido el ejecutable de tres niveles. | Completado |
| T48 | Anexo de reproducción | `reports/anexo-reproduccion.md` | Validar que los comandos funcionan con el commit final. | Completado |
| T54 | Lado CPU de `pp_mpi_omp_cuda` | `src/backends/cuda/`; `src/backends/mpi/comun.cpp`; CTest `ext3_*` | El trabajador E2 procesa cada bloque con `ejecutar_openmp` (`--hilos`); `comun.cpp` exige `FUNNELED`; sin CUDA compila con un motor vacío que siempre usa CPU; CTest `ext3_*` comprueba V1 (`k` e `hist512` idénticos al secuencial), que la suma de `n_local` sea `N` y un STOP por trabajador. | No iniciado |

### Lita (R4) — correctitud, barridos y extensión CUDA

| ID | Tarea | Entregable | Criterio de aceptación | Estado |
| --- | --- | --- | --- | --- |
| T23 | Inventario GPU | `docs/inventario-gpu.md` | Comandos y salida resumida por equipo. | Completado |
| T26 | Ejecutor parametrizable de barridos | `scripts/bench/ejecutar_barridos.py` | Un comando por corrida con `N`, procesos, hilos, semilla y metadatos. | Completado |
| T27 | Híbrido 2/4/8/16 núcleos | `scripts/bench/medir_hibrido.py`; `results/bench/hibrido.csv` | Matriz procesos × hilos con cinco tiempos. | Completado |
| T30 | X1 fuerte y X2 débil | `scripts/bench/ejecutar_barridos.py`; `results/bench/x1.csv`, `x2.csv` | X1–X2 medidos de nuevo sin otras cargas en la PC de referencia y versionados con su log. | En curso |
| T32 | MPI E1/E2 en CPU heterogéneas | `scripts/bench/comparar_mpi_heterogeneo.py`; `results/bench/` | Ejecutado en el clúster de T25; registra `t_cómputo` por rango y los mensajes intercambiados. | En curso |
| T38–T41 | Kernel CUDA, V2/V8, barrido y trabajador MPI con GPU | `src/backends/cuda/`; `results/validacion/`; `docs/resultados-cuda.md` | V2/V8 en verde y CSV de bloques × hilos y de CPU frente a CPU + GPU. | Completado |
| T55 | Lado GPU de `pp_mpi_omp_cuda` | `src/backends/cuda/trabajador_mpi.cpp`; `src/backends/cuda/CMakeLists.txt` | El primer rango local de cada PC con GPU (`OMPI_COMM_WORLD_LOCAL_RANK`, `cudaGetDeviceCount`) usa `cudaSetDevice(local % ndev)`; sin GPU vuelve a CPU; arquitecturas `89;120` (RTX 4060 y RTX 5090); V2 con tolerancia 1e-6 en ambas GPU. | No iniciado |
| T58 | Correcciones de `kernel.cu` y evidencia CUDA final | `src/backends/cuda/kernel.cu`; `results/validacion/t38_v2_cuda.txt`, `t39_v8_cuda.txt` | Libera la memoria ya reservada si falla un `cudaMalloc` intermedio (líneas ~196-200); comprueba los errores de `cudaRuntimeGetVersion`/`cudaDriverGetVersion` (~95-96); V2/V8 regenerados sobre el commit final. | No iniciado |

### Miguel (R5) — verificación final de la entrega

Miguel no revisa cada tarea: su única tarea es la verificación final.

| ID | Tarea | Entregable | Criterio de aceptación | Estado |
| --- | --- | --- | --- | --- |
| T57 | Verificación final de la entrega | `docs/verificacion-final.md` | Checklist con evidencia de: CI en verde, V1–V8, reproducción en la PC de referencia, existencia de cada entregable y corrida de respaldo de la demo. Habilita la etiqueta de T44. | No iniciado |

### Rhamses (R6) — documentación, informe y exposición

| ID | Tarea | Entregable | Criterio de aceptación | Estado |
| --- | --- | --- | --- | --- |
| T07 | Cronograma | `cronograma/`; `scripts/validar_cronograma.py` | Mantener el cronograma al día hasta S15; el validador termina en verde. | En curso |
| T28 | Secciones 1–4 del informe | `reports/informe/secciones/01-04*.tex` | Alcance y método vigentes. | Completado |
| T33 | Análisis de rendimiento | `scripts/bench/analizar-rendimiento.py` | Tiempo, speedup, eficiencia, throughput y Karp–Flatt de X1–X4 sin los `TODO-T33` de `07-rendimiento.tex`. | En curso |
| T36 | Resultados científicos | `reports/informe/secciones/08-*.tex`, `09-*.tex` | Incluye H5/κ y la limitación de V6. | En curso |
| T45 | Figuras finales | `scripts/bench/graficar-final.py`; `results/figures/final_*` | Figuras versionadas con datos y unidades correctos. | En curso |
| T46 | Informe IEEE integrado | `reports/informe/` | Sin el pendiente de `07-rendimiento.tex:92`; incluye CUDA, los tres niveles y el clúster con X8. | En curso |
| T47 | Bibliografía vinculada | `reports/informe/referencias.bib` | Cada referencia ligada a una decisión. | Completado |
| T50 | Presentación y guion | diapositivas finales en el repositorio | Una gráfica por conclusión principal y guion con responsable por sección. | No iniciado |

### Tareas del equipo

| ID | Tarea | Entregable | Criterio de aceptación | Estado |
| --- | --- | --- | --- | --- |
| T01 | Definición única | `docs/acta-revision-definicion.md` | Acta firmada por los seis integrantes. | En curso |
| T51 | Demostración en el clúster | `scripts/run/demo-cluster.ps1`; log de ensayo | Trabajo del equipo: cada integrante muestra lo que construyó (David el clúster, Ashley y Lita el ejecutable de tres niveles, Angela los resultados X8, Rhamses el relato). La corrida de respaldo en la PC de referencia se comprueba dentro de T57. | En curso |

### Dependencias del cierre

```text
T54 (Ashley) ─┐
T55 (Lita)  ──┼─> T56 X8 (Angela) ─> T46, T50 (Rhamses) ─> T57 verificación (Miguel) ─> T44 etiqueta (David)
T25 (David) ──┘          └─────────> T51 demo (equipo)
```

T54, T55 y T25 se trabajan en paralelo; T56 necesita las tres. T51 se ensaya después de T56 y su respaldo se comprueba en T57.

## Comparación de 2, 4, 8 y 16 recursos

| Implementación | Configuración solicitada | Precisión de la interpretación |
| --- | --- | --- |
| Secuencial | 1 núcleo | Línea base medida en el mismo tipo de CPU. |
| OpenMP | 2/4/8/16 hilos | Equivalen a núcleos físicos solo si hay suficientes núcleos y afinidad estable. |
| MPI E1 y E2 | 2/4/8/16 procesos | Registrar distribución por nodo y núcleos asignados a cada proceso. |
| MPI + OpenMP | 2/4/8/16 núcleos CPU totales | Elegir pares `procesos × hilos` cuyo producto sea el presupuesto; comparar más de una factorización cuando sea posible. |
| CUDA (en desarrollo) | 2/4/8/16 bloques y 128/256/512 hilos por bloque | Un bloque no es un núcleo físico GPU. Registrar SM y ocupación observada; no atribuir a «16 núcleos CUDA» una configuración de 16 bloques. |
| CPU + GPU (en desarrollo) | CPU sola frente a CPU + GPU | Mantener carga fija y declarar por separado recursos CPU y GPU. |

Una configuración que exceda los núcleos físicos disponibles se etiqueta como sobresuscrita y se analiza aparte. Todos los puntos comparables usan igual `N`, parámetros y semilla, una corrida de calentamiento y cinco medidas. Antes de calcular speedup se comprueba equivalencia de resultados. Los CSV guardan commit, hardware, afinidad, procesos, hilos, bloques, tiempos y conteos.

## Entregables por semana

| Semana | Entregable | Evidencia exigida |
| --- | --- | --- |
| S09 | E4 MPI | E1/E2, V1/V3/V4 y matriz de procesos 2/4/8/16. |
| S10 | E5 híbrido | Clúster MPI multinodo, matriz procesos × hilos y decisión de extensiones. |
| S11 | E6 rendimiento | X1–X4 CPU, cinco repeticiones y análisis por recurso. |
| S12 | E7 resultados | X6 y curvas con incertidumbre; CUDA cuando pase V2/V8. |
| S13 | E8 sensibilidad y código | X7, etiqueta final y guía de reproducción. |
| S14 | E9 informe | Informe IEEE y anexo de reproducción. |
| S15 | E10 exposición | Presentación, demostración, verificación final y paquete final. |
