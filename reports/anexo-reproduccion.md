# Anexo de reproducción (T48)

**Responsable:** Ashley · Anexo condensado para el informe IEEE. La guía paso a paso está en [docs/guia-reproduccion.md](../docs/guia-reproduccion.md); los contratos completos, en [docs/contratos.md](../docs/contratos.md).

## A. Entorno

### A.1 Hardware de medición

| Elemento | Valor |
| --- | --- |
| CPU | Intel Core Ultra 9 275HX: 8 núcleos P + 16 núcleos E, 24 hilos, sin SMT |
| Memoria del anfitrión | 63 GB |
| Sistema anfitrión | Windows 11 Pro, Docker Desktop sobre WSL2, con corriente alterna |
| Vista del contenedor | 24 vCPU (`nproc` = 24; `/proc/cpuinfo` informa 24 núcleos físicos), 31 GiB de RAM en la VM de WSL2 |
| Limitación | La afinidad (`OMP_PROC_BIND`, `OMP_PLACES`, `mpirun --bind-to`) ancla a vCPU de la VM, no a núcleos P o E concretos; el planificador de Windows decide el núcleo real. |

### A.2 Software (imagen `pp-g8`, `docker/Dockerfile`)

Versiones leídas de la imagen `pp-g8` (id `95d58276392f`, la misma de los logs `t14`/`t16`) con `docker run --rm pp-g8 bash -c "g++ --version; mpirun --version; cmake --version; python3 --version"`:

| Componente | Versión |
| --- | --- |
| Sistema base | Ubuntu 24.04 |
| Compilador C++ | g++ 13.3.0 (Ubuntu 13.3.0-6ubuntu2~24.04.1) |
| Compilador de V5 | Ubuntu clang 18.1.3 + libomp (Archer) y `libclang-rt-18-dev` |
| MPI | Open MPI 4.1.6 |
| CMake | 3.28.3 |
| Python | 3.12.3, con pytest 7.4.4, numpy 1.26.4, scipy 1.11.4 y matplotlib 3.6.3 |
| Git | 2.43.0 |
| Variables fijas | `OMPI_ALLOW_RUN_AS_ROOT=1`, `OMPI_ALLOW_RUN_AS_ROOT_CONFIRM=1`, `OMPI_MCA_btl_vader_single_copy_mechanism=none`; git con `core.autocrlf input` y `safe.directory '*'` |

## B. Compilación, ejecución y pruebas

Todo dentro de la imagen, con el repositorio montado en `/work` (en Git Bash, `MSYS_NO_PATHCONV=1`):

```bash
docker build -t pp-g8 -f docker/Dockerfile .
docker run --rm --shm-size=1g -v "$PWD:/work" -w /work -e PP_COMMIT=<commit> pp-g8 bash -c '<comando>'
```

| Paso | Comando |
| --- | --- |
| Compilar (Release, con MPI) | `cmake -S . -B build/docker-mpi -DCMAKE_BUILD_TYPE=Release -DPP_BUILD_MPI=ON && cmake --build build/docker-mpi --parallel` |
| Opciones CMake | `PP_BUILD_OPENMP=ON`, `PP_BUILD_MPI=OFF`, `PP_BUILD_CUDA=OFF` (no activada en T29), `PP_V6_OBSERVADO=OFF` |
| Pruebas CTest | `ctest --test-dir build/docker-mpi --output-on-failure` (20 pruebas; `v6_observado` deshabilitada) |
| V6 frente a lo observado | `-DPP_V6_OBSERVADO=ON` y `ctest -L v6_observado` (hoy no cumple el 10 % en las colas) |
| Pruebas de scripts | `PP_BIN_DIR=build/docker-mpi/src/backends PP_V6_GENERADOR=build/docker-mpi/pp_v6_generador python3 -m pytest -q tests/unit -k "not observado"` y `python3 -m pytest -q tests/integration` |
| V5 (carreras) | `--security-opt seccomp=unconfined` y `python3 -m pytest -v tests/concurrency` |
| Secuencial | `build/docker-mpi/src/backends/serial/pp_serial --config <yaml> --n <N> --salida <csv>` |
| OpenMP | `pp_openmp ... --hilos <h> --schedule static\|dynamic[:c]\|guided[:c]` con `OMP_PROC_BIND=close OMP_PLACES=cores` |
| MPI E1 / E2 | `mpirun -np <P> pp_mpi_estatico ...` / `mpirun -np <P> pp_mpi_dinamico ... [--lote B]` (en E2 el rango 0 es maestro y no simula) |
| Híbrido | `mpirun -np <P> --bind-to none pp_hibrido ... --hilos <h>` (`MPI_THREAD_FUNNELED`) |
| Calibración | `auditoria_datos.py` → `clasificar_regimenes.py` → `calibrar.py --semilla 20261015` → `generar_configs.py` |
| Mediciones | `medir_secuencial.py`, `medir_openmp.py`, `graficar_openmp_ashley.py`, `ejecutar_barridos.py --experimento x1\|x2\|x3`, `comparar_mpi_heterogeneo.py`; `medir_mpi.py` y `medir_hibrido.py` al integrar la ola A <!-- TODO-OLA-A --> |
| Corridas científicas | `corrida-oficial.py` (X6), `analizar-riesgo.py` (T35), `sensibilidad.py` (X7) al integrar la ola C <!-- TODO-OLA-C --> |

