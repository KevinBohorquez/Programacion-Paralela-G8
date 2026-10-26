# Guía de reproducción (T44)

**Responsable:** David · **Alcance:** desde un clon limpio, en Windows o Linux, hasta cada resultado versionado del proyecto (pruebas, datos, mediciones, corridas científicas, Compose, Swarm y demo).

Todo se ejecuta dentro de la imagen Docker `pp-g8`: en el anfitrión solo hacen falta Git y Docker. Las secciones 1–6.1, 8 y 9 se verificaron en el commit `3dcafa3`; las secciones 6.2–6.6 y 7 describen los scripts ya integrados (`medir_mpi.py`, `medir_hibrido.py`, `corrida-oficial.py`, `analizar-riesgo.py`, `sensibilidad.py`, `analizar-rendimiento.py`, `graficar-final.py`) con su CLI actual y los comandos de la campaña oficial.

## 1. Ruta rápida

```bash
git clone https://github.com/KevinBohorquez/Programacion-Paralela-G8.git
cd Programacion-Paralela-G8
docker build -t pp-g8 -f docker/Dockerfile .

# Git Bash en Windows: MSYS_NO_PATHCONV=1 (ver §11). En Linux no hace falta.
MSYS_NO_PATHCONV=1 docker run --rm --shm-size=1g -v "$PWD:/work" -w /work \
  -e PP_COMMIT=$(git rev-parse --short=12 HEAD) pp-g8 bash -c \
  'cmake -S . -B build/docker -DCMAKE_BUILD_TYPE=Release -DPP_BUILD_MPI=ON && cmake --build build/docker --parallel && ctest --test-dir build/docker --output-on-failure'
```

Resultado esperado: `100% tests passed, 0 tests failed out of 20` y `v6_observado (Disabled)` en la lista de pruebas no ejecutadas.

Abreviatura usada en el resto de la guía: **«en `pp-g8`»** = dentro de

```bash
MSYS_NO_PATHCONV=1 docker run --rm --shm-size=1g -v "$PWD:/work" -w /work \
  -e PP_COMMIT=$(git rev-parse --short=12 HEAD) -e GIT_COMMIT=$(git rev-parse --short=12 HEAD) \
  pp-g8 bash -c '<comando>'
```

En PowerShell: sin `MSYS_NO_PATHCONV`, con `"${PWD}:/work"` y `$(git rev-parse --short=12 HEAD)` igual.

## 2. Requisitos y convenciones

| Elemento | Valor |
| --- | --- |
| Anfitrión | Git y Docker (Docker Desktop con WSL2 en Windows, Docker Engine en Linux). |
| Imagen | `pp-g8`: Ubuntu 24.04, g++ 13.3, clang 18, Open MPI 4.1.6, CMake 3.28, Python 3.12 con pytest, numpy, scipy y matplotlib ([docker/Dockerfile](../docker/Dockerfile)). |
| Montaje | El repositorio se monta en `/work`; el código no se copia a la imagen. |
| Directorio de build | `build/docker`, Release y **con MPI** (`-DPP_BUILD_MPI=ON`): es el valor por defecto de `--build-dir` en todos los scripts de medición y de corridas científicas, y el que usa la campaña oficial. La demo web busca además los binarios MPI en `build/docker-mpi` (§9). `build/` está en `.gitignore`. |
| Semilla | `20261015` en calibración, mediciones y corridas científicas. |
| Ruta del repositorio | Contiene espacios y tildes: siempre entre comillas. |

### Variables de entorno

| Variable | La lee | Para qué |
| --- | --- | --- |
| `PP_COMMIT` | Ejecutables `pp_*` (columna `commit` del CSV); también `medir_secuencial.py`, `medir_openmp.py`, `medir_mpi.py`, `medir_hibrido.py` y `scripts/run/_comun_cientifico.py`, que la reenvían a los binarios | Sin ella, los binarios usan el commit que CMake leyó con `git` al configurar y los scripts llaman a `git rev-parse`. En un worktree, `git` dentro del contenedor falla (el archivo `.git` apunta a una ruta de Windows) y queda `desconocido`. |
| `GIT_COMMIT` | `scripts/bench/_comun_bench.py` (`ejecutar_barridos.py`, `comparar_mpi_heterogeneo.py`), Compose y Swarm (`docker/nodo_mpi.sh` la copia a `PP_COMMIT` y la reenvía con `mpirun -x PP_COMMIT`) | Misma razón; sin ella el script llama a `git rev-parse`. Se pasan **ambas** variables. |
| `PP_BIN_DIR` | `tests/unit/test_analitico.py`, `tests/integration/test_openmp_equivalencia.py`, `tests/integration/test_mpi.py` | Carpeta `.../src/backends`. Por defecto `build/src/backends` (o ninguna, en `test_mpi.py`); si no existe, la prueba se **omite** (no falla). |
| `PP_V6_GENERADOR` | `tests/unit/test_estadistico.py` | Ruta de `pp_v6_generador`. Por defecto `build/pp_v6_generador`; si no existe, la prueba se omite. |
| `PP_V6_N`, `PP_V6_N_OBS` | `test_estadistico.py` | Temporadas simuladas en V6 (20 000 por defecto). |
| `OMP_PROC_BIND`, `OMP_PLACES` | Ejecutables OpenMP e híbrido | Afinidad; los scripts de medición los fijan ellos mismos. |

