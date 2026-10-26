# Contratos de CLI, configuración y CSV (T02)

**Responsable:** David · **Revisor:** Rhamses · **Versión del contrato:** 1

Este documento fija las interfaces que comparten los backends. Describe lo que **ya implementan** `pp_serial`, `pp_openmp`, `pp_mpi_estatico` y `pp_mpi_dinamico` (código de Ashley en `src/core`, `src/io`, `src/stats` y de David en `src/backends/mpi`). Si algo cambia, se edita este archivo en el mismo PR y se sube la versión.

## 1. Índice global y clave

Una **configuración** `c` es una combinación de estación, régimen, capacidad `C`, umbral `U` y conjunto de parámetros. Cada configuración simula `N` temporadas.

| Concepto | Definición |
| --- | --- |
| Índice global | `i = c · N + j`, con `c = config_id` y `j ∈ [0, N)`. Una corrida de una sola configuración usa `config_id = 0` por defecto. |
| Reparto | Todo backend procesa rangos de `j`; el resultado no depende de quién procesa cada índice. |
| Clave | `derivar_clave(semilla, c) = splitmix64( splitmix64(semilla) ^ (c · 0xD6E8FEB86659FD93 + 0x2545F4914F6CDD1D) )`, 64 bits, partida en dos palabras de 32 bits para Philox4x32-10. |
| Contador Philox | `{ i bajo, i alto, día, sub }`; `sub = 0` decide la ocurrencia de lluvia y `sub ≥ 1` los intentos del muestreo gamma. Nada se siembra por proceso, hilo o bloque. |
| Aritmética de conteos | `uint64_t` (`MPI_UINT64_T` en MPI). El índice global debe caber en 64 bits (`validar` lo comprueba). |

Referencia: `include/simulacion.hpp` (`simular_escenario(params, clave, idx)` es una función pura).

## 2. Acumulador y reducción

Todo backend entrega por configuración un `pp::Acumulador` que se suma con `reduction(+)` o `MPI_SUM`:

| Campo | Tipo | Significado |
| --- | --- | --- |
| `k` | `uint64_t` | Escenarios con inundación (`Amax > U`). |
| `n` | `uint64_t` | Escenarios simulados. |
| `hist[512]` | `uint64_t[512]` | Histograma del máximo acumulado en clases de 1 mm: `min(floor(Amax), 511)`. |

**Invariantes** (V1, V3, V4): `n == N`; `Σ hist == n`; `k` e `hist` idénticos bit a bit entre `pp_serial`, `pp_openmp`, `pp_mpi_estatico` y `pp_mpi_dinamico` para cualquier número de hilos, procesos y `schedule`; dos corridas iguales dan lo mismo.

## 3. Configuración (YAML plano)

Pares `clave: valor` sin anidar; `#` inicia un comentario. Ejemplo en [`config/ejemplo.yaml`](../config/ejemplo.yaml). Las banderas de la CLI tienen prioridad.

| Clave | Tipo / unidad | Por defecto | Validación |
| --- | --- | --- | --- |
| `backend` | texto | el del ejecutable | Lo fija el ejecutable; el archivo no lo cambia. |
| `estacion` | texto | `sintetica` | Etiqueta que va al CSV. |
| `regimen` | texto | `normal` | `normal` o `el_nino` (etiqueta). |
| `config_id` | entero ≥ 0 | 0 | `config_id · n + n` no desborda `uint64`. |
| `semilla` | entero sin signo de 64 bits | 12345 | Se registra en cada CSV. |
| `n` | entero sin signo | 1 000 000 | `> 0`. |
| `dias` (`D`) | entero | 120 | `> 0`. |
| `p01`, `p11` | probabilidad | 0 | `[0, 1]`. Calibrados por T10. |
| `alfa`, `theta` | reales; `theta` en mm | 1 | `> 0`. Calibrados por T10. |
| `capacidad` (`C`) | real, mm/día | 0 | `≥ 0`. Rango de diseño 5–65, paso 5. |
| `umbral` (`U`) | real, mm | 0 | `≥ 0`. Referencias 30 / 50 / 80. |
| `hilos` | entero | 1 | `≥ 0`; 0 deja `OMP_NUM_THREADS`. Solo OpenMP e híbrido. |
| `schedule` | `static` \| `dynamic` \| `guided`, con `:chunk` opcional | vacío | Vacío respeta `OMP_SCHEDULE`. Solo OpenMP e híbrido. |
| `lote` (`B`) | entero | 62 500 | `> 0`. Solo `pp_mpi_dinamico`. |
| `repeticion` | entero | 1 | `≥ 0`; 0 = calentamiento. |
| `salida` | ruta | vacía | Vacía = no escribe CSV. El directorio debe existir. |

