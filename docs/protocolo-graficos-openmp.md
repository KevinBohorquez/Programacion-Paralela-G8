# Tabla y gráficos OpenMP de la tarea T18

**Responsables:** Ashley (generador) y Rhamses (revisión de figuras). El flujo aceptado es este: [medir_openmp.py](../scripts/bench/medir_openmp.py) produce las filas por punto que se publican como `results/bench/openmp.csv`, y [graficar_openmp_ashley.py](../scripts/bench/graficar_openmp_ashley.py) produce el agregado y las figuras. Los CSV y las figuras del barrido de referencia ya están versionados (commit `71fddf4`).

## 1. Flujo

```text
medir_secuencial.py ──► secuencial_t1.csv                (T14, T1: una fila con t1..t5)
medir_openmp.py --salida <dir>/openmp.csv
        ├─► <dir>/openmp.csv                (T16, UNA FILA POR CORRIDA: calentamiento = repetición 0, luego 1..5)
        ├─► <dir>/openmp_secuencial_ref.csv (referencia secuencial, una fila por corrida)
        └─► <dir>/openmp_resumen.csv        (UNA FILA POR PUNTO: serial + schedule × hilos, con t1..t5)
                              │
graficar_openmp_ashley.py ◄───┘  (--entrada <formato por punto>, --t1-csv secuencial_t1.csv)
        ├─► results/bench/openmp_agregado.csv
        └─► results/figures/openmp_{tiempo,speedup,eficiencia}.{png,svg}
```

Los dos formatos no son intercambiables:

| Archivo | Formato | Lo lee |
| --- | --- | --- |
| `openmp.csv` que escribe hoy `medir_openmp.py` | una fila por corrida (`modelo, hilos, repeticion, tiempo_s, …`) | [graficar_openmp.py](../scripts/bench/graficar_openmp.py) (§5) |
| `openmp_resumen.csv` que escribe hoy `medir_openmp.py` | una fila por punto (`backend, hilos, schedule, …, t1..t5, media, desviacion, …`) | `graficar_openmp_ashley.py` |
| `results/bench/openmp.csv` **versionado** (commit `71fddf4`) | una fila por punto: es el resumen de la medición de referencia, de una versión anterior del script que lo escribía con ese nombre | `graficar_openmp_ashley.py` (valor por defecto de `--entrada`) |

`graficar_openmp_ashley.py` exige columnas `t1..t5` por punto y termina con error si recibe el `openmp.csv` por corrida. Para regenerar las figuras publicadas tras una medición nueva, copie `<dir>/openmp_resumen.csv` a `results/bench/openmp.csv` (o páselo con `--entrada`).

## 2. Medición (T16)

`medir_openmp.py` mide primero la referencia secuencial (`backend=serial`) y después cada punto `schedule × hilos` con el mismo protocolo:

- **Calentamiento:** una corrida que no entra en la media; su tiempo se guarda en `t_calentamiento`.
- **Repeticiones:** cinco medidas (`t1` … `t5`), con `media` y `desviacion` (desviación estándar muestral).
- **Equivalencia V1:** cada corrida, calentamiento incluido, debe dar `k`, `n` e histograma idénticos al secuencial. Si no, `equivalente_serial = 0` y el script termina con error.
- **Build:** el script se niega a medir un build `Debug`.
- **Afinidad:** fija `OMP_PROC_BIND` y `OMP_PLACES` (por defecto `close` y `cores`) y retira `OMP_NUM_THREADS` y `OMP_SCHEDULE` del entorno. Los hilos y el schedule solo vienen de `--hilos` y `--schedule`.
- **Sobresuscripción:** marca `sobresuscrito` (hilos > núcleos físicos) y `excede_logicos`.
- **Metadatos:** cada fila guarda CPU, núcleos físicos y lógicos, RAM, compilador, tipo de build, commit, fecha y sistema operativo.

Comandos de la medición de referencia (`results/evidencia/t14_medir_secuencial.log`, `t16_build_release.log` y `t16_medir_openmp.log`), ejecutados dentro de la imagen `pp-g8` (`docker run --rm --shm-size=1g -v "$PWD:/work" -w /work pp-g8 bash -c '<comando>'`):

```bash
cmake --fresh -S . -B build/docker -DCMAKE_BUILD_TYPE=Release && cmake --build build/docker --parallel && ctest --test-dir build/docker --output-on-failure
python3 scripts/bench/medir_secuencial.py --build-dir build/docker --n 20000000 --repeticiones 5 --salida build/barrido/secuencial_t1.csv
python3 scripts/bench/medir_openmp.py --build-dir build/docker --n 20000000 --hilos 2,4,8,16 --schedules static,dynamic,64 --repeticiones 5 --salida build/barrido/openmp.csv
```

Los CSV se copiaron después a `results/bench/`: `secuencial_t1.csv` tal cual y el resumen por punto como `results/bench/openmp.csv` (ver §1).