> En un worktree, si falta `PP_COMMIT`, los scripts `medir_*.py` toman el commit de `git` y dentro del contenedor el resultado es `desconocido`. Pase siempre `-e PP_COMMIT -e GIT_COMMIT` (abreviatura «en `pp-g8`») y revise la columna `commit`.

## 3. Compilar

| Variante | Comando (en `pp-g8`) | Opción CMake |
| --- | --- | --- |
| Oficial: núcleo, secuencial, OpenMP, MPI estático, dinámico e híbrido | `cmake -S . -B build/docker -DCMAKE_BUILD_TYPE=Release -DPP_BUILD_MPI=ON && cmake --build build/docker --parallel` | `PP_BUILD_MPI=OFF` por defecto: sin la opción solo se compilan secuencial y OpenMP |
| Copia para la demo web (binarios MPI) | `cmake -S . -B build/docker-mpi -DCMAKE_BUILD_TYPE=Release -DPP_BUILD_MPI=ON && cmake --build build/docker-mpi --parallel` | igual que el oficial |
| V6 frente a lo observado en CTest | añadir `-DPP_V6_OBSERVADO=ON` | `OFF` por defecto |
| CUDA | No se compila: T29 no activó la extensión ([decision-cuda.md](decision-cuda.md)). | `PP_BUILD_CUDA=OFF` |

