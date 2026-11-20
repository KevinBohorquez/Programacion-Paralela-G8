# Plan de desarrollo hasta la semana 15

## Alcance

Este plan cubre S09–S15. Cada tarea del cronograma tiene un propietario que produce un artefacto comprobable; la columna «Revisor» de Excel designa a quien revisa el resultado, no a un coautor requerido. Cada integrante puede preparar su artefacto con datos sintéticos y contratos publicados mientras llegan las salidas de otras tareas. Solo la integración final depende de que los contratos se cumplan.

CUDA es una extensión en desarrollo (`docs/decision-cuda.md`): EXT1 (kernel validado con V2/V8) y después EXT2 (GPU como trabajador MPI y ejecutable de tres niveles MPI + OpenMP + CUDA). La extensión es desacoplada: el núcleo CPU y sus experimentos mantienen su alcance aunque la GPU no esté lista.

## Especificación por integrante

La fuente es la hoja `Tareas` de [cronograma-interno.xlsx](../cronograma/cronograma-interno.xlsx). GitHub no muestra el contenido de un `.xlsx`, por eso esta sección lo reproduce completo: para cada tarea pendiente copia el criterio de aceptación (columna I) y la ruta, el formato, las entradas, los pasos y la evidencia (columnas V–Z). Si el Excel y este documento difieren, se corrige el que quedó atrás en el mismo pull request. Estados revisados el 20/11.

Reglas comunes:

