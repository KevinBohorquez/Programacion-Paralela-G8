# Decisión sobre la extensión CUDA (T29)

**Responsable:** David (R1) · **Insumo:** inventario GPU de Lita (T23, rama `origin/lita`, `docs/inventario-gpu.md`) · **Fecha:** 26/10/2026 (cierre de S10) · **Decisión:** **NO-GO**: EXT1 y EXT2 no se activan.

## 1. Contexto

La definición del proyecto (`docs/definicion-proyecto.docx`, «Puerta de extensiones») establece que CUDA es una extensión desacoplada del núcleo MPI + OpenMP. EXT1 (kernel, reducción en memoria compartida, V2, V8 y X5) y EXT2 (nodo GPU como trabajador MPI en E2) se activan solo si se cumplen dos condiciones al cerrar E5 en S10:

1. Los entregables E1–E5 tienen evidencias técnicas completas.
2. Se dispone de una GPU NVIDIA utilizable con el CUDA Toolkit.

El inventario T23 propuso «Go condicionado» para EXT1 con una condición adicional: `nvcc` instalado y compilando un caso de prueba antes del inicio de S11 (03/11/2026), con E4 y E5 cerrados sin retraso. EXT2 quedó como «No-go provisional».

## 2. Criterios y evidencia

### 2.1 Criterio E1–E5 (núcleo al día)

Las definiciones de E1–E3 están en `docs/plan-desarrollo-semana-8.md` y las de E4–E5 en `docs/plan-desarrollo-semana-15.md`.

| Entregable | Evidencia exigida | Evidencia en el repositorio | ¿Cumple? |
| --- | --- | --- | --- |
| E1 Estructura | Definición, contratos, estructura, inventario de datos, Docker/CI mínimos | `docs/contratos.md`, `CMakeLists.txt`, `results/evidencia/t04_ctest.log`, `t05_hello_*.log` | Sí |
| E2 Secuencial | Resultados reproducibles; V6/V7 y T1 con archivos de evidencia | `results/bench/secuencial_t1.csv`, `results/evidencia/t14_medir_secuencial.log`, V7 en `tests/unit/test_analitico.py`. La V6 con datos observados sigue en diagnóstico. | Parcial |
| E3 OpenMP | Conteos conservados; V1/V5 y barrido 2/4/8/16 con CSV y gráficos | `results/bench/openmp.csv`, `results/bench/openmp_agregado.csv`, `results/figures/openmp_*`, `results/evidencia/t17_v5_archer.log` | Sí |
| E4 MPI | E1/E2, V1/V3/V4 y matriz de procesos 2/4/8/16 | Código y pruebas CTest (`results/evidencia/t04_ctest_mpi.log`); el barrido T21 no está medido aún | Parcial |
| E5 Híbrido | Swarm multinodo, matriz procesos × hilos y decisión de extensiones | `pp_hibrido` con pruebas 1×2 … 8×2 (`src/backends/hybrid/CMakeLists.txt`); el Swarm en tres equipos y la matriz T27 están pendientes | Parcial |

**Resultado:** el criterio no se cumple. E2, E4 y E5 no tienen todavía las evidencias completas.

### 2.2 Disponibilidad de GPU y toolkit

| Equipo | GPU | Modo del controlador | `nvcc` | Observación |
| --- | --- | --- | --- | --- |
| PC de Lita | RTX 4060, 8 GB, CC 8.9 | WDDM (también muestra el escritorio) | No instalado en Windows ni en WSL | Inventario T23, §1–§2 |
| PC de Miguel | RTX 5090 Laptop, 24 GB, CC 12.0 (controlador 617.42) | WDDM, con la GPU mostrando el escritorio | No instalado en el anfitrión | Consulta `nvidia-smi` del 26/10/2026 |
| Imagen `pp-g8` (todas las mediciones) | — | — | No incluida | `docker run --rm pp-g8 sh -c 'command -v nvcc'` no devuelve ruta |

**Resultado:** hay hardware, pero no hay un entorno CUDA operativo. En los dos equipos la GPU trabaja en modo WDDM. Windows aplica el *watchdog* TDR (≈ 2 s) a los kernels largos y la interfaz gráfica introduce ruido en los tiempos (inventario T23, §3.1). Usar CUDA dentro de `pp-g8` exigiría una imagen nueva con el toolkit y NVIDIA Container Toolkit en Docker Desktop. Ese entorno no está preparado ni probado.

### 2.3 Calendario

La condición del inventario T23 (`nvcc` compilando un caso de prueba antes del 03/11/2026) no se cumplió: ningún equipo tiene el toolkit instalado al cierre de S10. Las semanas S11–S13 se necesitan para completar E4–E5 (barridos MPI e híbrido, Swarm, X1–X3, X6 y X7). La definición prohíbe que una extensión retrase el núcleo.

## 3. Decisión

**NO-GO para EXT1 y EXT2.** No se implementa CUDA en esta entrega. Se aplica la alternativa prevista en el inventario T23, §4: S11–S12 se dedican a reforzar X1–X3 y la comparación MPI heterogénea (T32) solo con CPU.

Esta decisión deja la pertinencia de la GPU (rúbrica, criterio 1) como argumento del informe y no como implementación. El informe debe justificar que la GPU es pertinente para Monte Carlo y explicar por qué no se activó, con la evidencia de §2.

## 4. Consecuencias

| Elemento | Estado | Tratamiento |
| --- | --- | --- |
| T38 kernel CUDA, T39 reducción y pruebas, T40 barrido de bloques, T41 integración CPU + GPU | **No activado** | Se registran como no activados en el cronograma; no cuentan como pendientes del núcleo. |
| V2 (equivalencia GPU) y V8 (compute-sanitizer) | **No activado** | No se ejecutan; el informe las declara fuera de alcance por esta decisión. |
| X5 (barrido 2/4/8/16 bloques × 128/256/512 hilos por bloque) | **No activado** | Sin CSV ni figuras; no se publican cifras de GPU. |
| EXT2 (GPU como trabajador MPI en E2) | **No activado** | El reparto heterogéneo se estudia solo con CPU (T32). |
| Archivos reservados `src/backends/cuda/*`, `include/cuda.hpp`, `scripts/bench/medir_cuda.py`, `tests/concurrency/test_cuda.py` | Se conservan como marcadores | Cada uno tiene una sola línea que remite a este documento. No contienen código. |
| Compilación | Sin cambios | `PP_BUILD_CUDA` vale `OFF` por defecto en `CMakeLists.txt`, así que `src/backends/cuda` no entra en el build. Aunque se active, su `CMakeLists.txt` solo tiene un comentario y no define objetivos. |

### Condiciones para revisar la decisión

El equipo puede revertirla si, antes del congelamiento de código (S13), se cumplen todas estas condiciones:

1. E4 y E5 cerrados con evidencias.
2. CUDA Toolkit 12.8 o posterior (necesario para CC 12.0) compilando un kernel de prueba en WSL2.
3. Kernel por lotes acotados, para respetar el TDR de WDDM.
4. V2 y V8 planificadas con tiempo de medición.

En ese caso, Philox ya es una función pura (`src/core/philox_rng.cpp`). Basta marcarla `__host__ __device__` para reutilizar el mismo flujo aleatorio en la GPU (`docs/evaluacion-ashley-E3.md`, punto 7).
