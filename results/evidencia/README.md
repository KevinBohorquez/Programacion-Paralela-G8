# Evidencia de ejecución (semana 8)

Registros versionados de las corridas que respaldan las tareas de la semana 8.
Cada log empieza con una cabecera: comando exacto, fecha UTC, commit, id de la imagen `pp-g8`,
`nproc` dentro del contenedor y versión del compilador. Si el commit aparece con
"árbol con cambios sin commit", el log se generó antes de versionar la propia evidencia.

## Índice

| Archivo | Tarea | Qué demuestra | Resultado |
|---|---|---|---|
| `t05_hello_hibrido.log` | T05 | La imagen compila y ejecuta un hola MPI + OpenMP: 2 rangos × 2 hilos con `MPI_THREAD_FUNNELED` en un contenedor. | Correcto |
| `t05_hello_dos_contenedores.log` | T05 | El mismo hola con un rango en `nodo1` y otro en `nodo2` (Compose, TCP). | Correcto |
| `t04_ctest.log` | T04, T15, T17 (V1) | Compilación Release desde cero dentro del contenedor y `ctest`: `smoke` y `v1_equivalencia_openmp`. | 2/2 pruebas aprobadas |
| `t04_ctest_mpi.log` | T04 (trabajo `mpi` de la CI) | Compilación con `PP_BUILD_MPI=ON` y `ctest`: smoke, V1, MPI estático/dinámico con 1/2/4/8/16 procesos e híbrido. | 18/18 pruebas aprobadas |
| `t17_v5_archer.log` | T17 (V5) | V5 local (ThreadSanitizer + Archer) con el mismo comando de la CI: código real y control negativo con una carrera deliberada. | 2/2 aprobadas: 0 carreras en el código; el control negativo detecta su carrera |
| `t17_v5_archer_detalle.log` | T17 (V5) | Salida del detector copiada de `build/v5_archer.log`. | 0 advertencias de ThreadSanitizer |
| `t07_validar_cronograma.log` | T07 | `validar_cronograma.py` revisa T01–T53 en `cronograma/cronograma-interno.xlsx`. | Correcto |

V5 también pasa en la CI (ver abajo): el paso "V5 sin carreras (ThreadSanitizer + Archer)" terminó en
`success` y su log quedó como artefacto `v5-archer-log` de esa corrida. La imagen local necesita
`libclang-rt-18-dev` (runtime de TSan), que el runner de GitHub ya incluye.

## Integración continua (T04)

Corrida [38819186557](https://github.com/KevinBohorquez/Programacion-Paralela-G8/actions/runs/38819186557)
sobre `master` en el commit `2734c1f`: trabajos `construir-y-probar` (Debug, smoke + V1 + V5) y `mpi`
(V1, V3 y V4 con 1/2/4/8/16 procesos), ambos en verde.

## Cómo regenerar

Desde la raíz del repositorio en Git Bash (en PowerShell, sin `MSYS_NO_PATHCONV` y con `"${PWD}:/work"`):

```bash
# t04_ctest.log
MSYS_NO_PATHCONV=1 docker run --rm --shm-size=1g -v "$PWD:/work" -w /work pp-g8 bash -c \
  'cmake --fresh -S . -B build/docker -DCMAKE_BUILD_TYPE=Release && cmake --build build/docker --parallel && ctest --test-dir build/docker --output-on-failure'

# t04_ctest_mpi.log
MSYS_NO_PATHCONV=1 docker run --rm --shm-size=1g -v "$PWD:/work" -w /work pp-g8 bash -c \
  'cmake --fresh -S . -B build/docker-mpi -DCMAKE_BUILD_TYPE=Release -DPP_BUILD_MPI=ON && cmake --build build/docker-mpi --parallel && ctest --test-dir build/docker-mpi --output-on-failure'

# t17_v5_archer.log (deja además el detalle en build/v5_archer.log → t17_v5_archer_detalle.log)
MSYS_NO_PATHCONV=1 docker run --rm --shm-size=1g --security-opt seccomp=unconfined -v "$PWD:/work" -w /work pp-g8 bash -c \
  'python3 -m pytest -v tests/concurrency'

# t07_validar_cronograma.log
MSYS_NO_PATHCONV=1 docker run --rm -v "$PWD:/work" -w /work pp-g8 python3 scripts/validar_cronograma.py

# t05_*.log
bash docker/hello_hibrido.sh
```

## Equipo

Intel Core Ultra 9 275HX (8 núcleos P + 16 núcleos E, sin SMT), Docker Desktop sobre WSL2 con 24 vCPU.
Las cabeceras registran `nproc` = 24 dentro del contenedor. Qué hilo cae en un núcleo P o E no es
controlable desde el contenedor (ver `docker/README.md`).
