# Decisión sobre la extensión CUDA (T29)

**Responsable de la decisión:** equipo, con David (R1) · **Ejecución:** Lita (R4), tareas T38–T41 · **Insumo:** inventario GPU (T23, `docs/inventario-gpu.md`) · **Fecha de revisión:** 05/11/2026 · **Decisión:** CUDA se incluye en el proyecto como extensión en desarrollo.

## 1. Decisión

El equipo decidió incluir CUDA en el proyecto. La extensión está diseñada y aprobada, y se encuentra en desarrollo: todavía no hay kernels implementados, compilados ni medidos. Mientras tanto, los backends de CPU (secuencial, OpenMP, MPI estático, MPI dinámico e híbrido) siguen siendo la base de todas las campañas y no dependen de la GPU.

La definición del proyecto (`docs/definicion-proyecto.docx`, «Puerta de extensiones») mantiene CUDA como extensión desacoplada del núcleo MPI + OpenMP: la extensión no modifica el núcleo ni retrasa sus entregables.

## 2. Alcance

El desarrollo sigue dos etapas, en este orden.

| Etapa | Contenido | Resultado esperado |
| --- | --- | --- |
| **EXT1** | Kernel con un hilo por escenario, Philox en la GPU y reducción del conteo en memoria compartida. Barrido de bloques × hilos por bloque (X5). | Conteos equivalentes a la CPU, validados con V2 y V8. |
| **EXT2** | La GPU como trabajador MPI del esquema E2 (maestro–trabajador), junto con los trabajadores CPU. Es el nivel objetivo «todo en uno». | Comparación de CPU sola frente a CPU + GPU con carga fija. |

EXT2 empieza solo cuando EXT1 pase V2 y V8.

## 3. Requisitos previos

1. Instalar el CUDA Toolkit 12.x en WSL2 (Ubuntu) en el PC con la RTX 4060. Se elige WSL porque es el mismo entorno Linux donde ya compila y se mide el proyecto.
2. Comprobar que `nvcc` compila y ejecuta un caso de prueba en ese equipo.
3. Para la RTX 5090 Laptop (CC 12.0) hace falta el CUDA Toolkit 12.8 o posterior, si se usa ese equipo.

## 4. Plan y esfuerzo estimado

| Paso | Contenido | Esfuerzo aproximado |
| --- | --- | --- |
| 1 | Philox en el dispositivo (marcar la función pura de `src/core/philox_rng.cpp` como `__host__ __device__`) y simulación de una temporada en la GPU. | 2–3 días |
| 2 | Kernel por lotes acotados, para respetar el *watchdog* TDR de WDDM, y reducción en memoria compartida. | 2 días |
| 3 | Integración de CMake con el lenguaje CUDA (`PP_BUILD_CUDA`) y validación V2 (diferencia relativa ≤ 10⁻⁶) y V8. | 1–2 días |
| 4 | Barrido de bloques × hilos por bloque (X5: 2/4/8/16 bloques × 128/256/512 hilos por bloque). | 1–2 días |
| EXT2 | GPU como trabajador MPI de E2 y comparación CPU frente a CPU + GPU. | ≈ 1 semana adicional |

## 5. Criterios de aceptación

| Prueba | Criterio |
| --- | --- |
| V2 (equivalencia GPU) | Diferencia relativa del conteo ≤ 10⁻⁶ frente a la CPU con el mismo problema y la misma semilla, compilando con `-fmad=false`. |
| V8 (memoria y carreras GPU) | Cero errores de `compute-sanitizer` (memcheck y racecheck). |

No se publican cifras de GPU hasta que V2 y V8 pasen.

## 6. Hardware disponible

| Equipo | GPU | Modo del controlador | `nvcc` | Observación |
| --- | --- | --- | --- | --- |
| PC de Lita | RTX 4060, 8 GB, CC 8.9 | WDDM (también muestra el escritorio) | Pendiente de instalar en WSL | Equipo previsto para EXT1 (inventario T23, §1–§2) |
| PC de Miguel | RTX 5090 Laptop, 24 GB, CC 12.0 (controlador 617.42) | WDDM, con la GPU mostrando el escritorio | No instalado en el anfitrión | Consulta `nvidia-smi` del 26/10/2026 |
| Imagen `pp-g8` (mediciones actuales) | — | — | No incluida | Las campañas actuales son solo CPU |