Ejecutables: `build/docker/src/backends/{serial/pp_serial, openmp/pp_openmp, mpi/pp_mpi_estatico, mpi/pp_mpi_dinamico, hybrid/pp_hibrido}` y `build/docker/pp_v6_generador`. Todos aceptan `--ayuda` y la CLI de [contratos.md §4](contratos.md#4-línea-de-comandos).

Los scripts de medición se niegan a usar un build que no sea `Release` (`--permitir-debug` solo para probarlos).

Una corrida individual:

```bash
MSYS_NO_PATHCONV=1 docker run --rm --shm-size=1g -v "$PWD:/work" -w /work pp-g8 \
  build/docker/src/backends/serial/pp_serial --config config/piura_miraflores_el_nino.yaml --n 100000 --salida /tmp/r.csv
# híbrido: siempre con --bind-to none y OMP_PROC_BIND=false (contratos.md §6)
MSYS_NO_PATHCONV=1 docker run --rm --shm-size=1g -v "$PWD:/work" -w /work -e OMP_PROC_BIND=false -e OMP_PLACES=cores pp-g8 \
  mpirun -np 2 --bind-to none build/docker/src/backends/hybrid/pp_hibrido --config config/piura_miraflores_el_nino.yaml --n 100000 --hilos 2
```

Con la semilla del YAML, ambas dan `k = 59153` sobre `n = 100000` (V1).

## 4. Pruebas

| Suite | Comando (en `pp-g8`) | Resultado esperado |
| --- | --- | --- |
| CTest (build oficial, con MPI) | `ctest --test-dir build/docker --output-on-failure` | 20/20: `smoke`, `v6_generador`, `v1_equivalencia_openmp`, `v7_analitico`, `pp_mpi_estatico_np{1,2,4,8,16}`, `pp_mpi_dinamico_np{1,2,4,8,16}` y `pp_hibrido_{1x2,2x2,2x4,4x2,4x4,8x2}`; `v6_observado` «Not Run (Disabled)». Sin `-DPP_BUILD_MPI=ON` quedan solo las cuatro primeras. |
| Listar sin ejecutar | `ctest --test-dir build/docker -N` | `Total Tests: 21`. |
| V6 frente a lo observado (opcional) | `cmake -S . -B build/docker -DPP_V6_OBSERVADO=ON && ctest --test-dir build/docker -L v6_observado --output-on-failure` | **Falla hoy** en los estadísticos de cola: es un hallazgo documentado (`results/validacion/w0_v6_observado.log`), no un error del entorno. |
| Pytest unitarias | `PP_BIN_DIR=build/docker/src/backends PP_V6_GENERADOR=build/docker/pp_v6_generador python3 -m pytest -q tests/unit -k "not observado"` | Todas en verde salvo las 16 de V6 observado, que quedan `deselected`. Incluye las pruebas de scripts `test_medir_mpi.py`, `test_medir_hibrido.py`, `test_corrida_oficial.py`, `test_analizar_riesgo.py`, `test_sensibilidad.py`, `test_analizar_rendimiento.py` y `test_graficar_final.py`. |
| Pytest de integración | `PP_BIN_DIR=build/docker/src/backends python3 -m pytest -q tests/integration` | V1 serial frente a OpenMP (`test_openmp_equivalencia.py`) y `test_mpi.py`: V1, V3 (E2 termina limpio, cada trabajador recibe STOP) y V4 (la suma de `n_local` es N; dos corridas iguales coinciden) con 1, 2 y 4 procesos. Requiere `mpirun` en el `PATH`. |
| V5 sin carreras (Archer) | `docker run ... --security-opt seccomp=unconfined ... python3 -m pytest -v tests/concurrency` | 2/2: cero carreras y el control negativo detecta la suya ([evidencia](../results/evidencia/README.md)). |

> Sin `-k "not observado"`, `pytest tests/unit` ejecuta también V6 frente a lo observado y reporta 16 fallos esperados. Sin `PP_BIN_DIR`/`PP_V6_GENERADOR`, las pruebas que necesitan binarios se omiten en silencio (`skipped`): un verde sin esas variables no prueba los ejecutables.

## 5. Datos y calibración (T06–T10)

Las series `data/raw/` y las salidas `data/processed/` y `config/` están versionadas; regenerarlas solo comprueba que la tubería es reproducible. En `pp-g8`, en este orden:

| Paso | Comando | Escribe |
| --- | --- | --- |
| T08 auditoría | `python3 scripts/run/auditoria_datos.py` | `data/processed/auditoria_calidad.csv`, `docs/auditoria-datos.md` |
| T09 regímenes (ICEN, ENFEN) | `python3 scripts/run/clasificar_regimenes.py` | `data/processed/regimenes.csv` |
| T10 calibración y bootstrap | `python3 scripts/run/calibrar.py --semilla 20261015` | `data/processed/parametros.csv`, `bootstrap_parametros.csv` (100 réplicas por grupo), `calibracion_log.txt` |
| T10 configuraciones | `python3 scripts/run/generar_configs.py --commit $(git rev-parse --short HEAD)` | `data/processed/estaciones_seleccionadas.csv`, `config/<estacion>_<regimen>.yaml` (5 estaciones × 2 regímenes) |

Pase `--commit` desde el anfitrión: sin él, en un worktree el encabezado de los YAML queda `(commit desconocido)`. Comprobación: `git diff --ignore-cr-at-eol --stat` solo debe mostrar esa línea del encabezado; los parámetros, la auditoría y el bootstrap salen idénticos.

## 6. Mediciones de rendimiento

Protocolo común: misma `N`, semilla y configuración por comparación; una corrida de calentamiento que no cuenta y cinco repeticiones; V1 (`k`, `n` e histograma idénticos al secuencial) antes de calcular speedup. Valores por defecto: `N = 2 × 10⁷`, `config/sintetico.yaml`, semilla `20261015`.

### 6.1 T14 y T16: secuencial y OpenMP

```bash
# en pp-g8, tras compilar build/docker
python3 scripts/bench/medir_secuencial.py --build-dir build/docker --n 20000000 --repeticiones 5 --salida build/barrido/secuencial_t1.csv
python3 scripts/bench/medir_openmp.py --build-dir build/docker --n 20000000 --hilos 2,4,8,16 --schedules static,dynamic,64 --repeticiones 5 --salida build/barrido/openmp.csv
python3 scripts/bench/graficar_openmp_ashley.py --entrada build/barrido/openmp_resumen.csv --t1-csv build/barrido/secuencial_t1.csv \
  --agregado build/barrido/openmp_agregado.csv --figuras build/barrido/figuras --svg
```

`medir_openmp.py` escribe tres archivos: `openmp.csv` (una fila por corrida), `openmp_secuencial_ref.csv` y `openmp_resumen.csv` (una fila por punto, con `t1..t5`). El graficador necesita el formato **por punto**: el `results/bench/openmp.csv` versionado es ese resumen. Para publicar, copie `openmp_resumen.csv` → `results/bench/openmp.csv`, `secuencial_t1.csv` → `results/bench/` y vuelva a graficar sin `--entrada/--agregado/--figuras` (los valores por defecto apuntan a `results/`). Detalle en [protocolo-graficos-openmp.md](protocolo-graficos-openmp.md).

Todos los comandos de §6 y §7 se ejecutan **en `pp-g8`** (con `-e PP_COMMIT -e GIT_COMMIT`), tras compilar el build oficial `build/docker` con MPI (§3). Por ejemplo, desde Git Bash:

```bash
pp() { MSYS_NO_PATHCONV=1 docker run --rm --shm-size=1g -v "$PWD:/work" -w /work \
  -e PP_COMMIT=$(git rev-parse --short=12 HEAD) -e GIT_COMMIT=$(git rev-parse --short=12 HEAD) pp-g8 bash -c "$1"; }
pp 'python3 scripts/bench/medir_mpi.py --build-dir build/docker --procesos 2,4,8,16'
```

### 6.2 T21: MPI estático y dinámico

```bash
python3 scripts/bench/medir_mpi.py --build-dir build/docker --procesos 2,4,8,16 --dry-run   # solo imprime los comandos
python3 scripts/bench/medir_mpi.py --build-dir build/docker --procesos 2,4,8,16
```

Opciones: `--esquemas` (por defecto `mpi_estatico,mpi_dinamico`), `--n` (2e7), `--reps` (5), `--lote` (bloque de E2), `--bind-to` (`core`), `--t1-csv` / `--medir-t1`, `--timeout`, `--salida`. Escribe `results/bench/mpi.csv` (por corrida), `mpi_resumen.csv` (por punto, con speedup frente a T1, `eficiencia` y `eficiencia_computo`) y, si mide T1 aquí, `mpi_secuencial_ref.csv`. T1 se reutiliza de `results/bench/secuencial_t1.csv` cuando coinciden `N`, semilla, `config_id`, días y `k`. En E2 el rango 0 es el maestro y **no simula**: con P procesos trabajan P − 1 (columna `procesos_computo`).

### 6.3 T27: híbrido MPI + OpenMP

```bash
python3 scripts/bench/medir_hibrido.py --build-dir build/docker --presupuestos 2,4,8,16 --figura
```

Prueba todas las factorizaciones `procesos × hilos` de cada presupuesto (extremos incluidos), con `mpirun --bind-to none` y `OMP_PROC_BIND=false` por defecto (`--bind-to`, `--bind`, `--places`; razón en [contratos.md §6](contratos.md#6-log-de-verificación-mpi)). Escribe `results/bench/hibrido.csv`, `hibrido_resumen.csv` y, con `--figura`, `results/figures/hibrido_{speedup,eficiencia}.{png,svg}` (`--solo-figura` grafica un resumen existente).

### 6.4 X1–X3: barridos de escalabilidad y carga (T26, T30, T31)

```bash
# Ver el plan, los comandos exactos y la duración estimada antes de medir
python3 scripts/bench/ejecutar_barridos.py --experimento x1 --backend serial,openmp,mpi_estatico,mpi_dinamico,hibrido --build-dir build/docker --n 2e7 --dry-run

python3 scripts/bench/ejecutar_barridos.py --experimento x1 --backend serial,openmp,mpi_estatico,mpi_dinamico,hibrido --build-dir build/docker --n 2e7
python3 scripts/bench/ejecutar_barridos.py --experimento x2 --backend serial,openmp,mpi_estatico,mpi_dinamico,hibrido --build-dir build/docker --n 2.5e6
python3 scripts/bench/ejecutar_barridos.py --experimento x3 --backend serial,openmp,mpi_estatico,mpi_dinamico,hibrido --build-dir build/docker --recursos 8 --cargas 1e6,5e6,2e7
```

> Afinidad del híbrido en estos barridos: `ejecutar_barridos.py` lanza el híbrido con `--bind-to none`, pero su `--omp-bind` vale `close` por defecto. Según [contratos.md §6](contratos.md#6-log-de-verificación-mpi), esa combinación puede apilar hilos de procesos distintos en los mismos núcleos; la columna `afinidad` del CSV registra el valor usado. Para medir el híbrido con la afinidad recomendada, agregue `--omp-bind false`.

| Experimento | Qué varía | Por defecto |
| --- | --- | --- |
| `x1` (fuerte) | recursos 1/2/4/8/16 con `N` fijo | `N = 2e7` |
| `x2` (débil) | `N = n_base × recursos` | `n_base = 2.5e6` |
| `x3` (carga) | `N` en `--cargas` con recursos fijos | recursos 8 |

Recursos = hilos (OpenMP), procesos (MPI) o `p × h` (híbrido; solo las factorizaciones mixtas, filtrables con `--factorizaciones 2x8,4x4`). Salida: `results/bench/<experimento>.csv` y `.log` (`--salida`, `--log`, `--anexar`). Código de salida 2 si alguna fila no es equivalente (`equivalente = 0`): ese CSV no se usa.

### 6.5 T32: E1 frente a E2 en nodos heterogéneos

```bash
python3 scripts/bench/comparar_mpi_heterogeneo.py --n 2e5 --procesos 2 --reps 1 --build-dir build/docker --dry-run
python3 scripts/bench/comparar_mpi_heterogeneo.py --n 2e7 --procesos 4,8 --hosts nodo1:4,nodo2:4 --red-tcp eth0 --build-dir /opt/pp/build
```

Salidas: `--salida` (por defecto `results/bench/mpi_heterogeneo.csv`), `<salida>_resumen.csv` y `<salida>_resumen.md`. Con `--desde-csv a.csv,b.csv` solo resume CSV ya medidos. En un único anfitrión los «nodos» son iguales y se espera desbalance ≈ 1; la heterogeneidad real solo aparece en el clúster (§8.2).

### 6.6 T33 y T45: análisis de rendimiento y figuras finales

Después de las mediciones (leen lo que exista en `results/bench/`; cada entrada ausente se omite con un `AVISO`):

```bash
python3 scripts/bench/analizar-rendimiento.py
python3 scripts/bench/graficar-final.py
```

| Script | Entradas (por defecto) | Salidas |
| --- | --- | --- |
| `analizar-rendimiento.py` (`--bench`, `--salida`) | `results/bench/`: `secuencial_t1.csv`, `openmp.csv`, `mpi_resumen.csv`, `hibrido_resumen.csv`, `x1.csv`, `x2.csv`, `x3.csv` | `results/bench/analisis/rendimiento.{csv,md,tex}` (speedup, eficiencia, throughput, µs/escenario, Karp–Flatt, escalado débil) y `rendimiento_x3.csv` (ajuste `t = a + b·N`) |
| `graficar-final.py` (`--bench`, `--cientifico`, `--figuras`) | `results/bench/` y `results/cientifico/tablas/` | `results/figures/final_{speedup,eficiencia,karp_flatt,x2_debil,x3_tiempo,hibrido_factorizacion,e1_e2}.{png,svg}` y, si `analizar-riesgo.py`/`sensibilidad.py` no dejaron ya sus figuras, `final_riesgo_<estacion>` y `final_sensibilidad` |

Por eso `graficar-final.py` se ejecuta al final, después de §7.

## 7. Corridas científicas (X6, T35, X7)

Diseño: 10 configuraciones (`config/<estacion>_<regimen>.yaml`, 5 estaciones × normal/El Niño), umbral oficial `U` del YAML (50 mm) en X6 y `U ∈ {30, 50, 80}` mm en X7; cada punto usa la `semilla` y el `config_id` de su YAML (números aleatorios comunes entre capacidades). Los tres scripts comparten las opciones `--configs`, `--n`, `--backend {openmp,hibrido}` (por defecto `openmp`), `--hilos` (16), `--procesos` (2, solo híbrido, lanza `mpirun -np P --bind-to none`), `--build-dir` (`build/docker`), `--salida`, `--logs` (`results/cientifico/logs`), `--manifiesto` y `--dry-run`. Son **reanudables**: un punto (estación, régimen, `C`, `U`, `N`, parámetros) que ya está en el CSV se omite.

Comandos de la campaña oficial, en este orden (en `pp-g8`):

```bash
# T34 · X6: grilla de 17 capacidades (más la C de cada YAML), N = 1e7
python3 scripts/run/corrida-oficial.py --n 1e7 --backend openmp --hilos 16 --build-dir build/docker --capacidades 2,4,5,6,8,10,15,20,25,30,35,40,45,50,55,60,65

# T35 · banda epistémica: K = 100 réplicas bootstrap por estación × régimen, N = 1e6
python3 scripts/run/analizar-riesgo.py bootstrap --k 100 --n 1e6 --hilos 16 --build-dir build/docker --capacidades 2,4,6,8,10,15,20,30

# T35 · tablas y figuras de riesgo (desde x6.csv y bootstrap.csv)
python3 scripts/run/analizar-riesgo.py analizar

# T42 · X7: U = 30/50/80 mm con la C de cada YAML, más tablas y figuras
python3 scripts/run/sensibilidad.py --n 1e7 --hilos 16 --build-dir build/docker

# T33 y T45 (§6.6), con todo lo anterior ya escrito
python3 scripts/bench/analizar-rendimiento.py
python3 scripts/bench/graficar-final.py
```

Agregue `--dry-run` a cualquiera de las corridas para ver los puntos pendientes y sus comandos sin ejecutarlos.

| Tarea | Script y opciones propias | Salidas |
| --- | --- | --- |
| T34 · X6 | `corrida-oficial.py`: `--capacidades` (por defecto `2,3,4,5,6,7,8,9,10,12,15,20,25,30`), `--umbral` | `results/cientifico/x6.csv` (filas del contrato §5 con `hist512`), `x6_manifiesto.json` (commit, hardware, semillas y duración por punto), `logs/` |
| T35 · bootstrap | `analizar-riesgo.py bootstrap`: `--k` (100), `--bootstrap` (`data/processed/bootstrap_parametros.csv`), `--capacidades`, `--umbral`, `--dir-configs` (YAML temporales en `_build/bootstrap_configs`) | `results/cientifico/bootstrap.csv`, `bootstrap_manifiesto.json` |
| T35 · análisis | `analizar-riesgo.py analizar`: `--x6`, `--bootstrap-csv`, `--tablas`, `--figuras`, `--umbral`, `--capacidad-hist` (6 mm/día) | `results/cientifico/tablas/riesgo.{csv,md}`, `comparacion_enso.{csv,md}`, `results/figures/riesgo_<estacion>.{png,svg}`, `riesgo_comparacion_enso.{png,svg}`, `riesgo_hist_<estacion>.{png,svg}` |
| T42 · X7 | `sensibilidad.py`: `--umbrales` (`30,50,80`), `--capacidades` (opcional; por defecto la C del YAML), `--tablas`, `--figuras`, `--solo-analisis` (solo tablas y figuras desde `x7.csv`) | `results/cientifico/x7.csv`, `x7_manifiesto.json`, `tablas/sensibilidad.{csv,md}`, `results/figures/sensibilidad_<estacion>.{png,svg}`, `sensibilidad_resumen.{png,svg}` |

El IC de Wilson mide solo el error Monte Carlo; la banda bootstrap mide la incertidumbre de los parámetros calibrados. Advertencia V6: el generador subestima los extremos, así que estas probabilidades pueden subestimar el riesgo de inundación ([results/cientifico/README.md](../results/cientifico/README.md)).

## 8. Clúster con contenedores

### 8.1 Compose en un anfitrión: E1 y E2 (T22)

```bash
GIT_COMMIT=$(git rev-parse --short=12 HEAD) PP_N=2000000 PP_PROCESOS=2,3 PP_SLOTS=1 PP_REPS=5 \
  docker compose -f docker/compose.yaml up --abort-on-container-exit --exit-code-from nodo1
docker compose -f docker/compose.yaml down -v
```

`nodo1` compila en el volumen compartido `/opt/pp/build`, espera el sshd de `nodo2` y `nodo3` y lanza E1/E2 por ssh (`--mca btl tcp,self`). Variables: `PP_N`, `PP_PROCESOS`, `PP_SLOTS`, `PP_REPS`, `PP_LOTE`, `PP_CONFIG`, `GIT_COMMIT`. Salidas en `results/compose/` (ignorada por Git): `e1_estatico.{csv,log}`, `e2_dinamico.{csv,log}`, `e1_e2_comparacion_resumen.{csv,md}`. Los tres contenedores comparten la CPU: valida despliegue y equivalencia, no mide heterogeneidad.

### 8.2 Swarm en tres equipos (T25)

**Simulación en un anfitrión** (probada; no ejecuta `docker swarm init`):

```bash
PP_RED_DRIVER=bridge PP_N=200000 PP_PROCESOS=3,6 PP_HOSTS=nodo1:2,nodo2:2,nodo3:2 PP_REPS=1 \
  PP_RESULTADOS_HOST=../results/swarm-sim GIT_COMMIT=$(git rev-parse --short=12 HEAD) \
  docker compose -f docker/swarm-stack.yaml -p pp-swarm-sim up --abort-on-container-exit --exit-code-from nodo1
docker compose -f docker/swarm-stack.yaml -p pp-swarm-sim down -v
```

Equivale a `.\scripts\deploy\desplegar_swarm.ps1 -Accion simular -N 200000 -Procesos 3,6 -Reps 1`. Salidas en `results/swarm-sim/` con los mismos nombres que Compose.

**Clúster real** (pendiente de ejecución por el equipo): tres equipos con Docker Engine en la misma red, puertos 2377/tcp, 7946/tcp+udp y 4789/udp abiertos, y el repositorio en el **mismo camino absoluto y el mismo commit**.

| Paso | Dónde | Comando |
| --- | --- | --- |
| 1 | equipo 1 | `.\scripts\deploy\desplegar_swarm.ps1 -Accion iniciar -IpManager <ip_equipo1>` |
| 2 | equipos 2 y 3 | el `docker swarm join --token ... <ip_equipo1>:2377` que imprime el paso 1 |
| 3 | equipo 1 | `docker node ls` |
| 4 | equipo 1 | `.\scripts\deploy\desplegar_swarm.ps1 -Accion imagen -SshDestinos usuario@equipo2,usuario@equipo3` |
| 5 | equipo 1 | `.\scripts\deploy\desplegar_swarm.ps1 -Accion todo -Nodos <n1>,<n2>,<n3> -Repo <camino> -HostsMpi nodo1:8,nodo2:4,nodo3:4 -Procesos 4,8,16 -N 20000000 -Nucleos <total_fisicos>` |
| 6 | equipo 1 | revisar `<camino>/results/swarm/` |
| 7 | equipo 1 | `.\scripts\deploy\desplegar_swarm.ps1 -Accion retirar` (`-SalirDelSwarm` para dejar el modo Swarm) |

Ensaye cada paso con `-WhatIf`. Declare el CPU y los núcleos de cada equipo: slots de `-HostsMpi` ≤ núcleos físicos de cada uno, `-Nucleos` = su suma. La imagen lleva una clave SSH interna: no se publica en registros públicos.

## 9. Demo web de la exposición

```bash
# Requiere build/docker y build/docker-mpi compilados (§3)
docker run -d --name pp-g8-demo -p 8000:8000 -v "${PWD}:/work" -w /work pp-g8 python3 -u scripts/demo/servidor_demo.py
docker logs -f pp-g8-demo        # registro del backend
docker rm -f pp-g8-demo          # detener
```

Alternativa en el anfitrión: `uv run scripts/demo/servidor_demo.py` (cada corrida abre un contenedor `pp-g8`). Se abre en `http://127.0.0.1:8000`. La demo no escribe en el repositorio: usa un directorio temporal. Las figuras oficiales (`/api/openmp`) se leen de `results/bench/*.csv`.

### 9.1 T51: demostración en clúster con respaldo

[scripts/run/demo-cluster.ps1](../scripts/run/demo-cluster.ps1) (PowerShell, mismas convenciones que `desplegar_swarm.ps1`: `-Accion`, `-WhatIf`, `-Confirm`) reúne la demo web y una corrida E1/E2 en `-Destino compose`, `swarm-sim` o `swarm`:

| Momento | Comando | Efecto |
| --- | --- | --- |
| Día anterior | `.\scripts\run\demo-cluster.ps1 -Accion ensayo -Destino compose -N 2000000 -Procesos 2,3` | Corre E1/E2 y copia CSV, resúmenes y logs a `results/demo/respaldo/compose/` con `manifiesto.txt` (fecha, commit, parámetros). |
| Exposición | `.\scripts\run\demo-cluster.ps1 -Accion todo -Destino compose -N 2000000 -Procesos 2,3` | Levanta la demo web en `http://127.0.0.1:8000` y repite E1/E2; si la corrida falla, imprime el respaldo. |
| Si algo falla | `.\scripts\run\demo-cluster.ps1 -Accion mostrar -Destino compose` | Muestra el manifiesto y `e1_e2_comparacion_resumen.md` del respaldo, sin ejecutar nada. |
| Al terminar | `.\scripts\run\demo-cluster.ps1 -Accion detener` | Detiene el contenedor `pp-g8-demo`. |

Con `-Destino swarm` delega en `desplegar_swarm.ps1 -Accion todo` y necesita `-Nodos`, `-Repo`, `-HostsMpi` y, opcionalmente, `-Nucleos` (§8.2). Ensaye primero con `-WhatIf`. Los `.log` de `results/demo/` están en `.gitignore`: para versionar el respaldo, use `git add -f`.

## 10. Duraciones esperadas

Equipo de referencia: Intel Core Ultra 9 275HX, Docker Desktop sobre WSL2 con 24 vCPU.

| Paso | Duración | Fuente |
| --- | --- | --- |
| `docker build` de `pp-g8` | 5–15 min | depende de la red (paquetes apt); estimado |
| Configurar y compilar `build/docker` con MPI desde cero | ≈ 40 s | medido |
| `ctest` con MPI (20 pruebas) | ≈ 42 s | medido |
| Pytest unitarias / integración | ≈ 4 s / ≈ 1 s | medido |
| Tubería de datos T08–T10 | ≈ 3 s | medido |
| T14 secuencial (`N = 2e7`, 6 corridas) | ≈ 6 min | `results/evidencia/t14_medir_secuencial.log` |
| T16 OpenMP (3 schedules × 4 hilos + referencia) | ≈ 25 min | `results/evidencia/t16_medir_openmp.log` |
| T21 MPI (2 esquemas × 4 procesos) | ≈ 15 min | estimado (6 corridas por punto con speedup lineal) |
| T27 híbrido (14 factorizaciones) | ≈ 15 min | estimado (ídem) |
| X1 completo (5 backends, 25 puntos) | ≥ 57 min | `--dry-run` (ideal, speedup lineal) |
| X2 (4 backends) | ≥ 22 min | `--dry-run` |
| X3 (`--recursos 8 --cargas 1e6,5e6,2e7`) | ≥ 4 min | `--dry-run` con `--recursos 16`; con 8 recursos, mayor |
| Compose T22 (`N = 2e6`) | unos minutos | compilación + E1/E2 |
| Simulación Swarm (`N = 2e5`) | 1–3 min | compilación en tres volúmenes |
| X6 (10 configuraciones × 18 capacidades × 1e7) | ≈ 9–10 min | estimado con ≈ 0,31 µs/escenario (OpenMP, 16 hilos; [results/cientifico/README.md](../results/cientifico/README.md)) |
| Bootstrap T35 (100 réplicas × 10 configuraciones × 9 capacidades × 1e6) | ≈ 45–50 min | estimado (ídem) |
| X7 (10 configuraciones × 3 umbrales × 1e7) | ≈ 2 min | [results/cientifico/README.md](../results/cientifico/README.md) |
| `analizar-riesgo.py analizar`, `analizar-rendimiento.py`, `graficar-final.py` | segundos | sin simulación |

Las estimaciones de `--dry-run` usan 2,99 µs por escenario y speedup lineal: el tiempo real es mayor, en especial con 8 y 16 hilos (núcleos E). Los manifiestos `*_manifiesto.json` registran la duración real de cada punto científico.

## 11. Particularidades de Windows y del entorno

| Situación | Qué hacer |
| --- | --- |
| Git Bash traduce `/work` a una ruta de Windows | Anteponer `MSYS_NO_PATHCONV=1` a cada `docker run`. PowerShell no lo necesita. |
| CRLF en el clon de Windows | `.gitattributes` fuerza LF en `*.sh`, `*.yaml`, `*.yml` y `Dockerfile`. La imagen usa `core.autocrlf input`, así `git status` dentro del contenedor no marca todo como modificado. Compare con `git diff --ignore-cr-at-eol`. |
| Open MPI como root | La imagen define `OMPI_ALLOW_RUN_AS_ROOT=1` y `OMPI_ALLOW_RUN_AS_ROOT_CONFIRM=1`; fuera de la imagen hay que definirlas. |
| Memoria compartida entre rangos | `--shm-size=1g` en todo `docker run` que use MPI. |
| Híbrido | Siempre `mpirun --bind-to none`: con el anclaje por defecto, los hilos de cada rango comparten un núcleo. Los scripts ya lo hacen. |
| E2 (`pp_mpi_dinamico`) | El rango 0 solo reparte bloques y no simula: con P procesos trabajan P − 1. Compare eficiencias con esa salvedad. |
| Núcleos P y E | WSL2 expone 24 vCPU iguales; la afinidad ancla a vCPU, no a núcleos físicos. Toda medición declara esta limitación. |
| `git` en worktrees | Dentro del contenedor no resuelve el repositorio: pase `PP_COMMIT` y `GIT_COMMIT` (y `--commit` a `generar_configs.py`). |
| V5 | Requiere `--security-opt seccomp=unconfined`. |

## 12. Inventario de salidas

| Archivo | Lo produce | Versionado |
| --- | --- | --- |
| `data/processed/auditoria_calidad.csv`, `docs/auditoria-datos.md` | `auditoria_datos.py` | sí |
| `data/processed/regimenes.csv` | `clasificar_regimenes.py` | sí |
| `data/processed/parametros.csv`, `bootstrap_parametros.csv`, `calibracion_log.txt` | `calibrar.py` | sí |
| `data/processed/estaciones_seleccionadas.csv`, `config/<estacion>_<regimen>.yaml` | `generar_configs.py` | sí |
| `results/bench/secuencial_t1.csv` | `medir_secuencial.py` | sí |
| `results/bench/openmp.csv` (formato por punto) | `medir_openmp.py` (`openmp_resumen.csv`) | sí |
| `results/bench/openmp_agregado.csv`, `results/figures/openmp_{tiempo,speedup,eficiencia}.{png,svg}` | `graficar_openmp_ashley.py` | sí |
| `results/bench/mpi.csv`, `mpi_resumen.csv` | `medir_mpi.py` | al medir |
| `results/bench/hibrido.csv`, `hibrido_resumen.csv`, `results/figures/hibrido_*` | `medir_hibrido.py` | al medir |
| `results/bench/x1.csv`, `x2.csv`, `x3.csv` y `.log` | `ejecutar_barridos.py` | al medir |
| `results/bench/mpi_heterogeneo.csv`, `_resumen.csv`, `_resumen.md` | `comparar_mpi_heterogeneo.py` | al medir |
| `results/compose/*` | Compose T22 | no (`.gitignore`) |
| `results/swarm-sim/*` | simulación Swarm | no (`.gitignore`) |
| `results/swarm/*` | Swarm real | al ejecutar en el clúster |
| `results/cientifico/x6.csv`, `x6_manifiesto.json`, `logs/` | `corrida-oficial.py` | al correr |
| `results/cientifico/bootstrap.csv`, `bootstrap_manifiesto.json`, `tablas/riesgo.*`, `tablas/comparacion_enso.*`, `results/figures/riesgo_*` | `analizar-riesgo.py` | al correr |
| `results/cientifico/x7.csv`, `x7_manifiesto.json`, `tablas/sensibilidad.*`, `results/figures/sensibilidad_*` | `sensibilidad.py` | al correr |
| `results/bench/analisis/rendimiento.{csv,md,tex}`, `rendimiento_x3.csv` | `analizar-rendimiento.py` | al correr |
| `results/figures/final_*.{png,svg}` | `graficar-final.py` | al correr |
| `results/evidencia/*.log` | comandos de [results/evidencia/README.md](../results/evidencia/README.md) | sí |
| `results/validacion/*` | CTest y pytest de V1, V5, V6 y V7 | sí |

Esquemas de columnas: [reports/anexo-reproduccion.md](../reports/anexo-reproduccion.md) y [contratos.md §5](contratos.md#5-csv-de-resultados).

## 13. Lista de comprobación

- [ ] `docker build -t pp-g8 -f docker/Dockerfile .` termina sin errores.
- [ ] `ctest` con MPI: 20/20 y `v6_observado` deshabilitada.
- [ ] Pytest unitarias e integración en verde con `PP_BIN_DIR` y `PP_V6_GENERADOR` definidas.
- [ ] La tubería de datos reproduce `data/processed/` y `config/` salvo la línea del commit.
- [ ] Cada CSV de medición tiene `equivalente`/`equivalente_serial` = 1 y un commit distinto de `desconocido`.
- [ ] X6, bootstrap y X7 regenerados con `build/docker`, y `riesgo.md`/`sensibilidad.md` reescritos.
- [ ] `analizar-rendimiento.py` y `graficar-final.py` ejecutados al final, sin `AVISO` de entradas ausentes que se esperaban.