Protocolo de medición: misma `N`, semilla `20261015` y configuración por comparación; un calentamiento que no cuenta y cinco repeticiones; V1 (`k`, `n` e histograma idénticos al secuencial) antes de calcular speedup; build `Release` obligatorio. Códigos de salida de los ejecutables: `0` correcto, `2` error de argumentos/configuración/E/S/MPI, `3` falló una verificación.

## C. CSV de resultados del simulador (contrato T02, versión 1)

Lo escriben todos los ejecutables con `--salida` (`src/io/resultados_csv.cpp`). UTF-8, coma, `\n`, punto decimal, sin comillas (las comas dentro de los textos se sustituyen por espacios). Una fila por corrida; el archivo se crea con la cabecera y las corridas se agregan. Un CSV con otra cabecera se rechaza. 34 columnas, en este orden:

| # | Columna | Tipo / unidad | Significado |
| --- | --- | --- | --- |
| 1 | `backend` | texto | `serial`, `openmp`, `mpi_estatico`, `mpi_dinamico`, `hibrido` o `cuda` |
| 2 | `estacion` | texto | Estación (etiqueta del YAML) |
| 3 | `regimen` | texto | `normal` o `el_nino` |
| 4 | `config_id` | entero ≥ 0 | `c` del índice global `i = c·N + j` |
| 5 | `semilla` | uint64 | Semilla global (clave Philox derivada de semilla y `config_id`) |
| 6 | `n` | uint64 | Escenarios simulados (debe igualar los pedidos, V3) |
| 7 | `k` | uint64 | Escenarios con inundación (`Amax > U`) |
| 8 | `p_hat` | real | `k / n` |
| 9 | `wilson_inf` | real | Límite inferior del IC de Wilson al 95 % |
| 10 | `wilson_sup` | real | Límite superior del IC de Wilson al 95 % |
| 11 | `dias` | entero | Días de la temporada `D` |
| 12 | `capacidad` | real, mm/día | Capacidad de drenaje `C` |
| 13 | `umbral` | real, mm | Umbral de inundación `U` |
| 14 | `p01` | probabilidad | P(lluvia hoy \| seco ayer) |
| 15 | `p11` | probabilidad | P(lluvia hoy \| lluvia ayer) |
| 16 | `alfa` | real > 0 | Forma de la gamma del monto diario |
| 17 | `theta` | real > 0, mm | Escala de la gamma |
| 18 | `hilos` | entero | Hilos efectivos por proceso (1 sin OpenMP) |
| 19 | `procesos` | entero | Procesos MPI (1 sin MPI) |
| 20 | `repeticion` | entero | 0 = calentamiento; 1–5 = medidas |
| 21 | `calentamiento` | 0/1 | 1 en la corrida de calentamiento |
| 22 | `schedule` | texto | Schedule OpenMP efectivo (p. ej. `dynamic:1`); vacío si no aplica |
| 23 | `afinidad` | texto | `OMP_PROC_BIND=…;OMP_PLACES=…` (`no_definida` si faltan) |
| 24 | `tiempo_s` | real, s | Tiempo de pared del cómputo y la reducción (sin leer la configuración ni arrancar `mpirun`) |
| 25 | `commit` | texto | `PP_COMMIT` si está definida; si no, el hash que CMake leyó al configurar; `desconocido` sin ninguno |
| 26 | `cpu` | texto | Modelo de CPU del nodo del rango 0 (`/proc/cpuinfo`) |
| 27 | `nucleos_fisicos` | entero | Núcleos físicos del nodo del rango 0 |
| 28 | `nucleos_logicos` | entero | Hilos de hardware del nodo del rango 0 |
| 29 | `hist512` | 512 enteros separados por `;` | Histograma de `Amax` en clases de 1 mm, `min(floor(Amax), 511)`; suma = `n` |
| 30 | `hardware` | texto | `host=<nombre>;ram_gb=<GiB>` del nodo del rango 0 |
| 31 | `nodos` | entero | Nodos distintos (`MPI_Get_processor_name`); 1 sin MPI |
| 32 | `distribucion` | texto | Procesos por nodo, `host:p;host:p`; `host:1` sin MPI |
| 33 | `bloques` | entero o vacío | Bloques de la grilla CUDA; vacío en CPU |
| 34 | `hilos_por_bloque` | entero o vacío | Hilos por bloque CUDA; vacío en CPU |