## 7. Restricciones técnicas

1. **WDDM y TDR.** En los dos equipos la GPU trabaja en modo WDDM. Windows aplica el *watchdog* TDR (≈ 2 s) a los kernels largos, así que el kernel se lanza por lotes acotados y no con N = 10⁸ en una sola llamada. La interfaz gráfica introduce ruido en los tiempos (inventario T23, §3.1).
2. **Docker con GPU.** Usar CUDA dentro de `pp-g8` exige una imagen con el toolkit y NVIDIA Container Toolkit. EXT1 se desarrolla y valida en WSL; la imagen con GPU se prepara para EXT2.
3. **Precisión.** El contrato fija `-fmad=false` y la tolerancia de V2. La CC 8.9 soporta doble precisión con un rendimiento FP64 bajo frente a FP32; se mide en X5 antes de concluir.
4. **Un bloque no es un núcleo.** En X5 se registran SM y ocupación observada; una configuración de 16 bloques no equivale a «16 núcleos CUDA».

## 8. Riesgos

| Riesgo | Mitigación |
| --- | --- |
| La instalación del toolkit en WSL falla o se retrasa. | Es el primer paso del plan; sin `nvcc` operativo no se inicia el kernel y las campañas CPU siguen sin cambios. |
| El TDR de WDDM aborta kernels largos. | Lotes acotados por lanzamiento (paso 2). |
| V2 no alcanza ≤ 10⁻⁶ por diferencias de punto flotante. | `-fmad=false`, mismo flujo Philox que la CPU y comparación por lotes para localizar la divergencia. |
| Ruido en los tiempos por el escritorio en la misma GPU. | Repeticiones, registro del hardware y declaración explícita del modo WDDM junto a cada medición. |
| EXT2 depende de que el equipo con GPU participe en el Swarm. | EXT2 empieza solo con EXT1 validada; el reparto heterogéneo con CPU (T32) no depende de la GPU. |
| La extensión compite con el tiempo del núcleo. | La extensión es desacoplada: no bloquea la entrega de los backends de CPU. |

## 9. Estado del repositorio

