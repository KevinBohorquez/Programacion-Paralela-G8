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
| T38 kernel CUDA, T39 reducción y pruebas, T40 barrido de bloques, T41 integración CPU + GPU | En desarrollo |
| Archivos `src/backends/cuda/*`, `include/cuda.hpp`, `scripts/bench/medir_cuda.py`, `tests/concurrency/test_cuda.py` | Marcadores de una línea; todavía no contienen código. |
| Compilación | `PP_BUILD_CUDA` vale `OFF` por defecto en `CMakeLists.txt`; `src/backends/cuda/CMakeLists.txt` todavía no define objetivos. |
