# Inventario de GPU y decisión preliminar EXT1/EXT2 (T23)

**Responsable:** Lita (R4) · **Revisor:** David (R1) · **Primera consulta:** 15/10/2026 · **Actualización:** 19/11/2026 · **Alimenta a:** T29 (decisión CUDA, `docs/decision-cuda.md`) y T38–T41

Este inventario registra lo comprobado con comandos en los equipos disponibles. La decisión sobre EXT1/EXT2 está en T29 (`docs/decision-cuda.md`); aquí solo se resume en el §5.

## 1. Equipos revisados

| Equipo | Integrante | GPU | Memoria | CC | SM | Controlador | CUDA Toolkit (`nvcc`) | Acceso desde Linux | Fecha |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| PC de Lita: Windows 11 Pro (compilación 26300), i5-12400F 6C/12T, 15,8 GB RAM | Lita | NVIDIA GeForce RTX 4060 (AD107), modo **WDDM**, también muestra el escritorio | 8188 MiB | 8.9 (Ada Lovelace) | **24** (medido) | 621.01 (CUDA 13.5 como máximo) | **CUDA 13.3** en WSL Ubuntu-24.04 (`/usr/local/cuda`); CUDA 13.4 también instalado en Windows | Sí: WSL2 Ubuntu 24.04.5, kernel 6.18.58.1, ve la GPU por `/usr/lib/wsl/lib` | 19/11/2026 |
| [PC de referencia](guia-reproduccion.md#pc-de-referencia) (equipo de Miguel): Core Ultra 9 275HX (8P + 16E, 24 hilos), 63 GB de RAM, Windows 11 + WSL2 + Docker Desktop | Miguel | NVIDIA GeForce RTX 5090 Laptop, modo WDDM, muestra el escritorio | 24 GB | 12.0 (Blackwell) | Sin medir | 617.42 | No instalado en el anfitrión | Sin comprobar | 26/10/2026 (consulta tomada de `decision-cuda.md`) |
| Equipos de Angela, Ashley, David y Rhamses | — | Sin dato | — | — | — | — | — | — | Pendiente: cada uno ejecuta el §2 y agrega su fila o anota «sin GPU NVIDIA» |

## 2. Comandos ejecutados y salida resumida (PC de Lita, 19/11/2026)

```text
> nvidia-smi --query-gpu=name,memory.total,driver_version,compute_cap,pcie.link.gen.max,pcie.link.width.max,clocks.max.sm,power.limit,driver_model.current --format=csv
NVIDIA GeForce RTX 4060, 8188 MiB, 621.01, 8.9, 4, 8, 3105 MHz, 115.00 W, WDDM

> nvidia-smi            # cabecera
NVIDIA-SMI 621.01   KMD Version: 621.01   CUDA UMD Version: 13.5
GPU 0: NVIDIA GeForce RTX 4060  WDDM  Disp.A: On  868MiB / 8188MiB en uso por el escritorio

$ wsl -d Ubuntu-24.04 -- /usr/local/cuda/bin/nvcc --version
Cuda compilation tools, release 13.3, V13.3.73

$ wsl -d Ubuntu-24.04 -- ls /usr/local/cuda/bin      # herramientas disponibles para T39/T40
compute-sanitizer  ncu  nvcc  ...

$ wsl -d Ubuntu-24.04 -- uname -r ; grep PRETTY /etc/os-release
6.18.58.1-microsoft-standard-WSL2
Ubuntu 24.04.5 LTS

$ wsl -d Ubuntu-24.04 -- mpirun --version ; nproc ; free -g
mpirun (Open MPI) 4.1.6      # para EXT2 fuera de Docker
12                           # hilos lógicos visibles en WSL
Mem: 7 GB                    # límite por defecto de WSL (la mitad de la RAM del anfitrión)

> docker version --format '{{.Server.Version}}'
29.8.2                       # Docker Desktop sobre WSL2; la imagen pp-g8 no incluye CUDA
```

Consulta del dispositivo con un programa propio compilado con `nvcc -arch=sm_89` en WSL y `cudaGetDeviceProperties`:

```text
nombre=NVIDIA GeForce RTX 4060   cc=8.9   sm=24   mem_mib=8187
max_hilos_bloque=1024   max_hilos_sm=1536   max_bloques_sm=24   shared_bloque_kib=48   warp=32
runtime=13030 (CUDA 13.3)   driver=13050 (CUDA 13.5)
```

El mismo ejecutable pasa `compute-sanitizer --tool memcheck` («ERROR SUMMARY: 0 errors») y `--tool racecheck` («0 hazards»). Esto solo comprueba que la cadena de herramientas funciona: el programa no lanza kernels propios, así que **no** sustituye a V8 (T39).

## 3. Restricciones observadas

1. **GPU compartida con el escritorio (WDDM).** Los tiempos tendrán ruido de la interfaz gráfica (868 MiB ya ocupados por el escritorio) y Windows aplica el *watchdog* TDR (≈ 2 s por defecto) a los kernels largos. El kernel de T38 debe lanzarse por lotes acotados, no con N = 10⁸ en una sola llamada.
2. **24 SM y el barrido X5.** Cada bloque se ejecuta en un solo SM, así que las configuraciones de 2/4/8/16 bloques que pide el cronograma usan como máximo 16 de los 24 SM: **ninguna llena la GPU**. Para no concluir que la GPU es lenta, X5 añade un punto de referencia con la grilla completa (múltiplos de 24 bloques, hasta la ocupación máxima de 1536 hilos por SM) y registra la ocupación observada (`ncu`). Un bloque no equivale a un núcleo.
3. **Memoria de WSL.** WSL tiene 7 GB visibles. No afecta al kernel (la memoria de la GPU es aparte), pero limita compilaciones y corridas grandes en CPU dentro de WSL. Si hace falta, se sube en `%UserProfile%\.wslconfig`.
4. **Docker con GPU no preparado.** La imagen `pp-g8` no incluye el toolkit. EXT1 se desarrolla y valida en WSL nativo. Para EXT2 hay dos caminos: MPI nativo en WSL (Open MPI 4.1.6 ya está instalado) con un trabajador GPU en este mismo equipo, o una imagen con CUDA y NVIDIA Container Toolkit si la GPU tuviera que entrar en Swarm.
5. **Precisión.** El contrato fija `-fmad=false` y una diferencia relativa ≤ 10⁻⁶ en el conteo (V2). La CC 8.9 soporta doble precisión, pero con un rendimiento FP64 bajo frente a FP32 en una GPU de consumo; hay que medirlo en T40 antes de sacar conclusiones.
6. **Dos versiones del toolkit.** Hay CUDA 13.3 en WSL y 13.4 en Windows. Todas las compilaciones y mediciones del proyecto usan el de WSL (13.3) y lo registran en el CSV.

## 4. Cambios respecto de la consulta del 15/10/2026

| Dato | 15/10/2026 | 19/11/2026 |
| --- | --- | --- |
| Controlador | 572.83 (CUDA 12.8) | 621.01 (CUDA 13.5) |
| `nvcc` | No instalado | CUDA 13.3 en WSL; 13.4 en Windows |
| Distribución WSL | Ubuntu (anotada como 26.04) | Ubuntu-24.04 (24.04.5 LTS), la que usa el proyecto |
| SM | 24, según la ficha técnica | 24, medido con `cudaGetDeviceProperties` |
| Docker | No instalado | Docker Desktop 29.8.2 |
| RTX 5090 Laptop de la PC de referencia | No figuraba | Agregada con su consulta del 26/10 |

## 5. Decisión preliminar y alternativa CPU

**Fecha:** 19/11/2026. **Decisión vigente (T29):** CUDA se desarrolla como extensión desacoplada sobre la RTX 4060 de Lita, que es el único equipo con `nvcc` operativo.

| Extensión | Estado | Requisito previo | Situación al 19/11 |
| --- | --- | --- | --- |
| **EXT1** (kernel CUDA, reducción, V2/V8, barrido X5) | En desarrollo | CUDA Toolkit en WSL y `nvcc` compilando un caso de prueba | **Cumplido.** Se puede empezar T38. |
| **EXT2** (GPU como trabajador MPI en E2) | En desarrollo, después de EXT1 | EXT1 validada con V2/V8 | Pendiente de EXT1. Puede ejecutarse en este mismo equipo (CPU + GPU) sin el clúster de T25. |

**Alternativa CPU:** si EXT1 no pasa V2 y V8, no se publican cifras de GPU y **todas las campañas (X1–X3, X6, X7) siguen en CPU** con los backends secuencial, OpenMP, MPI E1/E2 e híbrido, que no dependen de la GPU. La RTX 5090 Laptop de la PC de referencia queda como respaldo: necesitaría CUDA 12.8 o posterior (CC 12.0) y no se usa mientras la 4060 esté operativa, para no mezclar hardware en X5.
