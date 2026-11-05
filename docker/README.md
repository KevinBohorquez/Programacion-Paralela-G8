# Imagen Docker del proyecto (T05)

La imagen `pp-g8` contiene solo la cadena de herramientas (Ubuntu 24.04, igual que la CI):
CMake, g++, clang + libomp (Archer para V5), Open MPI 4.1, Python 3 con pytest, matplotlib y scipy, y git.
El código no se copia: se monta en `/work` al ejecutar, así cada corrida usa el árbol actual.

## Construir

Desde la raíz del repositorio (el contexto queda vacío gracias a `.dockerignore`):

```bash
docker build -t pp-g8 -f docker/Dockerfile .
```

## Ejecutar con el repositorio montado

La ruta del repositorio tiene espacios y tildes: siempre entre comillas.

Git Bash (`MSYS_NO_PATHCONV=1` evita que Git Bash traduzca `/work` a una ruta de Windows):

```bash
MSYS_NO_PATHCONV=1 docker run --rm -it --shm-size=1g -v "$PWD:/work" -w /work pp-g8
```

PowerShell:

```powershell
docker run --rm -it --shm-size=1g -v "${PWD}:/work" -w /work pp-g8
```

Dentro del contenedor, por ejemplo:

```bash
cmake -S . -B build/docker -DCMAKE_BUILD_TYPE=Release   # build/ está en .gitignore
cmake --build build/docker --parallel
```

Opciones necesarias según la tarea:

| Caso | Opción |
|---|---|
| MPI (memoria compartida entre rangos) | `--shm-size=1g` |
| V5 con ThreadSanitizer/Archer | `--security-opt seccomp=unconfined` |

La imagen ya define `OMPI_ALLOW_RUN_AS_ROOT=1` y `OMPI_ALLOW_RUN_AS_ROOT_CONFIRM=1` (se ejecuta como root)
y configura git con `core.autocrlf input` y `safe.directory '*'`: el clon de Windows tiene CRLF
y, sin eso, `git status` dentro del contenedor marcaría todo como modificado.

## Hola híbrido MPI + OpenMP

`hello_hibrido.cpp` inicia MPI con `MPI_THREAD_FUNNELED`, comprueba el nivel provisto y cada rango
abre una región OpenMP. El rango 0 imprime las líneas ordenadas por (rango, hilo).

Un contenedor (2 rangos × 2 hilos):

```bash
MSYS_NO_PATHCONV=1 docker run --rm --shm-size=1g -v "$PWD:/work" -w /work -e OMP_NUM_THREADS=2 pp-g8 \
  bash -c 'mpicxx -fopenmp -O2 -o /tmp/hello_hibrido docker/hello_hibrido.cpp && mpirun -np 2 --bind-to none /tmp/hello_hibrido'
```

Dos contenedores (un rango en `nodo1` y otro en `nodo2`, lanzados por ssh y comunicados por TCP):

```bash
docker compose -f docker/compose-hello.yaml run --rm nodo1
docker compose -f docker/compose-hello.yaml down -v
```

Para regenerar la evidencia de ambas variantes (con comando, fecha, imagen y commit en la cabecera):

```bash
bash docker/hello_hibrido.sh
```

Escribe `results/evidencia/t05_hello_hibrido.log` y `results/evidencia/t05_hello_dos_contenedores.log`.

> `compose-hello.yaml` es solo para T05. Las corridas E1/E2 con Compose son T22 (`compose.yaml`).
> La clave SSH se genera dentro de la imagen y solo sirve para la red interna de compose; no publiques la imagen.

## Sala de control de la demo

El servidor de la sala de control corre en un contenedor `pp-g8` en el puerto 8765: ver [docs/demo-sala-control.md](../docs/demo-sala-control.md) y `scripts/run/demo-sala.ps1` (o `demo-sala.sh`).

## Advertencia de hardware

El equipo de medición es un Intel Core Ultra 9 275HX: 8 núcleos P + 16 núcleos E, sin SMT.
Docker Desktop corre sobre WSL2 y expone 24 vCPU; `OMP_PROC_BIND`/`OMP_PLACES` y `mpirun --bind-to`
fijan hilos a vCPU de la máquina virtual, no a núcleos físicos. Qué hilo cae en un núcleo P o E
no es controlable desde el contenedor, así que toda medición debe declarar esta limitación.

## E1 y E2 con Compose (T22)

`compose.yaml` levanta `nodo1`, `nodo2` y `nodo3`. `nodo1` compila una sola vez en el volumen
compartido `binarios` (`/opt/pp/build`, el mismo camino en los tres), espera el sshd de los otros
dos y ejecuta `docker/nodo_mpi.sh lanzador`: E1 y E2 con `scripts/bench/ejecutar_barridos.py`
(mpirun por ssh, `--mca btl tcp,self`) y la comparación de `scripts/bench/comparar_mpi_heterogeneo.py`.

```bash
GIT_COMMIT=$(git rev-parse --short=12 HEAD) PP_N=2000000 PP_PROCESOS=2,3 PP_SLOTS=1 PP_REPS=5 \
  docker compose -f docker/compose.yaml up --abort-on-container-exit --exit-code-from nodo1
docker compose -f docker/compose.yaml down -v
```