Invariantes: `Σ hist512 = n`; `k` y `hist512` idénticos bit a bit entre backends, hilos, procesos y schedules (V1).

## D. CSV de medición (`scripts/bench/`)

Los scripts de medición leen el CSV del simulador por nombre de columna y escriben CSV propios (`csv.DictWriter`, coma, con cabecera).

### D.1 `results/bench/secuencial_t1.csv` (`medir_secuencial.py`, T14)

Una sola fila.

| Columnas | Significado |
| --- | --- |
| `backend`, `n`, `semilla`, `config_id`, `dias` | Carga medida (`backend = serial`) |
| `k` | Inundaciones; idéntico en las 6 corridas o el script falla |
| `repeticiones` | Número de medidas (5) |
| `cpu`, `nucleos_fisicos`, `nucleos_logicos`, `ram_gb` | Hardware |
| `compilador`, `tipo_build`, `commit`, `fecha`, `so` | Entorno |
| `t_calentamiento`, `t1` … `t5` | Tiempos en s (calentamiento y cada repetición) |
| `media`, `desviacion` | Media y desviación estándar muestral de `t1..t5`, s |
| `us_por_escenario` | µs por temporada (`media / n`) |
| `supera_10us` | 1 si `us_por_escenario ≥ 10` (riesgo §16.1 de la definición) |

### D.2 `medir_openmp.py` (T16)

| Archivo | Granularidad | Columnas |
| --- | --- | --- |
| `<salida>.csv` | una fila por corrida OpenMP | `modelo`, `hilos`, `repeticion` (0 = calentamiento), `tiempo_s`, `n`, `semilla`, `cpu`, `nucleos_fisicos`, `afinidad`, `schedule`, `commit`, `calentamiento`, `hilos_efectivos`, `nucleos_logicos`, `sobresuscrito`, `excede_logicos`, `k`, `config_id` |
| `<salida>_secuencial_ref.csv` | una fila por corrida secuencial | las mismas, con `modelo = secuencial` |
| `<salida>_resumen.csv` (publicado como `results/bench/openmp.csv`) | una fila por punto `schedule × hilos` | `backend`, `hilos`, `hilos_efectivos`, `schedule`, `n`, `semilla`, `config_id`, `afinidad`, `nucleos_fisicos`, `nucleos_logicos`, `sobresuscrito` (hilos > físicos), `excede_logicos` (hilos > lógicos), `t_calentamiento`, `t1` … `t5`, `media`, `desviacion`, `k`, `equivalente_serial` (V1: 1/0), `cpu`, `ram_gb`, `compilador`, `tipo_build`, `commit`, `fecha`, `so` |

### D.3 `results/bench/openmp_agregado.csv` (`graficar_openmp_ashley.py`, T18)

Una fila por `schedule × hilos`: `schedule`, `hilos`, `n`, `semilla`, `t1_media`, `t1_desv` (T1 secuencial, s), `tp_media`, `tp_desv` (con p hilos, s), `speedup` (`T1/Tp`), `speedup_desv_aprox` (propagación de errores relativos; no es un IC), `eficiencia` (`speedup/p`), `sobresuscrito`, `muestras`, `fuente_t1` (T14 o la fila serial del propio CSV), `cpu`, `nucleos_fisicos`, `nucleos_logicos`, `afinidad`, `commit`, `fuente`.

### D.4 `results/bench/<x1|x2|x3>.csv` (`ejecutar_barridos.py`, T26)

Una fila por punto (backend × recursos × N). Con `--anexar` se agregan filas y se unen columnas.

