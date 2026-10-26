# Inventario de GPU y decisión preliminar EXT1/EXT2 (T23)

**Responsable:** Lita (R4) · **Revisor:** David (R1) · **Fecha de consulta:** 15/10/2026 · **Alimenta a:** T29 (decisión CUDA, S10)

Este inventario registra lo que se comprobó con comandos en los equipos disponibles. La decisión final de activar EXT1/EXT2 la toma T29; aquí solo hay una propuesta preliminar con su alternativa CPU.

## 1. Equipos revisados

| Equipo | Integrante | GPU | Memoria | Compute capability | Controlador (CUDA máx.) | CUDA Toolkit (`nvcc`) | Acceso desde Linux |
| --- | --- | --- | --- | --- | --- | --- | --- |
| PC de Lita (Windows 11 Pro, i5-12400F 6C/12T, 15,8 GB RAM) | Lita | NVIDIA GeForce RTX 4060 (AD107, modo WDDM, también muestra el escritorio) | 8188 MiB | 8.9 (Ada Lovelace) | 572.83 (CUDA 12.8) | **No instalado** (ni en Windows ni en WSL) | Sí: WSL2 Ubuntu 26.04 ve la GPU (`/usr/lib/wsl/lib/libcuda.so`, `nvidia-smi`) |
| Equipos de los demás integrantes | Angela, Ashley, David, Miguel, Rhamses | Pendiente | — | — | — | — | — |

Datos no medidos aquí y tomados de la ficha técnica de NVIDIA para la RTX 4060: **24 SM** (3072 núcleos CUDA, 128 por SM). Deben confirmarse con `deviceQuery` o `cudaGetDeviceProperties` cuando se instale el toolkit (T38).

Para completar la tabla, cada integrante ejecuta los comandos de la sección 2 y agrega su fila en este archivo.

## 2. Comandos ejecutados y salida resumida

```text
> nvidia-smi --query-gpu=name,memory.total,driver_version,compute_cap,pcie.link.gen.max,pcie.link.width.max,clocks.max.sm,power.limit --format=csv
NVIDIA GeForce RTX 4060, 8188 MiB, 572.83, 8.9, 4, 8, 3105 MHz, 115.00 W

> nvidia-smi            # cabecera
NVIDIA-SMI 572.83   Driver Version: 572.83   CUDA Version: 12.8
GPU 0: NVIDIA GeForce RTX 4060  WDDM  Disp.A: On  730MiB / 8188MiB en uso por el escritorio

> where nvcc ; $env:CUDA_PATH ; dir "C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA"
(sin resultados: el toolkit no está instalado)

$ wsl -d Ubuntu -- /usr/lib/wsl/lib/nvidia-smi --query-gpu=name,memory.total,driver_version,compute_cap --format=csv,noheader
NVIDIA GeForce RTX 4060, 8188 MiB, 572.83, 8.9
$ wsl -d Ubuntu -- command -v nvcc      # → no instalado
$ uname -r                               # → 6.6.87.2-microsoft-standard-WSL2
```

Docker no está instalado en este equipo (ni Docker Desktop ni dentro de WSL), dato relevante para T25 y EXT2.

## 3. Restricciones observadas

1. **GPU compartida con el escritorio (WDDM).** Los tiempos tendrán ruido de la interfaz gráfica y Windows aplica el *watchdog* TDR a kernels largos (≈ 2 s por defecto). El kernel de T38 debe lanzarse por lotes acotados, no con N = 10⁸ en una sola llamada.
2. **Sin toolkit.** Antes de T38 hay que instalar el CUDA Toolkit 12.x para WSL-Ubuntu (requiere `sudo`) o en Windows con MSVC. Se recomienda WSL: es el mismo entorno Linux donde ya compila y se mide el proyecto (T16, T17).
3. **Una sola GPU conocida.** Mientras no aparezcan otras, EXT2 tendría un único nodo GPU y su comparación CPU frente a CPU+GPU dependerá de que este equipo participe en el clúster de T25.
4. **Docker con GPU no preparado.** Para EXT2 dentro de Swarm haría falta Docker Engine y NVIDIA Container Toolkit en este equipo, además de declarar la GPU como recurso del nodo.
5. **Precisión.** El contrato fija `-fmad=false` y una diferencia relativa ≤ 10⁻⁶ en el conteo (V2). La capacidad 8.9 soporta doble precisión, aunque con un rendimiento FP64 bajo frente a FP32 en GPU de consumo; hay que medirlo en T40 antes de concluir.

## 4. Decisión preliminar (a confirmar en T29)

| Extensión | Propuesta | Condición para mantenerla | Alternativa si no se cumple |
| --- | --- | --- | --- |
| **EXT1** (kernel CUDA, reducción, V2/V8, barrido de bloques) | **Go condicionado** | Toolkit instalado y `nvcc` compilando un caso de prueba antes del inicio de S11 (03/11/2026); E4 y E5 cerrados sin retraso. | Descartar EXT1 y dedicar S11–S12 a reforzar X1–X3 y la comparación MPI heterogénea (T32) solo con CPU. |
| **EXT2** (GPU como trabajador MPI en E2) | **No-go provisional** | Reconsiderar solo si EXT1 pasa V2/V8 y el Swarm de T25 funciona con este equipo como nodo. | Comparar E1/E2 en CPU heterogéneas (T32) y documentar el reparto que tendría la GPU como trabajo futuro. |

Las tareas T38–T41 permanecen «No iniciado» hasta el acta de T29 (`docs/decision-cuda.md`).