| Elemento | Estado |
| --- | --- |
| T38 kernel CUDA | **Hecho (19/11/2026, rama `lita-cuda`).** Núcleo compartido CPU/GPU en `include/nucleo_hd.hpp` (`__host__ __device__`; la CPU sigue idéntica bit a bit), kernel con un hilo por escenario, paso de grilla, lotes de 2²⁰ escenarios y reducción de k y del histograma en memoria compartida (`src/backends/cuda/kernel.cu`), ejecutable `pp_cuda` y prueba `v2_cuda` en CTest. |
| V2 | **Pasa.** En la RTX 4060 (CC 8.9, CUDA 13.3, `-fmad=false`), con 4 casos (κ = ∞, κ = 2, α > 1 con κ = 0,7 y Tumbes El Tigre normal) × 3 grillas (48×256, 2×128, 16×512) y N = 10⁶: k y las 512 clases del histograma son **idénticos** a la CPU (diferencia relativa 0). Escenario por escenario, amax coincide bit a bit en ≈ 85 % y difiere como máximo en 4·10⁻¹² relativo (log/cos/pow de la GPU). La igualdad exacta de k y del histograma es **empírica, no garantizada**: basta que un amax distinto en la última cifra quede en otro lado de U o de un borde de clase para que difieran. El criterio formal de la GPU es la tolerancia de V2 (≤ 10⁻⁶, `include/nucleo_hd.hpp`). Evidencia: `results/validacion/t38_v2_cuda.txt`. Con N = 10⁷ en Tumbes El Tigre normal, `pp_cuda` da el mismo k que X6 H5 en CPU (3 038 980). |
| T39 reducción y pruebas | **Hecho (19/11/2026).** Reducción en dos niveles en `src/backends/cuda/reduccion.cuh`: contadores de 32 bits por bloque en memoria compartida (un lote de 2²⁰ escenarios no los desborda) y suma de 64 bits a la memoria global; el resultado no depende de la grilla. V2 agrega bordes con igualdad exacta frente a la CPU: n = 1, más hilos que escenarios, bloques sin trabajo, 32 hilos por bloque, el máximo admitido y cortes de lote en 2²⁰ + 1 y 1,5 · 2²⁰. `tests/concurrency/test_cuda.py` compara `pp_cuda` con `pp_serial` por el CSV (4 configuraciones × 3 grillas: `k` e `hist512` idénticos), `--progreso` y argumentos inválidos. |
| V8 | **Pasa.** `compute-sanitizer` (2026.2.1) con memcheck (`--leak-check full`), racecheck, initcheck y synccheck sobre `pp_cuda`, con H5 (κ = 2), grilla automática (N = 2·10⁴) y bloques/hilos sin trabajo (777 escenarios, 200 × 512): 0 errores y 0 *hazards*. Control negativo: las mismas herramientas detectan un acceso fuera de rango y una carrera en memoria compartida en kernels defectuosos a propósito. Evidencia: `results/validacion/t39_v8_cuda.txt`; en CTest, `ctest -L v8`. |
| Procedencia de V2/V8 | Según su cabecera, `t38_v2_cuda.txt` y `t39_v8_cuda.txt` se generaron antes del commit de T39 (base `1bb2974` con cambios sin commit). Ese commit (`134a5a0`) cambió el código CUDA (`kernel.cu`, `reduccion.cu`/`reduccion.cuh`, `include/cuda.hpp`) y sus pruebas (`tests/unit/v2_cuda.cpp`, `tests/concurrency/test_cuda.py`, `src/backends/cuda/CMakeLists.txt`), y `kernel.cu` e `include/cuda.hpp` volvieron a cambiar en T40 (`a79c998`) y T41 (`b88d25e`). **Pendiente:** regenerar ambas evidencias con GPU sobre el commit final de la rama. |
| Límite de hilos por bloque | El kernel usa 94 registros por hilo, así que en CC 8.9 admite como máximo 640 hilos por bloque (94 × 1024 supera los 65 536 registros del SM). Con más, `pp_cuda` termina con código 2 y un mensaje claro. X5 usa 128/256/512, que caben. Con 256 hilos caben 2 bloques por SM (48 en total), lo que se analiza en T40. |
| T40 barrido X5 | **Hecho (19/11/2026).** `scripts/bench/medir_cuda.py`; datos en `results/bench/lita_i5-12400F/cuda*.csv` y figura `results/figures/cuda_x5.png`. El tiempo depende solo de los SM usados (2/4/8/16 bloques = 2/4/8/16 SM, escalado ≥ 99 %), no de los hilos por bloque; la GPU llena es 10,6× T1 y 2,3× OpenMP con 6 núcleos. SM y ocupación observados con un lanzamiento instrumentado (Nsight Compute sin permiso de contadores). Análisis: `docs/resultados-cuda.md` §1. |
| T41 EXT2 (GPU como trabajador MPI) | **Hecho (19/11/2026).** `pp_mpi_dinamico_gpu` (`src/backends/cuda/trabajador_mpi.cpp`): E2 sin cambios de protocolo, con el último rango procesando cada bloque en la GPU. V3 pasa y V1 bit a bit (`--verificar`) pasó en CTest `ext2_*` y en las 36 corridas medidas; esa igualdad es empírica, no garantizada (ver V2: el criterio formal de la GPU es la tolerancia 10⁻⁶). Con 6 procesos, 4 CPU + GPU es 3,2× E2 solo CPU y 12,1× T1; la cola dio el 75 % a la GPU (96 % de la suma ideal). Datos: `cuda_ext2*.csv`, figura `cuda_ext2.png`, análisis en `docs/resultados-cuda.md` §2. |
| T43 registro de integración | Insumos listos para David: PR de `lita-cuda`, `PP_BUILD_CUDA=OFF` por defecto (el CI sin GPU no cambia: `test_cuda.py` se omite), V2/V8 en `results/validacion/`, X5 y EXT2 en `docs/resultados-cuda.md`. |
| Compilación | `PP_BUILD_CUDA` vale `OFF` por defecto. Con `ON` necesita `nvcc`; la imagen Docker no trae CUDA, así que se compila en WSL con `scripts/cuda/compilar_wsl.sh` (`--probar` corre `ctest -L cuda`: V2, V2 de ejecutables y los 8 casos de V8). |