Escribe en `results/compose/`: `e1_estatico.csv`, `e2_dinamico.csv`, `e1_e2_comparacion_resumen.{csv,md}`
y los `.log`. `GIT_COMMIT` se pasa desde el anfitrión porque dentro del contenedor git no siempre ve
el repositorio (por ejemplo, en un worktree). Lo leen los scripts de medición; los simuladores leen
`PP_COMMIT`, que `nodo_mpi.sh` toma de `GIT_COMMIT` si no se define y reenvía a todos los rangos con
`mpirun -x PP_COMMIT`, de modo que la columna `commit` del CSV de cada simulador también es correcta.
Los contenedores comparten la CPU del anfitrión: sirve para
validar el despliegue y la equivalencia de k, no para medir nodos heterogéneos.

## Ejecutor de barridos X1–X3 (T26)

Dentro del contenedor, con un build Release que incluya MPI:

```bash
cmake -S . -B build/docker -DCMAKE_BUILD_TYPE=Release -DPP_BUILD_MPI=ON && cmake --build build/docker --parallel
python3 scripts/bench/ejecutar_barridos.py --experimento x1 --backend openmp --recursos 1,2 --n 2e5 --reps 1 --dry-run
```

`--dry-run` imprime cada punto, su comando exacto y la duración estimada. El híbrido se lanza siempre
con `mpirun --bind-to none` (con el enlazado por defecto los hilos de cada rango comparten un núcleo).

## Swarm en tres equipos (T25)

`swarm-stack.yaml` define un servicio por equipo (`nodo1`, `nodo2`, `nodo3`), fijado con la etiqueta
de nodo `pp_nodo=1|2|3`, en una red overlay con subred fija (`PP_SUBRED`, por defecto `10.77.0.0/24`;
Open MPI usa ese CIDR en `btl_tcp_if_include` porque en Swarm el orden eth0/eth1 no es fijo).
Cada equipo compila el mismo commit en su volumen local `/opt/pp`; `nodo2` y `nodo3` dejan sshd
y `nodo1` lanza E1/E2 con `PP_HOSTS` (slots por equipo, p. ej. `nodo1:8,nodo2:4,nodo3:4`).

### Simulación en un solo anfitrión (probada)

No usa `docker swarm init` (no cambia el modo del Docker local). Compose ignora `deploy:` y la red pasa a bridge:

```bash
PP_RED_DRIVER=bridge PP_N=200000 PP_PROCESOS=3,6 PP_HOSTS=nodo1:2,nodo2:2,nodo3:2 PP_REPS=1 \
  PP_RESULTADOS_HOST=../results/swarm-sim \
  docker compose -f docker/swarm-stack.yaml -p pp-swarm-sim up --abort-on-container-exit --exit-code-from nodo1
docker compose -f docker/swarm-stack.yaml -p pp-swarm-sim down -v
```

Equivale a `scripts/deploy/desplegar_swarm.ps1 -Accion simular -N 200000 -Procesos 3,6 -Reps 1`.

### Lo que el equipo debe ejecutar en el clúster real (no probado aquí)

Requisitos: tres equipos en la misma red con Docker Engine (Linux o WSL2 con Docker nativo; Docker
Desktop dificulta los bind mounts entre nodos), puertos 2377/tcp, 7946/tcp+udp y 4789/udp abiertos,
y el repositorio clonado en el MISMO camino absoluto y en el MISMO commit en los tres.

| Paso | Dónde | Comando |
|---|---|---|
| 1 | equipo 1 | `.\scripts\deploy\desplegar_swarm.ps1 -Accion iniciar -IpManager <ip_equipo1>` |
| 2 | equipos 2 y 3 | el `docker swarm join --token ... <ip_equipo1>:2377` que imprime el paso 1 |
| 3 | equipo 1 | `docker node ls` para ver los nombres de los tres nodos |
| 4 | equipo 1 | `.\scripts\deploy\desplegar_swarm.ps1 -Accion imagen -SshDestinos usuario@equipo2,usuario@equipo3` (o `docker build` en cada equipo) |
| 5 | equipo 1 | `.\scripts\deploy\desplegar_swarm.ps1 -Accion todo -Nodos <n1>,<n2>,<n3> -Repo <camino> -HostsMpi nodo1:8,nodo2:4,nodo3:4 -Procesos 4,8,16 -N 20000000 -Nucleos <total_fisicos>` |
| 6 | equipo 1 | revisar `<camino>/results/swarm/` (CSV de E1/E2, resumen y logs de servicios) |
| 7 | equipo 1 | `.\scripts\deploy\desplegar_swarm.ps1 -Accion retirar` (`-SalirDelSwarm` para volver al modo normal) |

Todos los pasos aceptan `-WhatIf` para ver qué se ejecutaría. Las mediciones deben declarar el modelo de CPU
y los núcleos de cada equipo (`-HostsMpi` con slots ≤ núcleos físicos de cada uno; `-Nucleos` = su suma).
La imagen lleva la clave SSH interna: distribúyala solo entre los equipos del grupo (nunca a un registro público).