## 4. Línea de comandos

Todos los ejecutables aceptan las mismas opciones (`--ayuda` las lista). Cada clave del YAML tiene su bandera (`--n`, `--semilla` o `--seed`, `--config-id`, `--capacidad`, `--umbral`, `--dias`, `--p01`, `--p11`, `--alfa`, `--theta`, `--estacion`, `--regimen`, `--hilos`, `--schedule`, `--lote`, `--repeticion`, `--salida`) más:

```text
<ejecutable> [--config archivo.yaml] [opciones] [--calentamiento] [--verificar] [--silencioso]
```

- `--calentamiento`: marca la fila como calentamiento (repetición 0, indicador 1). Después van las repeticiones 1–5 con indicador 0.
- `--verificar` (solo MPI): el rango 0 recalcula la referencia secuencial y compara `k` e histograma bit a bit (V1); es para cargas pequeñas.
- `--silencioso`: no imprime el resumen.
- Los ejecutables MPI se lanzan con `mpirun -np P`; el número de procesos lo fija `mpirun`.
- **Códigos de salida:** `0` correcto; `2` error de argumentos, configuración, E/S o MPI; `3` falló una verificación (suma ≠ N en `pp_openmp` y MPI, o V1 en MPI).

## 5. CSV de resultados

UTF-8, separador coma, `\n`, punto decimal, sin comillas. Una fila por corrida y configuración; el archivo se crea con la cabecera y las corridas siguientes se agregan. Cabecera exacta (`pp::encabezado_csv`):

```csv
backend,estacion,regimen,config_id,semilla,n,k,p_hat,wilson_inf,wilson_sup,dias,capacidad,umbral,p01,p11,alfa,theta,hilos,procesos,repeticion,calentamiento,schedule,afinidad,tiempo_s,commit,cpu,nucleos_fisicos,nucleos_logicos,hist512,hardware,nodos,distribucion,bloques,hilos_por_bloque
```

Las cinco últimas columnas (`hardware` … `hilos_por_bloque`) se agregaron para la entrega final (S15) **al final** de la cabecera: las columnas anteriores conservan su posición y los lectores por nombre (`csv.DictReader`) siguen funcionando. Un archivo con la cabecera anterior no se mezcla: `pp::escribir_csv` se niega a agregar filas a un CSV cuya cabecera no coincide.

| Columna | Tipo / unidad | Regla |
| --- | --- | --- |
| `backend` | texto | `serial`, `openmp`, `mpi_estatico`, `mpi_dinamico`, `hibrido` o `cuda`. |
| `estacion`, `regimen`, `config_id`, `semilla` | texto, texto, entero, entero | Copia de la configuración. |
| `n`, `k` | `uint64` | `n` es lo **simulado** (debe ser igual a lo pedido, V3) y `k` las inundaciones. |
| `p_hat`, `wilson_inf`, `wilson_sup` | reales | `k / n` e intervalo de Wilson al 95 %. |
| `dias`, `capacidad`, `umbral`, `p01`, `p11`, `alfa`, `theta` | según §3 | Parámetros usados. |
| `hilos` | entero | Hilos efectivos por proceso (1 si no hay OpenMP). |
| `procesos` | entero | Procesos MPI (1 si no hay MPI). |
| `repeticion`, `calentamiento` | entero | 0 y 1 para calentamiento; 1–5 y 0 para las medidas. |
| `schedule` | texto | `schedule` efectivo (por ejemplo `dynamic:1`); vacío si no aplica. |
| `afinidad` | texto | `OMP_PROC_BIND=…;OMP_PLACES=…` (`no_definida` si faltan). |
| `tiempo_s` | real, segundos | Tiempo de pared del cómputo y la reducción; no incluye leer la configuración. |
| `commit`, `cpu` | texto | Hash corto de Git y modelo de CPU del nodo del rango 0. |
| `nucleos_fisicos`, `nucleos_logicos` | entero | Del nodo del rango 0. |
| `hist512` | 512 enteros separados por `;` | `hist[0] … hist[511]`; su suma es `n`. |
| `hardware` | texto | `host=<nombre>;ram_gb=<GiB>` del nodo del rango 0 (`gethostname`, `MemTotal` de `/proc/meminfo`). |
| `nodos` | entero | Nodos distintos según `MPI_Get_processor_name`; 1 sin MPI. |
| `distribucion` | texto | Procesos por nodo, `host:p;host:p` en orden del primer rango de cada nodo (p. ej. `pc1:8;pc2:8`); `host:1` sin MPI. |
| `bloques`, `hilos_por_bloque` | entero o vacío | Grilla CUDA (bloques e hilos por bloque); **vacías** en los backends de CPU. |

