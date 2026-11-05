# Ejecución de las campañas por otro equipo o agente

Esta guía es para quien clone la rama y quiera ejecutar las pruebas, las mediciones y las corridas científicas en su propio equipo, a mano o con un agente de código (Claude Code, Codex u otro). El detalle de cada script está en la [guía de reproducción](docs/guia-reproduccion.md); aquí solo va el orden, las reglas y lo que hay que entregar.

## 1. Requisitos

- Docker (Docker Desktop en Windows o macOS, Docker Engine en Linux). No hace falta GPU: CUDA quedó descartado ([decisión](docs/decision-cuda.md)).
- No hace falta Python, CMake ni compilador en el anfitrión: todo corre dentro de la imagen `pp-g8`.
- Al menos 16 núcleos físicos para reproducir la matriz completa 2/4/8/16. Con menos, ver §4.

## 2. Reglas para el agente

1. **No hacer `git push`, abrir PR ni fusionar.** Solo commits locales; la publicación la decide una persona del equipo.
2. **Una sola máquina por campaña.** T1, M1, M2 y X1–X3 se miden en el mismo equipo. No mezclar tiempos de equipos distintos en un mismo informe.
3. **Medir T1 primero en el equipo propio.** `medir_mpi.py` y `medir_hibrido.py` reutilizan `results/bench/secuencial_t1.csv`; si queda el T1 de otro equipo, el speedup sale mal.
4. **Anfitrión en reposo durante las mediciones.** Antes de cada paso cronometrado, `docker ps` no debe mostrar otros contenedores que `pp-g8`. No compilar, correr pruebas ni levantar otros proyectos en paralelo. Una medición con interferencia se descarta (coeficiente de variación alto, speedup menor que 1 con 2 procesos).
5. **Pasos en secuencia, nunca en paralelo.** Cada paso usa todos los núcleos.
6. **Registrar el commit.** En Git Bash de Windows, anteponer `MSYS_NO_PATHCONV=1` a `docker run`. En un worktree, pasar `-e PP_COMMIT=... -e GIT_COMMIT=...` (ver [README](README.md)).
7. **No inventar resultados.** Si un paso falla, se informa el error y la salida; no se completan CSV a mano.

## 3. Orden de ejecución

Definir el atajo (Git Bash o Linux, desde la raíz del repositorio):

```bash
docker build -t pp-g8 -f docker/Dockerfile .
C=$(git rev-parse --short=12 HEAD)
D() { MSYS_NO_PATHCONV=1 docker run --rm --shm-size=1g -e PP_COMMIT="$C" -e GIT_COMMIT="$C" -v "$PWD:/work" -w /work pp-g8 bash -c "$1"; }
```

| # | Paso | Comando | Duración de referencia* |
|---|------|---------|-------------------------|
| 1 | Compilar | `D "cmake -S . -B build/docker -DCMAKE_BUILD_TYPE=Release -DPP_BUILD_MPI=ON && cmake --build build/docker -j"` | < 1 min |
| 2 | Pruebas | `D "ctest --test-dir build/docker --output-on-failure"`<br>`D "python3 -m pytest -q tests/unit"`<br>`D "PP_BIN_DIR=build/docker/src/backends python3 -m pytest -q tests/integration"` | pocos minutos |
| 3 | T1 propio | `D "python3 scripts/bench/medir_secuencial.py --build-dir build/docker"` | ~6 min |
| 4 | M1 · MPI E1/E2 | `D "python3 scripts/bench/medir_mpi.py --build-dir build/docker --procesos 2,4,8,16"` | ~40 min |
| 5 | M2 · híbrido | `D "python3 scripts/bench/medir_hibrido.py --build-dir build/docker --presupuestos 2,4,8,16 --figura"` | ~45 min |
| 6 | X1 · fuerte | `D "python3 scripts/bench/ejecutar_barridos.py --experimento x1 --backend serial,openmp,mpi_estatico,mpi_dinamico,hibrido --build-dir build/docker --n 2e7"` | ~70 min |
| 7 | X2 · débil | igual con `--experimento x2 --n 2.5e6` | ~30 min |
| 8 | X3 · carga | igual con `--experimento x3 --recursos 8 --cargas 1e6,5e6,2e7` (sin `--n`) | ~15 min |
| 9 | X6 · riesgo | `D "python3 scripts/run/corrida-oficial.py --n 1e7 --backend openmp --hilos 16 --build-dir build/docker --capacidades 2,4,5,6,8,10,15,20,25,30,35,40,45,50,55,60,65"` | — |
| 10 | X7 · sensibilidad | `D "python3 scripts/run/sensibilidad.py --n 1e7 --hilos 16 --build-dir build/docker"` | — |
| 11 | Bootstrap | `D "python3 scripts/run/analizar-riesgo.py bootstrap --k 100 --n 1e6 --hilos 16 --build-dir build/docker --capacidades 2,4,6,8,10,15,20,30"` | — |
| 12 | Análisis de riesgo | `D "python3 scripts/run/analizar-riesgo.py analizar"` | < 1 min |
| 13 | Análisis y figuras finales | `D "python3 scripts/bench/analizar-rendimiento.py && python3 scripts/bench/graficar-final.py"` | < 1 min |

\* Medidas en un Intel Core Ultra 9 275HX (8P + 16E, sin SMT) con Docker Desktop sobre WSL2. «—» indica que aún no hay referencia.

Antes de los pasos 6–8 se puede añadir `--dry-run` para ver el plan y la duración estimada sin medir.

## 4. Equipos con menos de 16 núcleos

Recortar las listas al número de núcleos físicos (por ejemplo `--procesos 2,4,8` y `--presupuestos 2,4,8` en un equipo de 8 núcleos) y bajar `--hilos` en los pasos 9–11. Los puntos por encima de los núcleos físicos quedan marcados como sobresuscritos en el CSV y no sirven como escalabilidad.

## 5. Qué entregar

- CSV y registros en `results/bench/`, `results/cientifico/` y `results/evidencia/`, y figuras en `results/figures/`.
- Un commit local por campaña con mensaje convencional, por ejemplo `chore(T21,T27): versionar las matrices MPI e híbrida medidas en <equipo>`.
- Un resumen con el equipo usado (CPU, núcleos, RAM, sistema), la salida de las pruebas del paso 2 y cualquier paso fallido o descartado con su motivo.