| Columna | Tipo | Significado |
| --- | --- | --- |
| `experimento` | texto | `x1` (fuerte), `x2` (débil) o `x3` (carga) |
| `backend` | texto | `serial`, `openmp`, `mpi_estatico`, `mpi_dinamico` o `hibrido` |
| `n` | entero | Escenarios del punto |
| `procesos`, `hilos` | entero | Factorización usada |
| `recursos` | entero | Presupuesto: hilos, procesos o `procesos × hilos` |
| `nodos` | entero | Nodos distintos según `--hosts`/`--hostfile` (1 sin ellos) |
| `hosts` | texto | Hosts usados, `;` (el hostname local sin `--hosts`) |
| `schedule` | texto | Schedule efectivo (`-` si no aplica) |
| `lote` | texto | Tamaño de bloque de E2 (`por_defecto`) o `-` |
| `afinidad` | texto | Variables OpenMP y `--bind-to` aplicados |
| `sobresuscrito` | 0/1 | Recursos > núcleos físicos (`--nucleos`) |
| `nucleos_ref` | entero | Núcleos usados para esa marca |
| `repeticiones` | entero | Medidas por punto |
| `t_calentamiento` | real, s | Tiempo de la corrida de calentamiento (vacío con `--sin-calentamiento`) |
| `tiempos` | reales `;` | `tiempo_s` interno de cada repetición |
| `media`, `desviacion`, `minimo` | real, s | Estadísticos de `tiempos` (desviación muestral) |
| `k`, `k_ref` | entero | `k` del punto y de la referencia |
| `equivalente` | 1/0/vacío | V1 frente a la referencia (`--referencia serial\|primera`); vacío con `ninguna` |
| `trabajo_rangos` | enteros `;` | `n_local` de cada rango (líneas `[verif]`) |
| `bloques_rangos` | enteros `;` | Bloques recibidos por rango (solo E2) |
| `desbalance` | real | máx / media del trabajo de los rangos que computan |
| `semilla`, `config_id`, `config`, `config_sha` | | Carga y SHA-1 (12 hex) del YAML |
| `commit` | texto | `GIT_COMMIT` o `git rev-parse` (+`cambios_sin_commit` si el árbol está sucio) |
| `cpu`, `nucleos_fisicos`, `nucleos_logicos`, `nproc`, `ram_gb`, `gpu`, `red`, `hostname` | | Hardware del lanzador |
| `tipo_build`, `compilador`, `so`, `comando` | | Del `CMakeCache.txt`, del sistema y la línea de comandos |
| `commit_binario` | texto | Columna `commit` del CSV del simulador |
| `fecha` | ISO 8601 | Fin del punto |

### D.5 `comparar_mpi_heterogeneo.py` (T32)

`<salida>.csv` contiene las filas de D.4 para E1 y E2. `<salida>_resumen.csv`, una fila por `procesos × n`: `procesos`, `n`, `t_e1`, `sd_e1`, `desbalance_e1`, `nodos_e1` (trabajo por nodo, `host=n;…`), `t_e2`, `sd_e2`, `desbalance_e2`, `nodos_e2`, `razon_e2_e1` (`t_e2 / t_e1`), `mas_rapido` (`E1`/`E2`), `equivalentes` (1 si todas las filas son V1). `<salida>_resumen.md` es la misma tabla en Markdown. Compose y Swarm escriben `e1_estatico.csv`, `e2_dinamico.csv` y `e1_e2_comparacion_resumen.{csv,md}`.

### D.6 Barridos MPI e híbrido (T21, T27) <!-- TODO-OLA-A -->

<!-- TODO-OLA-A: detallar columnas de mpi.csv, mpi_resumen.csv, hibrido.csv e hibrido_resumen.csv al integrar la rama entrega/a. -->

`results/bench/mpi.csv` y `hibrido.csv` (una fila por corrida) y `mpi_resumen.csv` / `hibrido_resumen.csv` (una fila por punto: tiempos, media, desviación, speedup frente a T1, eficiencia, afinidad y metadatos; en MPI además `procesos_computo` y `eficiencia_computo`, porque en E2 el maestro no simula).

### D.7 Resultados científicos (X6, T35, X7) <!-- TODO-OLA-C -->

<!-- TODO-OLA-C: completar con el esquema definitivo de x6.csv, bootstrap.csv, x7.csv y las tablas al integrar la ola C. -->

Planificado: `results/cientifico/x6.csv`, `bootstrap.csv` y `x7.csv` usan el contrato de la sección C; las tablas `results/cientifico/tablas/{riesgo,comparacion_enso,sensibilidad}.{csv,md}` agregan `p̂`, IC de Wilson, la banda epistémica (percentiles 2,5/50/97,5 entre réplicas bootstrap) y `p_hist` (excedencia leída de `hist512`, control de consistencia).
