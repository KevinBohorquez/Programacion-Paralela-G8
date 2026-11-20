# Resultados de la extensión CUDA: X5 (T40) y EXT2 (T41)

**Responsable:** Lita (R4) · **Revisores:** R6 (T40), David R1 (T41) · **Fecha:** 19/11/2026 · **Rama:** `lita-cuda`
**Equipo:** Intel Core i5-12400F (6 núcleos físicos, 12 lógicos, sin núcleos E), 7,7 GiB visibles en WSL2,
NVIDIA GeForce RTX 4060 (CC 8.9, 24 SM, 8 GiB, controlador 621.01), CUDA 13.3 en WSL Ubuntu-24.04, Open MPI 4.1.6.
Todo se midió en este mismo equipo y sesión (regla 2 de `AGENTS.md`), con T1 propio.

Las cifras de GPU se publican porque V2 y V8 pasan (`docs/decision-cuda.md`, `results/validacion/t38_v2_cuda.txt`
y `t39_v8_cuda.txt`). En **todos** los puntos de este documento, k y el histograma de 512 clases resultaron idénticos al
secuencial. Es una igualdad observada, no garantizada: el criterio formal de la GPU es la tolerancia de V2 (≤ 10⁻⁶).

## 1. X5 · bloques × hilos por bloque (T40)

**Datos:** `results/bench/lita_i5-12400F/cuda.csv` (una fila por corrida) y `cuda_resumen.csv` (una por punto),
registro en `cuda_log.txt`, figura `results/figures/cuda_x5.png`. **Script:** `scripts/bench/medir_cuda.py`.
**Carga:** `config/sintetico.yaml`, N = 10⁷, semilla 20261015, calentamiento + 5 repeticiones por punto; commit
`a79c998`. El tiempo es el `tiempo_s` del CSV: reserva de memoria en el dispositivo, cómputo, reducción y copia del resultado, sin crear el contexto CUDA. La reserva (`cudaMalloc`) entra porque `MotorCuda` se construye dentro de `simular_cuda`, que se llama dentro de la región medida (`src/backends/cuda/main.cpp`); no se midió por separado, pero frente a 4,3–34,4 s se espera despreciable.
Todos los puntos tienen CV < 2 %.

| Grilla | SM usados (observados) | Ocupación observada por SM | Tiempo medio (s) | Speedup frente a T1 | Frente a OpenMP 6 hilos |
| --- | --- | --- | --- | --- | --- |
| T1 `pp_serial` | — | — | 30,38 | 1,00 | 0,21 |
| OpenMP, 6 hilos (`static`) | — | — | 6,49 | 4,68 | 1,00 |
| 2 × 128 / 2 × 256 / 2 × 512 | 2 | 8 % / 17 % / 33 % | 34,36 / 34,15 / 34,14 | 0,88 / 0,89 / 0,89 | 0,19 |
| 4 × 128 / 4 × 256 / 4 × 512 | 4 | 8 % / 17 % / 33 % | 17,19 / 17,16 / 17,11 | 1,77 / 1,77 / 1,78 | 0,38 |
| 8 × 128 / 8 × 256 / 8 × 512 | 8 | 8 % / 17 % / 33 % | 8,64 / 8,59 / 8,56 | 3,52 / 3,54 / 3,55 | 0,75 |
| 16 × 128 / 16 × 256 / 16 × 512 | 16 | 8 % / 17 % / 33 % | 4,31 / 4,25 / 4,25 | 7,04 / 7,15 / 7,14 | 1,50–1,53 |
| 24 × 128 (1 bloque por SM) | 24 | 8 % | 2,87 | 10,59 | 2,26 |
| 120 × 128 (máximo residente: 5 por SM) | 24 | 42 % | 2,89 | 10,51 | 2,25 |
| 48 × 256 (máximo residente: 2 por SM) | 24 | 33 % | **2,85** | **10,67** | **2,28** |
| 24 × 512 (máximo residente: 1 por SM) | 24 | 33 % | 2,88 | 10,55 | 2,25 |

«Ocupación observada» es la fracción de los 1536 hilos de un SM que estuvieron residentes a la vez, medida con un
lanzamiento instrumentado (`%smid` y `%globaltimer` por bloque). En todos los puntos coincidió con la teórica de la
API de ocupación de CUDA. Nsight Compute no se pudo usar: en este equipo no tiene permiso para leer los contadores
de la GPU (`ERR_NVGPUCTRPERM`, se habilita desde el panel de NVIDIA con permisos de administrador).