- Una tarea se da por terminada cuando su entregable está versionado en `master` y cumple el criterio de aceptación; el revisor lo comprueba en el pull request.
- Ninguna tarea tiene el mismo integrante como responsable y revisor.
- La fecha límite es el corte interno del Excel (columna H): martes 23:59 de la última semana de la tarea. «Vencida» indica que esa fecha ya pasó y la tarea sigue pendiente.
- Las mediciones que se repiten (T59, T60 y T61) se ejecutan en la **PC de referencia** descrita en la [guía de reproducción](guia-reproduccion.md#pc-de-referencia), con el host en reposo y coordinando el turno con Miguel, y se versionan con el commit del binario medido.

Cada integrante tiene primero una tabla con todas sus tareas y después una ficha por tarea pendiente («No iniciado» o «En curso») con qué hacer, qué entregar, entradas y dependencias, evidencia, criterio de aceptación, revisor y fecha límite.

| Integrante | Tareas | Pendientes | Tareas con ficha |
| --- | --- | --- | --- |
| [David (R1)](#david-r1--integración-mpi-clúster-y-entregas) | 12 | 7 | T25, T29, T43, T44, T49, T52, T53 |
| [Angela (R2)](#angela-r2--datos-riesgo-y-campañas-x3-x6-y-x8) | 10 | 3 | T34, T56, T61 |
| [Ashley (R3)](#ashley-r3--núcleo-pruebas-imagen-docker-t1-y-lado-cpu-de-los-tres-niveles) | 12 | 3 | T22, T54, T59 |
| [Lita (R4)](#lita-r4--correctitud-barridos-x1x2-y-extensión-cuda) | 15 | 4 | T32, T55, T58, T60 |
| [Miguel (R5)](#miguel-r5--verificación-final-de-la-entrega) | 1 | 1 | T57 |
| [Rhamses (R6)](#rhamses-r6--cronograma-documentación-informe-y-exposición) | 10 | 7 | T01, T07, T33, T36, T45, T46, T50 |
| [Equipo](#tareas-del-equipo) | 1 | 1 | T51 |

### David (R1) — integración, MPI, clúster y entregas

| ID | Tarea | Estado | Revisor | Fecha límite |
| --- | --- | --- | --- | --- |
| T02 | Especificar contrato de CLI, configuración y CSV de resultados | Completado | Rhamses (R6) | 29/09 |
| T03 | Preparar repositorio Git local, estructura y reglas de contribución | Completado | Ashley (R3) | 29/09 |
| T19 | Implementar MPI E1 estático con MPI_Reduce | Completado | Ashley (R3) | 20/10 |
| T20 | Implementar MPI E2 dinámico con REQ/WORK/STOP | Completado | Lita (R4) | 20/10 |
| T24 | Integrar MPI + OpenMP con `MPI_THREAD_FUNNELED` y afinidad | Completado | Ashley (R3) | 27/10 |
| T25 | Clúster MPI de 2–3 PC con WSL2 nativo (red mirrored, `sshd` en 2222, firewall Hyper-V, `btl_tcp_if_include`), sin Swarm | No iniciado | Ashley (R3) | 24/11 |
| T29 | Registrar decisión interna de CUDA tras revisar E1–E5 | En curso | Lita (R4) | 27/10 (vencida) |
| T43 | Integrar solo extensiones que superen sus pruebas | En curso | Lita (R4) | 17/11 (vencida) |
| T44 | Etiquetar código final y documentar reproducción | En curso | Ashley (R3) | 17/11 (vencida) |
| T49 | Publicar informe técnico final en `reports/` | No iniciado | Rhamses (R6) | 24/11 |
| T52 | Preparar paquete final de informe, repositorio y presentación | No iniciado | Rhamses (R6) | 01/12 |
| T53 | Exponer el proyecto y registrar preguntas y respuestas | No iniciado | Rhamses (R6) | 01/12 |

#### T25 — Clúster MPI de 2–3 PC con WSL2 nativo (red mirrored, sshd en 2222, firewall Hyper-V, btl_tcp_if_include), sin Swarm

Estado: **No iniciado** (0 %) · semanas S10–S14

**Qué hacer:**

1. Activar `networkingMode=mirrored` en `.wslconfig`.
2. Levantar `sshd` en el puerto 2222 y abrir la regla del firewall de Hyper-V.
3. Copiar claves.
4. Fijar `btl_tcp_if_include` a la interfaz de la LAN.
5. Ejecutar `hostname` y el híbrido con igual N y semilla.
6. Recoger logs y verificar la suma de escenarios.

- **Qué entregar:** `docs/cluster-mpi.md`; `results/bench/cluster.csv`; log de `mpirun` en `results/bench/`. Formato: Guía MD de configuración; log de `mpirun` multinodo y CSV de ejecución.
- **Entradas y dependencias:** 2–3 PC con Windows 11 + WSL2 en red mirrored; Open MPI de la imagen T05; híbrido T24; ssh entre nodos en el puerto 2222.
- **Evidencia:** Log con dos o tres hostnames distintos, comando `mpirun` y `results/bench/cluster.csv` sin escenarios perdidos.
- **Criterio de aceptación:** `mpirun` con `hostfile` de 2–3 PC distintas ejecuta el híbrido; log con el `hostname` de cada rango y el mismo N completado sin pérdida de escenarios.
- **Revisor:** Ashley (R3)
- **Fecha límite:** 24/11 (martes 23:59 de S14)

#### T29 — Registrar decisión interna de CUDA tras revisar E1–E5

Estado: **En curso** (50 %) · semana S10

**Qué hacer:**

1. Comparar GPU disponible, tiempo restante, coste de implementación y pruebas.
2. Decidir activar o no EXT1 y EXT2.
3. Registrar justificación y responsables sin solicitar ayuda externa.

- **Qué entregar:** `docs/decision-cuda.md`. Formato: Acta de decisión CUDA en MD con criterio go/no-go y evidencias.
- **Entradas y dependencias:** Inventario T23; resultados E1–E5; criterios de tiempo y disponibilidad CUDA.
- **Evidencia:** `docs/decision-cuda.md` con fecha, evidencia, go/no-go y tareas T38–T41 activadas o descartadas.
- **Criterio de aceptación:** `docs/decision-cuda.md` indica go/no-go, la evidencia de E1–E5 que lo sustenta, la GPU disponible y las tareas EXT activadas, con fecha y enlaces.
- **Revisor:** Lita (R4)
- **Fecha límite:** 27/10 (martes 23:59 de S10), vencida

#### T43 — Integrar solo extensiones que superen sus pruebas

Estado: **En curso** (50 %) · semana S13

**Qué hacer:**

1. Revisar V2/V8 y V3.
2. Integrar solo las extensiones que pasan sus pruebas.
3. Resolver conflictos de CMake e interfaz.
4. Ejecutar compilación y CTest en master.
5. Registrar la decisión final en `docs/decision-cuda.md` y corregir `README.md:3`.

- **Qué entregar:** `docs/decision-cuda.md`; `README.md`. Formato: Pull request de integración y log CI; no duplicar archivos de otros módulos.
- **Entradas y dependencias:** Decisión T29; pruebas T39/T41; tres niveles T54–T55; correcciones T58.
- **Evidencia:** PR de integración, enlace a CI verde, `docs/decision-cuda.md` con el estado de EXT1–EXT3 y `README.md:3` actualizado.
- **Criterio de aceptación:** Registro de integración de EXT1–EXT3 con V2/V8 en `docs/decision-cuda.md`; master pasa CI; `README.md:3` deja de afirmar que no hay kernels implementados.
- **Revisor:** Lita (R4)
- **Fecha límite:** 17/11 (martes 23:59 de S13), vencida

#### T44 — Etiquetar código final y documentar reproducción

Estado: **En curso** (50 %) · semana S13

**Qué hacer:**

1. Verificar un clon limpio.
2. Documentar dependencias y comandos para compilar, validar y repetir X1–X7 aplicables.
3. Etiquetar como `entrega-final` el commit que T57 dio por verificado.

- **Qué entregar:** etiqueta `entrega-final`; `docs/guia-reproduccion.md`. Formato: Guía de reproducción y README actualizados; etiqueta Git `entrega-final`.
- **Entradas y dependencias:** master tras T43 y la verificación T57; scripts, datos de ejemplo y cronograma de experimentos.
- **Evidencia:** `docs/guia-reproduccion.md` con comandos probados y etiqueta `entrega-final` apuntando al commit verificado por T57.
- **Criterio de aceptación:** Etiqueta `entrega-final` en el commit que T57 dio por verificado; `docs/guia-reproduccion.md` y README con comandos para compilar, probar y repetir X1–X7 aplicables.
- **Revisor:** Ashley (R3)
- **Fecha límite:** 17/11 (martes 23:59 de S13), vencida

#### T49 — Publicar informe técnico final en reports/

Estado: **No iniciado** (0 %) · semana S14

**Qué hacer:**

1. Comprobar portada, páginas, figuras, referencias y anexo.
2. Colocar PDF definitivo en `reports/`.
3. Registrar commit y confirmar apertura del archivo.

- **Qué entregar:** `reports/informe-final.pdf` (generado desde `reports/informe/`). Formato: PDF final del informe en `reports/` y enlace al commit.
- **Entradas y dependencias:** PDF T46; anexo T48; referencias T47; fecha de entrega.
- **Evidencia:** `reports/informe-final.pdf` legible y enlace al commit de master antes del corte.
- **Criterio de aceptación:** PDF legible, con referencias y anexos, registrado en master antes del corte.
- **Revisor:** Rhamses (R6)
- **Fecha límite:** 24/11 (martes 23:59 de S14)

#### T52 — Preparar paquete final de informe, repositorio y presentación

Estado: **No iniciado** (0 %) · semana S15

**Qué hacer:**

1. Enumerar archivos finales.
2. Calcular SHA-256.
3. Verificar rutas y enlaces.
4. Registrar commit/tag y comprobar que paquete se abre en equipo distinto.

- **Qué entregar:** `docs/manifiesto-entrega.md`. Formato: Manifiesto MD con rutas, hashes, commit/tag y enlaces al paquete final.
- **Entradas y dependencias:** Tag T44; PDF T49; diapositivas T50; demo T51.
- **Evidencia:** `docs/manifiesto-entrega.md` con ruta, hash, versión y enlace de cada artefacto.
- **Criterio de aceptación:** Índice de archivos con hashes y enlaces al commit/tag `entrega-final`.
- **Revisor:** Rhamses (R6)
- **Fecha límite:** 01/12 (martes 23:59 de S15)

#### T53 — Exponer el proyecto y registrar preguntas y respuestas

Estado: **No iniciado** (0 %) · semana S15

**Qué hacer:**

1. Registrar quién presentó cada sección, si demo corrió y con qué configuración.
2. Anotar preguntas y respuestas textuales breves.
3. Enlazar versión mostrada.

- **Qué entregar:** `docs/acta-exposicion-final.md`. Formato: Acta MD de exposición: fecha, participantes, demo y preguntas.
- **Entradas y dependencias:** Guion T50; demo T51; asistentes y fecha de exposición.
- **Evidencia:** `docs/acta-exposicion-final.md` con fecha, seis participantes, demo, preguntas y commit/tag.
- **Criterio de aceptación:** Acta interna con fecha, participantes, demostración realizada y preguntas recibidas.
- **Revisor:** Rhamses (R6)
- **Fecha límite:** 01/12 (martes 23:59 de S15)

### Angela (R2) — datos, riesgo y campañas X3, X6 y X8

| ID | Tarea | Estado | Revisor | Fecha límite |
| --- | --- | --- | --- | --- |
| T06 | Inventariar 3–5 series diarias SENAMHI candidatas con ≥ 20 años | Completado | Rhamses (R6) | 29/09 |
| T08 | Auditar faltantes, atípicos y años incompletos de cada serie | Completado | Rhamses (R6) | 06/10 |
| T09 | Clasificar años normal y El Niño con fuente ENFEN | Completado | Rhamses (R6) | 06/10 |
| T10 | Calibrar p01, p11, alfa y theta por estación/régimen y 100 bootstrap | Completado | Ashley (R3) | 06/10 |
| T31 | Ejecutar X2 débil y X3 con cargas 10⁶/10⁷/10⁸/10⁹ | Completado | David (R1) | 03/11 |
| T34 | Ejecutar X6 CPU con 1,3×10¹⁰ escenarios y respaldar resultados | En curso | Lita (R4) | 10/11 (vencida) |
| T35 | Calcular riesgo, IC Wilson, banda bootstrap y curva riesgo–capacidad | Completado | Rhamses (R6) | 10/11 |
| T42 | Ejecutar X7 para U=30/50/80 mm y normal/El Niño | Completado | Rhamses (R6) | 17/11 |
| T56 | Medir X8 de los tres niveles: MPI, MPI+OpenMP, MPI+OpenMP+GPU y las tres en una sola PC | No iniciado | Rhamses (R6) | 01/12 |
| T61 | Medir de nuevo X3 con cargas 10⁶/10⁷/10⁸/10⁹ y 8 recursos en la PC de referencia | No iniciado | Lita (R4) | 01/12 |

- **T31 (completada):** X2 y X3 medidos el 26/10 en la misma sesión (X3 solo con 10⁶, 5×10⁶ y 2×10⁷); cifras provisionales; la nueva medición es T60 (X2) y T61 (X3).

#### T34 — Ejecutar X6 CPU con 1,3×10¹⁰ escenarios y respaldar resultados

Estado: **En curso** (80 %) · semana S12

**Qué hacer:**

1. Particionar en lotes con rangos no solapados y registrar semilla, commit y configuración (hecho en `x6_manifiesto.json` y `bootstrap_manifiesto.json`).
2. Completar los escenarios hasta 1,3×10¹⁰ o justificar el total y ajustar el criterio al plan oficial.
3. Calcular el SHA-256 de cada CSV y log y añadirlo al manifiesto.
4. Copiar `results/cientifico/` a dos equipos y registrar ambas ubicaciones.

- **Qué entregar:** `scripts/run/corrida-oficial.py`; `results/cientifico/x6.csv`; `results/cientifico/x6_manifiesto.json`. Formato: CSV X6 con 1,3×10¹⁰ escenarios, logs y respaldo íntegro.
- **Entradas y dependencias:** Parámetros T10; backend CPU validado; `scripts/run/corrida-oficial.py`; espacio de almacenamiento.
- **Evidencia:** `results/cientifico/x6.csv`, manifiesto de lotes y logs con N total, SHA-256 y dos ubicaciones de respaldo. Pendiente: el manifiesto suma 170 × 10⁷ = 1,7×10⁹ (X6) y 8000 × 10⁶ = 8×10⁹ (bootstrap), unos 9,7×10⁹ escenarios frente a 1,3×10¹⁰ (igual en los manifiestos `_h5`); no hay SHA-256 ni evidencia de respaldo en dos equipos; la ruta `results/official/x6.csv` del plan no existe.
- **Criterio de aceptación:** CSV contabiliza N por configuración y total; logs y copia íntegra en dos equipos.
- **Revisor:** Lita (R4)
- **Fecha límite:** 10/11 (martes 23:59 de S12), vencida

#### T56 — Medir X8 de los tres niveles: MPI, MPI+OpenMP, MPI+OpenMP+GPU y las tres en una sola PC

Estado: **No iniciado** (0 %) · semanas S14–S15

**Qué hacer:**

1. Extender `medir_cpu_gpu.py` con (1) MPI solo, (2) MPI+OpenMP, (3) MPI+OpenMP+GPU y (4) las tres en una sola PC.
2. Barrer N de 10⁷ a 10⁸ con igual semilla, calentamiento y cinco repeticiones.
3. Registrar los bloques procesados por rango y por PC.

- **Qué entregar:** `scripts/bench/medir_cpu_gpu.py`. Formato: Python; `results/bench/x8.csv` y figura SVG/PNG de fracción de bloques.
- **Entradas y dependencias:** Clúster T25; ejecutable de tres niveles T54–T55; ejecutor de barridos T26; T1 de T59 como referencia secuencial.
- **Evidencia:** `results/bench/x8.csv` y `results/figures/x8_fraccion_bloques.svg/.png` con commit, hardware y cinco tiempos por punto.
- **Criterio de aceptación:** CSV con las cuatro configuraciones, N de 10⁷ a 10⁸ y cinco repeticiones; figura de fracción de bloques por rango y por PC.
- **Revisor:** Rhamses (R6)
- **Fecha límite:** 01/12 (martes 23:59 de S15)

#### T61 — Medir de nuevo X3 con cargas 10⁶/10⁷/10⁸/10⁹ y 8 recursos en la PC de referencia

Estado: **No iniciado** (0 %) · semanas S14–S15

**Qué hacer:**

1. Esperar el T1 de T59 y coordinar el turno de la PC de referencia con el host en reposo.
2. Compilar el commit vigente de master en Release (`-DPP_BUILD_MPI=ON`) en la imagen `pp-g8`.
3. Estimar la duración con `--dry-run`.
4. Ejecutar `ejecutar_barridos.py --experimento x3 --backend serial,openmp,mpi_estatico,mpi_dinamico,hibrido --recursos 8 --cargas 1e6,1e7,1e8,1e9`.
5. Si la corrida serial con 10⁹ no cabe, excluirla y declarar la excepción en las notas del CSV y en el informe.
6. Comprobar `equivalente = 1`.
7. Versionar CSV y log con el commit del binario.

- **Qué entregar:** `scripts/bench/ejecutar_barridos.py`; `results/bench/x3.csv`; `results/bench/x3.log`. Formato: CSV X3 con N, backend, recursos, cinco tiempos, k, equivalencia, hardware y commit; log de la corrida.
- **Entradas y dependencias:** T1 de T59; ejecutor de barridos T26; backends validados (V1); PC de referencia (`docs/guia-reproduccion.md#pc-de-referencia`) con turno coordinado.
- **Evidencia:** `results/bench/x3.csv` y `x3.log` con commit del binario, hardware, host en reposo, cinco tiempos por punto, `equivalente = 1` y cada excepción declarada.
- **Criterio de aceptación:** `results/bench/x3.csv` con N = 10⁶, 10⁷, 10⁸ y 10⁹ y 8 recursos por backend, calentamiento y cinco tiempos por punto, host en reposo y binario actual; toda exclusión (p. ej. serial con 10⁹) declarada en las notas del CSV y en el informe; log versionado.
- **Revisor:** Lita (R4)
- **Fecha límite:** 01/12 (martes 23:59 de S15)

### Ashley (R3) — núcleo, pruebas, imagen Docker, T1 y lado CPU de los tres niveles

| ID | Tarea | Estado | Revisor | Fecha límite |
| --- | --- | --- | --- | --- |
| T04 | Preparar CMake y CI de compilación C/C++ | Completado | David (R1) | 29/09 |
| T05 | Preparar Docker base con GCC, Open MPI, Random123 y hello híbrido | Completado | David (R1) | 29/09 |
| T11 | Implementar escenario secuencial con Philox, gamma y balance Lindley | Completado | David (R1) | 06/10 |
| T12 | Implementar Wilson, histograma de 512 clases y CSV de salida | Completado | Angela (R2) | 06/10 |
| T14 | Medir T1 secuencial y actualizar escalones de carga | Completado | Lita (R4) | 06/10 |
| T15 | Implementar backend OpenMP con reducción de k, n e histograma | Completado | Lita (R4) | 13/10 |
| T21 | Ejecutar V1/V3/V4 y barrido MPI E1/E2 con 2/4/8/16 procesos | Completado | David (R1) | 20/10 |
| T22 | Preparar Compose para MPI E1/E2 y exportación de resultados | En curso | David (R1) | 20/10 (vencida) |
| T37 | Documentar procesos MPI, hilos OpenMP, reducción y afinidad | Completado | David (R1) | 10/11 |
| T48 | Preparar anexo de reproducibilidad y esquemas de datos | Completado | David (R1) | 24/11 |
| T54 | Lado CPU del ejecutable de tres niveles `pp_mpi_omp_cuda`: trabajador E2 con OpenMP por bloque | No iniciado | Lita (R4) | 24/11 |
| T59 | Medir de nuevo T1 secuencial con el binario actual de master en la PC de referencia | No iniciado | David (R1) | 24/11 |

- **T14 (completada):** T1 medido y versionado el 15/10 (`results/bench/secuencial_t1.csv`, `results/evidencia/t14_medir_secuencial.log`); la nueva medición con el binario actual es T59.

#### T22 — Preparar Compose para MPI E1/E2 y exportación de resultados

Estado: **En curso** (80 %) · semana S09

**Qué hacer:**

1. Definir servicios y red.
2. Montar carpeta de salida.
3. Documentar un comando para lanzar E1 y E2.
4. Comprobar salida CSV y código de retorno.
5. Guardar logs de contenedor.
6. Copiar los logs y CSV de `results/compose/` (excluido por `.gitignore` desde 3dcafa3) a `results/evidencia/` y versionarlos.

- **Qué entregar:** `docker/compose.yaml`. Formato: YAML Compose; logs y CSV de E1/E2 exportados desde contenedores.
- **Entradas y dependencias:** Imagen T05; ejecutables E1/E2; `docker/compose.yaml`.
- **Evidencia:** `docker/compose.yaml`, comando de ejecución, logs E1/E2 y CSV exportados en `results/evidencia/`. Pendiente: los logs y CSV no están versionados porque `results/compose/` está en `.gitignore` (3dcafa3).
- **Criterio de aceptación:** Un comando levanta contenedores, corre ambos esquemas y guarda CSV y logs; los logs y CSV de E1/E2 quedan versionados en `results/evidencia/`.
- **Revisor:** David (R1)
- **Fecha límite:** 20/10 (martes 23:59 de S09), vencida

#### T54 — Lado CPU del ejecutable de tres niveles pp_mpi_omp_cuda: trabajador E2 con OpenMP por bloque

Estado: **No iniciado** (0 %) · semana S14

**Qué hacer:**

1. Procesar cada bloque WORK con `ejecutar_openmp` y `--hilos`.
2. Exigir `MPI_THREAD_FUNNELED` en `comun.cpp`.
3. Compilar sin CUDA con un motor vacío que siempre usa CPU.
4. Añadir CTest `ext3_*` que comparen k e `hist512` con el secuencial, sumen `n_local` y cuenten un `STOP` por trabajador.

- **Qué entregar:** `src/backends/cuda/` (`pp_mpi_omp_cuda`); `src/backends/mpi/comun.cpp`; `CMakeLists.txt`. Formato: C++/MPI/OpenMP; CTest `ext3_*` y log de V1 frente al secuencial.
- **Entradas y dependencias:** E2 T20; híbrido FUNNELED T24; `ejecutar_openmp` T15; trabajador GPU T41.
- **Evidencia:** Salida de `ctest -R ext3_` en verde y log V1 con commit, N, procesos e hilos.
- **Criterio de aceptación:** CTest `ext3_*` en verde: V1 con k e `hist512` idénticos al secuencial, suma de `n_local` = N y un `STOP` por trabajador; compila y corre sin CUDA.
- **Revisor:** Lita (R4)
- **Fecha límite:** 24/11 (martes 23:59 de S14)

#### T59 — Medir de nuevo T1 secuencial con el binario actual de master en la PC de referencia

Estado: **No iniciado** (0 %) · semana S14

**Qué hacer:**

1. Coordinar el turno de la PC de referencia y cerrar toda otra carga (contenedores, compilaciones, navegador).
2. Compilar el commit vigente de master en Release dentro de la imagen `pp-g8`.
3. Ejecutar `scripts/bench/medir_secuencial.py --n 20000000 --repeticiones 5` (un calentamiento y cinco repeticiones con la misma semilla).
4. Comprobar que k es idéntico en las seis corridas.
5. Guardar la salida de consola en `results/evidencia/t59_medir_secuencial.log` con comando, fecha, commit, imagen y host.
6. Versionar el CSV y el log.
7. Avisar a T60, T61, T33 y T46 del nuevo T1.

- **Qué entregar:** `scripts/bench/medir_secuencial.py`; `results/bench/secuencial_t1.csv`; `results/evidencia/t59_medir_secuencial.log`. Formato: CSV T1 con calentamiento, cinco tiempos y metadatos de CPU; log con comando, fecha, commit e imagen.
- **Entradas y dependencias:** Binario serial Release del commit vigente de master; PC de referencia (`docs/guia-reproduccion.md#pc-de-referencia`) con turno coordinado; N = 2×10⁷ y semilla de T14; `scripts/bench/medir_secuencial.py`.
- **Evidencia:** `results/bench/secuencial_t1.csv` y `results/evidencia/t59_medir_secuencial.log` con comando, fecha, commit del binario, imagen, host en reposo, cinco tiempos y k idéntico.
- **Criterio de aceptación:** `results/bench/secuencial_t1.csv` con calentamiento, cinco tiempos, media, desviación, CPU y commit del binario actual de master, medido con el host en reposo; log versionado; la referencia T1 de X1–X3 y del informe queda actualizada.
- **Revisor:** David (R1)
- **Fecha límite:** 24/11 (martes 23:59 de S14)

### Lita (R4) — correctitud, barridos X1–X2 y extensión CUDA

| ID | Tarea | Estado | Revisor | Fecha límite |
| --- | --- | --- | --- | --- |
| T13 | Crear y ejecutar pruebas V6 estadísticas y V7 analítica | Completado | Ashley (R3) | 06/10 |
| T16 | Medir OpenMP con 2/4/8/16 hilos, afinidad y schedules | Completado | Ashley (R3) | 13/10 |
| T17 | Ejecutar V1 y V5 para OpenMP | Completado | Ashley (R3) | 13/10 |
| T23 | Inventariar GPU y decidir disponibilidad para EXT1/EXT2 | Completado | David (R1) | 20/10 |
| T26 | Automatizar barridos con N, procesos, hilos, semilla y hardware parametrizables | Completado | Rhamses (R6) | 27/10 |
| T27 | Medir híbrido con 2/4/8/16 núcleos CPU totales | Completado | David (R1) | 27/10 |
| T30 | Ejecutar X1 fuerte con 2/4/8/16 recursos por backend CPU | Completado | Rhamses (R6) | 03/11 |
| T32 | Comparar MPI E1/E2 en CPU heterogéneas con 2/4/8/16 procesos | En curso | Ashley (R3) | 03/11 (vencida) |
| T38 | Implementar kernel CUDA con Philox e índice global | Completado | Ashley (R3) | 03/11 |
| T39 | Implementar reducción CUDA y ejecutar V2/V8 | Completado | Ashley (R3) | 10/11 |
| T40 | Medir CUDA con 2/4/8/16 bloques y 128/256/512 hilos por bloque | Completado | Rhamses (R6) | 10/11 |
| T41 | Integrar GPU como trabajador MPI y comparar CPU frente a CPU+GPU | Completado | David (R1) | 17/11 |
| T55 | Lado GPU de `pp_mpi_omp_cuda`: GPU para el primer rango local de cada PC con GPU y vuelta a CPU sin GPU | No iniciado | Ashley (R3) | 24/11 |
| T58 | Corregir `kernel.cu` (liberación ante fallo de `cudaMalloc` y errores de versión) y regenerar la evidencia CUDA final | No iniciado | Ashley (R3) | 24/11 |
| T60 | Medir de nuevo X1 fuerte y X2 débil con el binario actual en la PC de referencia | No iniciado | Ashley (R3) | 01/12 |

- **T30 (completada):** X1 medido el 26/10 (5 backends, 1–16 recursos, 5 repeticiones, N = 2×10⁷); la sesión se declaró no válida como referencia por carga ajena ([guion de la semana 11](guion-exposicion-semana-11.md)) y la nueva medición es T60.

#### T32 — Comparar MPI E1/E2 en CPU heterogéneas con 2/4/8/16 procesos

Estado: **En curso** (50 %) · semana S11

**Qué hacer:**

1. Fijar N/semilla.
2. Medir 2/4/8/16 procesos en distribución de nodos documentada.
3. Registrar escenarios por rank, tiempo de cómputo/espera y mensajes.
4. Comparar balance E1/E2.

- **Qué entregar:** `scripts/bench/comparar_mpi_heterogeneo.py`; `results/bench/mpi_heterogeneo.csv`. Formato: CSV E1/E2 en nodos heterogéneos: distribución, balance y tiempos.
- **Entradas y dependencias:** E1 T19, E2 T20; nodos heterogéneos T25; medir_mpi T21.
- **Evidencia:** `results/bench/mpi_heterogeneo.csv` y resumen de desbalance y coste de comunicación con mapa rank–nodo.
- **Criterio de aceptación:** Ejecutado en el clúster de T25 con igual N y asignación de procesos; CSV con tiempo de cómputo por rango, balance y coste de los mensajes intercambiados.
- **Revisor:** Ashley (R3)
- **Fecha límite:** 03/11 (martes 23:59 de S11), vencida

#### T55 — Lado GPU de pp_mpi_omp_cuda: GPU para el primer rango local de cada PC con GPU y vuelta a CPU sin GPU

Estado: **No iniciado** (0 %) · semana S14

**Qué hacer:**

1. Leer `OMPI_COMM_WORLD_LOCAL_RANK`.
2. Con `cudaGetDeviceCount` usar `cudaSetDevice(local % ndev)` solo en el primer rango local de cada PC con GPU.
3. Volver a CPU si no hay dispositivo.
4. Fijar las arquitecturas CUDA 89;120.
5. Ejecutar V2 en ambas GPU.

- **Qué entregar:** `src/backends/cuda/trabajador_mpi.cpp`; `src/backends/cuda/CMakeLists.txt`. Formato: C++/MPI/CUDA; log V2 por GPU y asignación rango → dispositivo.
- **Entradas y dependencias:** Kernel T38–T39; lado CPU T54; GPU inventariadas en T23 (RTX 4060 y RTX 5090).
- **Evidencia:** `results/validacion/t55_v2_tres_niveles.txt` con V2 ≤ 1e-6 en RTX 4060 y RTX 5090 y el dispositivo asignado a cada rango.
- **Criterio de aceptación:** V2 con tolerancia 1e-6 frente a CPU en RTX 4060 y RTX 5090; los rangos sin GPU usan CPU; compila para las arquitecturas 89;120.
- **Revisor:** Ashley (R3)
- **Fecha límite:** 24/11 (martes 23:59 de S14)

#### T58 — Corregir kernel.cu (liberación ante fallo de cudaMalloc y errores de versión) y regenerar la evidencia CUDA final

Estado: **No iniciado** (0 %) · semana S14

**Qué hacer:**

1. Liberar los buffers ya reservados si falla un `cudaMalloc` intermedio (líneas ~196-200).
2. Comprobar el código de retorno de `cudaRuntimeGetVersion` y `cudaDriverGetVersion` (~95-96).
3. Recompilar y regenerar V2 y V8 sobre el commit final.

- **Qué entregar:** `src/backends/cuda/kernel.cu`; `results/validacion/t38_v2_cuda.txt`; `results/validacion/t39_v8_cuda.txt`. Formato: CUDA C++; logs V2/V8 con el commit final.
- **Entradas y dependencias:** Kernel T38; reducción T39; observaciones de la revisión de CUDA.
- **Evidencia:** `t38_v2_cuda.txt` y `t39_v8_cuda.txt` con el commit final, la GPU usada y el resultado de V2/V8.
- **Criterio de aceptación:** `kernel.cu` libera la memoria ya reservada si falla un `cudaMalloc` intermedio y comprueba `cudaRuntimeGetVersion/cudaDriverGetVersion`; V2 y V8 regenerados sobre el commit final.
- **Revisor:** Ashley (R3)
- **Fecha límite:** 24/11 (martes 23:59 de S14)

#### T60 — Medir de nuevo X1 fuerte y X2 débil con el binario actual en la PC de referencia

Estado: **No iniciado** (0 %) · semanas S14–S15

**Qué hacer:**

1. Esperar el T1 de T59 y coordinar el turno de la PC de referencia con el host en reposo.
2. Compilar el commit vigente de master en Release (`-DPP_BUILD_MPI=ON`) en la imagen `pp-g8`.
3. Fijar N de X1: 2×10⁸ si la estimación de `--dry-run` cabe en el turno, si no 2×10⁷ declarado como excepción.
4. Ejecutar `ejecutar_barridos.py --experimento x1 --backend serial,openmp,mpi_estatico,mpi_dinamico,hibrido --n <N>`.
5. Ejecutar `--experimento x2` con los mismos backends y N por recurso 2,5×10⁶.
6. Comprobar `equivalente = 1` en todas las filas antes de calcular speedup.
7. Versionar CSV y logs con el commit del binario y registrar el N elegido en el informe.

- **Qué entregar:** `scripts/bench/ejecutar_barridos.py`; `results/bench/x1.csv`; `results/bench/x1.log`; `results/bench/x2.csv`; `results/bench/x2.log`. Formato: CSV X1 (N fijo) y X2 (N por recurso) con backend, procesos, hilos, cinco tiempos, k, equivalencia, hardware y commit; log por experimento.
- **Entradas y dependencias:** T1 de T59; ejecutor de barridos T26; backends validados (V1); PC de referencia (`docs/guia-reproduccion.md#pc-de-referencia`) con turno coordinado.
- **Evidencia:** `results/bench/x1.csv`, `x1.log`, `x2.csv` y `x2.log` con commit del binario, hardware, host en reposo, cinco tiempos por punto, `equivalente = 1` y el N elegido.
- **Criterio de aceptación:** `results/bench/x1.csv` y `x2.csv` con serial, OpenMP, MPI E1, MPI E2 e híbrido para 1/2/4/8/16 recursos, calentamiento y cinco tiempos por punto, host en reposo y binario actual; V1 equivalente en todas las filas antes de calcular speedup; N de X1 declarado en el CSV y en el informe; logs versionados.
- **Revisor:** Ashley (R3)
- **Fecha límite:** 01/12 (martes 23:59 de S15)

### Miguel (R5) — verificación final de la entrega

Miguel no revisa ninguna tarea: su única tarea es la verificación final, que comprueba la evidencia de las demás y habilita la etiqueta de T44.

| ID | Tarea | Estado | Revisor | Fecha límite |
| --- | --- | --- | --- | --- |
| T57 | Verificación final de la entrega | No iniciado | David (R1) | 01/12 |

#### T57 — Verificación final de la entrega

Estado: **No iniciado** (0 %) · semana S15

**Qué hacer:**

1. Comprobar CI en verde y V1–V8.
2. Comprobar que T59–T61 tienen CSV y log versionados con el commit del binario.
3. Reproducir la guía en la PC de referencia.
4. Verificar que existe cada entregable.
5. Ejecutar la corrida de respaldo de la demo.
6. Registrar el resultado y, si todo pasa, habilitar la etiqueta `entrega-final` de T44.

- **Qué entregar:** `docs/verificacion-final.md`. Formato: Checklist MD con resultado y evidencia por punto.
- **Entradas y dependencias:** CI de master; V1–V8; mediciones T59–T61; X8 T56; informe T46; diapositivas T50; demo T51.
- **Evidencia:** `docs/verificacion-final.md` con fecha, commit verificado y enlace a la evidencia de cada punto.
- **Criterio de aceptación:** `docs/verificacion-final.md` con cada punto comprobado y su evidencia; habilita la etiqueta de T44.
- **Revisor:** David (R1)
- **Fecha límite:** 01/12 (martes 23:59 de S15)

### Rhamses (R6) — cronograma, documentación, informe y exposición

| ID | Tarea | Estado | Revisor | Fecha límite |
| --- | --- | --- | --- | --- |
| T01 | Cerrar la definición única y registrar aprobación interna del equipo | En curso | David (R1) | 29/09 (vencida) |
| T07 | Registrar las 61 tareas y responsables en el tablero del equipo | En curso | David (R1) | 29/09 (vencida) |
| T18 | Publicar tabla y gráficos OpenMP de tiempo, speedup y eficiencia | Completado | David (R1) | 13/10 |
| T28 | Redactar secciones 1–4 del informe con alcance y método vigentes | Completado | Angela (R2) | 27/10 |
| T33 | Calcular tiempo, speedup, eficiencia, throughput y Karp–Flatt de X1–X4 | En curso | Angela (R2) | 03/11 (vencida) |
| T36 | Redactar resultados científicos a partir de tablas X6 | En curso | Angela (R2) | 10/11 (vencida) |
| T45 | Generar figuras finales de rendimiento, riesgo y sensibilidad | En curso | Angela (R2) | 17/11 (vencida) |
| T46 | Integrar informe IEEE con problema, modelo, método y resultados | En curso | David (R1) | 24/11 |
| T47 | Vincular cada referencia IEEE con una decisión de diseño | Completado | Angela (R2) | 24/11 |
| T50 | Preparar presentación y guion de exposición | No iniciado | David (R1) | 01/12 |

#### T01 — Cerrar la definición única y registrar aprobación interna del equipo

Estado: **En curso** (50 %) · semana S06

**Qué hacer:**

1. Releer alcance, modelo, variables, entregables y semanas.
2. Consolidar una sola definición.
3. Comprobar cada enlace del README.
4. Registrar revisión individual con fecha.

- **Qué entregar:** `docs/acta-revision-definicion.md`. Formato: DOCX de definición y acta de revisión en MD.
- **Entradas y dependencias:** `docs/definicion-proyecto.docx`; `README.md`; comentarios de los seis integrantes
- **Evidencia:** `docs/acta-revision-definicion.md` con seis nombres, observaciones resueltas y commit del DOCX.
- **Criterio de aceptación:** Documento en `docs/` y registro de revisión de seis integrantes; enlaces del README válidos.
- **Revisor:** David (R1)
- **Fecha límite:** 29/09 (martes 23:59 de S06), vencida

#### T07 — Registrar las 61 tareas y responsables en el tablero del equipo

Estado: **En curso** (50 %) · semana S06

**Qué hacer:**

1. Registrar cada ID una sola vez.
2. Asignar propietario único, revisor distinto, semana, fecha límite, archivo y criterio.
3. Actualizar estados con la evidencia versionada.
4. Ejecutar `scripts/validar_cronograma.py` y versionar su log.

- **Qué entregar:** `cronograma/cronograma-interno.xlsx`; `scripts/validar_cronograma.py`. Formato: Cronograma interno XLSX: 61 tareas con propietario, revisor, fecha, estado y criterio; log del validador.
- **Entradas y dependencias:** Lista T01–T61; seis integrantes; fechas y criterios del cronograma.
- **Evidencia:** `cronograma/cronograma-interno.xlsx` con 61 IDs únicos y `results/evidencia/t07_validar_cronograma.log` en verde.
- **Criterio de aceptación:** Tablero con ID, responsable, revisor distinto, fecha, estado y criterio de terminado de cada tarea, al día hasta S15; `scripts/validar_cronograma.py` termina en verde.
- **Revisor:** David (R1)
- **Fecha límite:** 29/09 (martes 23:59 de S06), vencida

#### T33 — Calcular tiempo, speedup, eficiencia, throughput y Karp–Flatt de X1–X4

Estado: **En curso** (50 %) · semana S11

**Qué hacer:**

1. Validar esquema/semilla y cinco muestras.
2. Calcular media, desviación, speedup=T1/Tp, eficiencia=S/p, throughput=N/t y Karp–Flatt.
3. Separar comparaciones con hardware distinto.

- **Qué entregar:** `scripts/bench/analizar-rendimiento.py`. Formato: CSV agregado y figuras PNG/SVG: speedup, eficiencia, throughput y Karp–Flatt.
- **Entradas y dependencias:** CSV de T16, T21, T27 y T32; T1 de T59; X1–X2 de T60; X3 de T61; fórmulas de métricas acordadas.
- **Evidencia:** `results/bench/analisis/` con el CSV agregado y PNG/SVG de X1–X4 con fórmulas, T1 y advertencias de sobresuscripción.
- **Criterio de aceptación:** Tablas y figuras de X1–X4 con media, desviación, base T1 y límites del hardware identificados; `07-rendimiento.tex` sin los `TODO-T33`.
- **Revisor:** Angela (R2)
- **Fecha límite:** 03/11 (martes 23:59 de S11), vencida

#### T36 — Redactar resultados científicos a partir de tablas X6

Estado: **En curso** (50 %) · semana S12

**Qué hacer:**

1. Redactar resultados por zona/régimen/capacidad con N, k, IC y banda.
2. Interpretar sin extrapolar fuera de datos.
3. Incluir limitaciones y rutas a CSV.

- **Qué entregar:** `reports/informe/secciones/08-resultados-cientificos.tex`; `reports/informe/secciones/09-sensibilidad.tex`. Formato: Secciones LaTeX de resultados científicos del informe, con fuente CSV.
- **Entradas y dependencias:** Resultados T34–T35; metodología T28; tablas/figuras trazables.
- **Evidencia:** Secciones 08 y 09 con tablas y pies de figura que citan el CSV de origen en `results/cientifico/`.
- **Criterio de aceptación:** Secciones 08 y 09 con N, parámetros, IC, banda epistémica, figuras y limitaciones; incluyen H5/κ y la limitación de V6.
- **Revisor:** Angela (R2)
- **Fecha límite:** 10/11 (martes 23:59 de S12), vencida

#### T45 — Generar figuras finales de rendimiento, riesgo y sensibilidad

Estado: **En curso** (50 %) · semana S13

**Qué hacer:**

1. Seleccionar métricas científicas y de rendimiento.
2. Generar PNG/SVG con unidad, título, leyenda, incertidumbre y fuente CSV.
3. Verificar legibilidad en tamaño de informe.

- **Qué entregar:** `scripts/bench/graficar-final.py`. Formato: Figuras PNG/SVG con unidades, leyenda, fuente CSV y resolución.
- **Entradas y dependencias:** CSV de T33, T35, T40, T42 y T56; T1, X1–X2 y X3 de T59–T61; `scripts/bench/graficar-final.py`.
- **Evidencia:** `results/figures/final_*.png` y `final_*.svg` con manifiesto figura → CSV → script.
- **Criterio de aceptación:** Archivos con título, unidades, leyenda, fuente CSV y resolución apta para informe.
- **Revisor:** Angela (R2)
- **Fecha límite:** 17/11 (martes 23:59 de S13), vencida

#### T46 — Integrar informe IEEE con problema, modelo, método y resultados

Estado: **En curso** (50 %) · semana S14

**Qué hacer:**

1. Unificar estilo IEEE, numeración, ecuaciones, tablas y citas.
2. Contrastar cifras con CSV.
3. Exportar PDF y revisar páginas, enlaces, figuras y fuentes.

- **Qué entregar:** `reports/informe/`. Formato: Informe fuente en LaTeX (`reports/informe/`) y PDF IEEE generado desde las secciones integradas.
- **Entradas y dependencias:** Secciones T28, T36 y T37; análisis T33 con X1–X3 de T60–T61; X8 de T56; clúster de T25; figuras T45; referencias T47.
- **Evidencia:** PDF generado desde `reports/informe/` con revisión visual y correspondencia de cada cifra con su CSV.
- **Criterio de aceptación:** PDF con todas las secciones, tablas y figuras concordantes con CSV; sin el pendiente de `07-rendimiento.tex:92`; cifras de X1–X3 tomadas de T60–T61; incluye CUDA, los tres niveles y el clúster con X8.
- **Revisor:** David (R1)
- **Fecha límite:** 24/11 (martes 23:59 de S14)

#### T50 — Preparar presentación y guion de exposición

Estado: **No iniciado** (0 %) · semana S15

**Qué hacer:**

1. Construir diapositivas de problema, método, versiones, validación, 2/4/8/16, riesgo y conclusiones.
2. Asignar turnos y tiempos a seis.
3. Ensayar con cifras verificadas.

- **Qué entregar:** `presentacion/proyecto-final.pptx`; `presentacion/proyecto-final.pdf`. Formato: Presentación PPTX/PDF y guion de los seis integrantes.
- **Entradas y dependencias:** Informe T46; figuras T45; X8 T56; demo T51; seis integrantes.
- **Evidencia:** `presentacion/proyecto-final.pptx` y PDF; guion con diapositiva, responsable, duración y mensaje principal.
- **Criterio de aceptación:** Diapositivas con una conclusión por gráfico y guion asignado a los seis integrantes.
- **Revisor:** David (R1)
- **Fecha límite:** 01/12 (martes 23:59 de S15)

### Tareas del equipo

Trabajo de los seis integrantes; la columna «Responsable» del Excel dice «Todos».

| ID | Tarea | Estado | Revisor | Fecha límite |
| --- | --- | --- | --- | --- |
| T51 | Demostración del equipo en el clúster y respaldo | En curso | David (R1) | 01/12 |

#### T51 — Demostración del equipo en el clúster y respaldo

Estado: **En curso** (50 %) · semana S15

**Qué hacer:**

1. Trabajo del equipo: cada integrante muestra lo que construyó (David el clúster, Ashley y Lita el ejecutable de tres niveles, Angela los resultados X8, Rhamses el relato).
2. Ensayar el día previo, medir la duración y guardar el log. La corrida de respaldo en la PC de referencia se comprueba dentro de T57.

- **Qué entregar:** `scripts/run/demo-cluster.ps1`. Formato: PowerShell, log de ensayo y resultados CSV de respaldo.
- **Entradas y dependencias:** Clúster T25; tres niveles T54–T55; X8 T56; versión etiquetada T44; script `demo-cluster.ps1`.
- **Evidencia:** Log de ensayo fechado, comando único de demo y `results/demo/respaldo.csv` validado.
- **Criterio de aceptación:** Ensayo del equipo con log de ejecución el día previo; cada integrante muestra su parte.
- **Revisor:** David (R1)
- **Fecha límite:** 01/12 (martes 23:59 de S15)

### Dependencias del cierre

```text
T59 T1 (Ashley) ─┬─> T60 X1–X2 (Lita) ──┐
                 └─> T61 X3 (Angela) ───┴─> T33 análisis (Rhamses) ─┐
T54 (Ashley) ─┐                                                     ├─> T46 informe, T50 (Rhamses) ─> T57 verificación (Miguel) ─> T44 etiqueta (David)
T55 (Lita)  ──┼─> T56 X8 (Angela) ──────────────────────────────────┘
T25 (David) ──┘          └─> T51 demo (equipo)
```

- T59 va primero: T60, T61 y T56 usan su T1 como referencia secuencial.
- T54, T55 y T25 se trabajan en paralelo; T56 necesita las tres.
- T46 y T50 esperan las cifras de T33 (con los datos de T60 y T61) y de T56.
- T51 se ensaya después de T56 y su respaldo se comprueba en T57; T57 también comprueba que T59–T61 tienen CSV y log versionados.

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
| S11 | E6 rendimiento | X1–X4 CPU, cinco repeticiones y análisis por recurso; la nueva medición de T1 y X1–X3 (T59–T61) se completa en S14–S15. |
| S12 | E7 resultados | X6 y curvas con incertidumbre; CUDA cuando pase V2/V8. |
| S13 | E8 sensibilidad y código | X7, etiqueta final y guía de reproducción. |
| S14 | E9 informe | Informe IEEE y anexo de reproducción. |
| S15 | E10 exposición | Presentación, demostración, verificación final y paquete final. |