| Parámetro | Valor de la medición de referencia |
| --- | --- |
| Carga | N = 2 × 10⁷ escenarios, 120 días, `config/sintetico.yaml`, `config_id = 0` |
| Semilla | 20261015 |
| Hilos | 2, 4, 8 y 16 |
| Schedules | `static`, `dynamic` (el runtime lo informa como `dynamic:1`) y `dynamic:64` |
| Afinidad | `OMP_PROC_BIND=close`, `OMP_PLACES=cores` |
| Compilador y build | g++ 13.3.0 (Ubuntu 24.04), `Release` |
| Commit medido | `43be549ae855` |
| Equipo | Intel Core Ultra 9 275HX, Docker Desktop sobre WSL2 (24 vCPU, 31,1 GB) |

## 3. Agregado y gráficos (T18)

Desde la raíz del repositorio, dentro de `pp-g8`:

```bash
python3 scripts/bench/graficar_openmp_ashley.py --t1-csv results/bench/secuencial_t1.csv --svg
```

Valores por defecto: `--entrada results/bench/openmp.csv`, `--agregado results/bench/openmp_agregado.csv` y `--figuras results/figures`. `--svg` añade los `.svg` a los `.png`. `--plantilla` dibuja ejes vacíos rotulados «PENDIENTE», sin cifras.

Reglas que aplica el generador:

- **Sin datos no hay gráfico:** termina con error si falta el CSV, si un punto no tiene las cinco muestras o si no hay filas OpenMP.
- **Misma carga y hardware:** exige un único valor de `n`, `semilla`, `cpu` y `nucleos_fisicos` en todo el CSV.
- **V1:** rechaza el CSV si alguna fila tiene `equivalente_serial` distinto de 1.
- **T1:** con `--t1-csv` se usa la media de T14, ya sea en columnas `t1..t5` o en cinco filas `tiempo_s`. Sin esa opción, se usa la fila `serial` del propio CSV de T16. La columna `fuente_t1` del agregado indica cuál se usó. La medición de referencia usó T14.
- **Cálculos:** `speedup = media(T1) / media(Tp)` y `eficiencia = speedup / p`. `speedup_desv_aprox` propaga los errores relativos de T1 y Tp; es aproximada y no es un intervalo de confianza.
- **Figuras:** una curva por schedule, con línea ideal en speedup y eficiencia y la referencia T1 en el gráfico de tiempo. Las barras de error muestran una desviación estándar. Los puntos sobresuscritos llevan marcador hueco.

`openmp_agregado.csv` tiene una fila por `schedule × hilos`. Sus columnas son `t1_media`, `t1_desv`, `tp_media`, `tp_desv`, `speedup`, `speedup_desv_aprox`, `eficiencia`, `sobresuscrito`, `muestras`, `fuente_t1`, CPU, núcleos, afinidad, commit y fuente.

La prueba `tests/unit/test_graficar_openmp_ashley.py` cubre el agregado, los rechazos y la generación de figuras con un CSV sintético.

## 4. Advertencias para interpretar las cifras

- **Núcleos P y E:** el Core Ultra 9 275HX tiene 8 núcleos de rendimiento (P) y 16 de eficiencia (E), sin hyper-threading. WSL2 expone 24 vCPU iguales, y `/proc/cpuinfo` los informa como 24 núcleos físicos. `OMP_PLACES=cores` no distingue los tipos de núcleo, y el planificador de Windows decide en qué núcleo real corre cada vCPU. A partir de 8 hilos, parte del trabajo puede caer en núcleos E. La pérdida de eficiencia con 8 y 16 hilos mezcla ese efecto con el del paralelismo. No debe leerse como sobrecarga de OpenMP sin más análisis.
- **Afinidad en WSL2:** `OMP_PROC_BIND` ancla los hilos a vCPU, no a núcleos físicos del anfitrión. La afinidad solo se respeta dentro de la máquina virtual.
- **Sobresuscripción:** con 24 núcleos informados, ningún punto de 2 a 16 hilos queda marcado como sobresuscrito en este equipo. En un equipo con menos núcleos, el generador marca los puntos y deben analizarse aparte.
- **Equivalencia antes del rendimiento:** solo se interpreta un speedup si V1 (`equivalente_serial = 1`) y V5 (`results/evidencia/t17_v5_archer.log`) están en verde.

## 5. Generador alternativo

[graficar_openmp.py](../scripts/bench/graficar_openmp.py), con su prueba `tests/unit/test_graficar_openmp.py`, lee un formato distinto: una fila por corrida y la cabecera `modelo,hilos,repeticion,tiempo_s,…`. Las figuras publicadas no lo usan. Se conserva para CSV externos con ese formato. Escribe en `<salida>/processed/openmp_resumen.csv` y en `<salida>/figures/openmp_*.svg`. Con `--salida results` sobrescribiría los `.svg` publicados, así que debe usarse con otro directorio de salida.