### Lectura

1. **El tiempo depende solo de cuántos SM trabajan.** Cada bloque corre en un SM; con 2, 4, 8 y 16 bloques se usan
   2, 4, 8 y 16 de los 24 SM, y el tiempo baja a la mitad cada vez que se duplican los bloques (34,4 → 17,2 → 8,6 →
   4,3 s; eficiencia de escalado ≥ 99 %). Los hilos por bloque no cambian nada: 128, 256 y 512 dan el mismo tiempo.
2. **Un SM se satura con un bloque de 128 hilos.** Con 24 × 128 (8 % de ocupación) el tiempo es el mismo que con
   la ocupación máxima posible (42 %). El kernel calcula en doble precisión (Box–Muller, `log`, `pow`, gamma) y la
   RTX 4060 tiene pocas unidades FP64 por SM (≈ 1/64 del rendimiento FP32): con 4 *warps* por SM esas unidades ya
   están ocupadas, y más hilos solo esperan. Por eso **un bloque no equivale a un núcleo** y «16 bloques» no es
   comparable con «16 hilos» de CPU (`docs/decision-cuda.md` §7).
3. **Un SM rinde 0,44 de un núcleo de CPU** en este problema (≈ 145 000 escenarios/s por SM frente a 329 000 de un
   núcleo del i5-12400F con `pp_serial`). Con 2 bloques la GPU es más lenta que T1 (0,88×); recién con 16 bloques
   supera a OpenMP con 6 núcleos.
4. **La GPU completa es 10,6 veces T1 y 2,3 veces OpenMP con 6 núcleos.** Ninguna configuración del barrido pedido
   (2/4/8/16 bloques) llena la GPU, como se había previsto en `docs/inventario-gpu.md` §3; las filas con 24 o más
   bloques son la referencia de la GPU llena.
5. **Límite de registros.** El kernel usa 94 registros por hilo: admite hasta 640 hilos por bloque y, con 256, solo
   2 bloques por SM (ocupación máxima 33 %). No se forzó un tope de registros (`__launch_bounds__`) porque, según el
   punto 2, más ocupación no aceleraría el kernel.

**Para el informe:** el barrido pedido mide «cuántos SM se usan», no «cuántos hilos». La figura `cuda_x5.png` muestra el
speedup por bloques (izquierda) y el rendimiento en función de los SM observados (derecha), donde las tres
curvas de hilos por bloque caen sobre la misma recta.

## 2. EXT2 · la GPU como trabajador MPI de E2 (T41)

**Datos:** `results/bench/lita_i5-12400F/cuda_ext2.csv` y `cuda_ext2_resumen.csv`, registro en `cuda_ext2_log.txt`
(incluye el trabajo de cada rango), figura `results/figures/cuda_ext2.png`. **Script:** `scripts/bench/medir_cpu_gpu.py`.
**Ejecutable:** `pp_mpi_dinamico_gpu` (`src/backends/cuda/trabajador_mpi.cpp`). **Carga:** `config/sintetico.yaml`,
N = 10⁷, semilla 20261015, bloques de la cola de 62 500 escenarios (el valor por defecto de E2), grilla de la GPU
24 × 128 (la más rápida de X5 con menos hilos), calentamiento + 5 repeticiones; commit `b88d25e`; `mpirun --bind-to none`.

### Diseño

- Es el mismo E2 de David (maestro en el rango 0, mensajes REQ/WORK/STOP, cobertura exacta de la cola). El único
  cambio es que el **último rango** procesa cada bloque `[i0, i1)` con un lanzamiento del kernel de EXT1 en lugar de
  recorrerlo en la CPU. Para eso E2 recibe una función por bloque (`esquema_dinamico_bloques`); `pp_mpi_dinamico` usa
  la de siempre y su comportamiento no cambia (las 16 pruebas MPI y del híbrido siguen pasando).
- Como la GPU usa el mismo núcleo y el mismo contador Philox que la CPU, el resultado salió **idéntico bit a bit** al
  secuencial: `--verificar` (V1) pasa con la GPU en la cola (pruebas `ext2_*` de CTest). Es una igualdad empírica:
  log/cos/pow de la GPU pueden diferir en la última cifra (≈ 15 % de los amax en V2), así que no está garantizada.