El generador de gráficos de T18 usa su propio CSV de medición ([`protocolo-graficos-openmp.md`](protocolo-graficos-openmp.md)); falta unificarlo con este.

## 6. Log de verificación (MPI)

Los ejecutables MPI imprimen desde el rango 0 líneas con prefijo `[verif]`, para que los scripts y el CI las filtren:

```text
[verif] backend=mpi_estatico procesos=4 n_solicitado=10007 nivel_hilos_mpi=1 nucleo=pp_core
[verif] rango=0 inicio=0 fin=2502 n_local=2502
[verif] rango=1 inicio=2502 fin=5005 n_local=2503
...
[verif] suma_n=10007 suma_n_rangos=10007 suma_hist=10007 k=… estado=OK
[verif] v1_referencia=OK k_ref=…
```

En `mpi_dinamico` cada rango informa `bloques=` en lugar de `inicio`/`fin`, y el rango 0 comprueba que los bloques asignados cubran `[0, N)` sin solape ni huecos. Cualquier `estado` distinto de `OK` termina con código 3.

### Híbrido MPI + OpenMP (`pp_hibrido`)

Reparte `[0, N)` entre los procesos como `pp_mpi_estatico` y, dentro de cada proceso, llama a `ejecutar_openmp` con `--hilos` hilos y `--schedule`. Solo el hilo principal llama a MPI: se inicializa con `MPI_Init_thread(MPI_THREAD_FUNNELED)`, el nivel concedido se registra en `nivel_hilos_mpi=` y, si es menor que FUNNELED, termina con código 2. El presupuesto de núcleos es `procesos × hilos`.

```text
[verif] backend=hibrido procesos=2 n_solicitado=10007 nivel_hilos_mpi=MPI_THREAD_FUNNELED nucleo=pp_core
[verif] hibrido procesos=2 hilos_por_proceso=4 nucleos_totales=8 schedule=dynamic:7 OMP_PROC_BIND=close OMP_PLACES=cores
[verif] rango=0 inicio=0 fin=5004 hilos=4 n_local=5004
```

En el CSV, `procesos` es P y `hilos` son los hilos efectivos por proceso. Un `procesos × hilos` mayor que los núcleos físicos del equipo está sobresuscrito y se analiza aparte.

**Afinidad.** Con su anclaje por defecto, Open MPI fija cada proceso a un núcleo y todos sus hilos compartirían ese núcleo. Hay dos combinaciones válidas:

| Lanzamiento | `OMP_PROC_BIND` | Por qué |
| --- | --- | --- |
| `mpirun --bind-to none` (el que usan `medir_hibrido.py` y `ejecutar_barridos.py` para el híbrido) | `false` (valor por defecto de `medir_hibrido.py --bind`; en `ejecutar_barridos.py` el valor por defecto de `--omp-bind` es `close`, así que para el híbrido pase `--omp-bind false`) | Sin anclaje MPI, cada proceso ve **todos** los núcleos y la misma lista de lugares. Con `close`, el hilo 0 de **cada** proceso iría al primer lugar y los hilos de procesos distintos se apilarían en los mismos núcleos; `spread` tiene el mismo problema, porque todos los procesos reparten sus hilos sobre lugares idénticos. Con `false` el planificador del sistema operativo reparte los `procesos × hilos` hilos. |
| `mpirun --map-by ppr:<procesos>:node:PE=<hilos>` | `close` u otro, con `OMP_PLACES=cores` | Open MPI reserva `hilos` núcleos distintos a cada proceso; la lista de lugares de cada proceso se limita a sus núcleos y `close` ya no solapa procesos. |

`OMP_PROC_BIND=close` con `--bind-to none` solo es aceptable cuando se verifica equivalencia y no se mide tiempo (por ejemplo, las pruebas CTest `pp_hibrido_<p>x<h>`). Los valores efectivos quedan en la columna `afinidad` y en el log `[verif]`; el ejemplo de arriba muestra el formato, no la afinidad recomendada.