- El contexto CUDA se crea antes de `MPI_Init`, fuera del tiempo medido (0,14–0,18 s; queda en el CSV), y el rango
  GPU espera al kernel con `cudaDeviceScheduleBlockingSync`, así que duerme en lugar de ocupar un núcleo.

### Resultados

| Variante | Procesos (trabajadores) | Tiempo medio (s) | CV | Speedup frente a T1 | Frente a «E2 CPU» | Escenarios hechos por la GPU |
| --- | --- | --- | --- | --- | --- | --- |
| T1 `pp_serial` | 1 | 28,71 | 0,5 % | 1,00 | 0,26 | — |
| E2 CPU | 6 (5 CPU) | 7,57 | 1,2 % | 3,79 | 1,00 | — |
| `pp_cuda` 24 × 128, sin MPI | 1 | 2,85 | 1,4 % | 10,08 | 2,66 | 100 % |
| E2 solo GPU | 2 (1 GPU) | 3,00 | 1,2 % | 9,58 | 2,53 | 100 % (160 bloques) |
| **E2 CPU + GPU** | **6 (4 CPU + 1 GPU)** | **2,37** | 1,7 % | **12,12** | **3,20** | **75 %** (120 de 160 bloques) |
| E2 CPU + GPU | 7 (5 CPU + 1 GPU)* | 2,28 | 3,7 % | 12,62 | 3,33 | 71 % (114 de 160 bloques) |

\* Siete procesos en seis núcleos físicos (`--oversubscribe`): el rango GPU casi no usa CPU porque duerme mientras
espera al kernel, pero el punto se marca como sobresuscrito (`sobresuscrito=1`) y tiene más variación.

V1 (k = 1 060 442 e histograma idénticos al secuencial) y V3 (`estado=OK`: suma = N y cobertura exacta de la cola)
pasan en las 36 corridas. Este T1 (28,71 s) es de la sesión de T41; el de X5 (30,38 s) es de otra sesión, y cada
tabla usa el suyo.

### Lectura

1. **Con los mismos seis procesos, cambiar un trabajador de CPU por la GPU hace a E2 3,2 veces más rápido.** E2 con
   CPU y GPU juntas (12,1×) supera también a la GPU sola (9,6×) y a `pp_cuda` sin MPI (10,1×).
2. **La cola dinámica reparte según la velocidad de cada trabajador, sin ajustar nada.** Por separado, la GPU procesa
   3,34 millones de escenarios/s (E2 solo GPU) y cada trabajador de CPU 0,264 millones/s (E2 CPU ÷ 5). Con 4 de CPU y
   la GPU, el reparto ideal le daría a la GPU el 76 % y el tiempo ideal sería 2,28 s. Se midió 75 % y 2,37 s: el 96 %
   de la suma ideal de los dos rendimientos. La diferencia es la cola final: el último bloque de un trabajador de CPU
   tarda ≈ 0,24 s, y en ese tiempo la GPU, que ya no tiene bloques, espera.
3. **El costo de MPI para la GPU es pequeño:** E2 solo GPU tarda un 5 % más que `pp_cuda` (3,00 s frente a 2,85 s),
   por los 322 mensajes de la cola y una sincronización por bloque de 62 500 escenarios (≈ 19 ms de GPU cada uno).
4. **Los mensajes no cambian:** E2 manda 2 × bloques + 2 mensajes por trabajador (REQ, WORK y STOP), 330 en total con
   cinco trabajadores, sean de CPU o de GPU. El trabajo de cada rango está en el registro.
5. **Es el mejor resultado medido en este equipo:** 12,1× frente a T1 con 6 núcleos y la GPU, frente a 4,7× de
   OpenMP con los mismos 6 núcleos (X5). No se compara con equipos de más núcleos (regla 2 de `AGENTS.md`).

### Límites

- Una sola GPU y un solo equipo: es un nodo heterogéneo CPU + GPU, no un clúster. Con varias GPU, cada una sería un
  rango más de la misma cola.
- Los bloques de 62 500 escenarios son pequeños para la GPU (≈ 20 escenarios por hilo con 24 × 128). Bloques más
  grandes reducen los mensajes, pero alargan la cola final de los trabajadores de CPU. No se barrió el tamaño de bloque.
- El kernel trabaja en doble precisión; una versión en simple precisión sería mucho más rápida en esta GPU, pero
  rompería la equivalencia exacta con la CPU (V2), que es el criterio del proyecto.
