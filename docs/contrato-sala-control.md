# Contrato de la sala de control (demo en vivo)

La sala de control es una página a pantalla completa que muestra, mientras corre el simulador, el uso de cada núcleo, el avance de cada backend y la verificación de que todos producen el mismo resultado. Este contrato fija las interfaces entre sus tres piezas para que se construyan en paralelo.

| Pieza | Ubicación | Responsabilidad |
|-------|-----------|-----------------|
| Simulador | `src/` | Opción `--progreso` que imprime líneas de avance en `stderr` |
| Servidor | `scripts/demo/sala_control.py` y `scripts/demo/sala/*.py` | Lanza corridas, muestrea la CPU, emite eventos SSE, graba y reproduce |
| Interfaz | `scripts/demo/sala/static/` | HTML, CSS y JS sin dependencias externas (sin CDN) |

El servidor corre **dentro** del contenedor `pp-g8` (así `/proc/stat` muestra los 24 vCPU de WSL2 y los binarios se llaman directo), publicado en el puerto `8765`.

## 1. Líneas de avance del simulador (`--progreso`)

- Sin `--progreso`, la salida no cambia en nada (las mediciones oficiales se toman sin la opción).
- Con `--progreso`, el binario escribe en `stderr`, una línea por evento, con este formato exacto:

```text
[prog] hecho=<entero> total=<entero>                    # serial, OpenMP; MPI E1 e híbrido añaden rango=<r>
[prog] rango=<r> hecho=<entero> total=<entero>          # E1 / híbrido: avance de cada rango sobre su tramo
[prog] rango=<r> bloque=<i0>,<i1>                       # E2: el maestro (rango 0) asigna [i0, i1) al trabajador r
```

- Frecuencia: como máximo una línea por cada 1 % de `total` por emisor (más la línea final con `hecho=total`).
- `total` es el número de escenarios del emisor (N en serial/OpenMP; el tramo del rango en E1/híbrido).
- En OpenMP e híbrido el contador es atómico y solo imprime el hilo 0 (o quien cruce el umbral, con una sola impresión por umbral).
- `k` y `hist512` deben ser idénticos con y sin `--progreso` (prueba obligatoria).

## 2. Eventos SSE (`GET /api/stream`)

Cada evento es `data: <JSON>\n\n`. Campos comunes: `t` (tipo) y `ts` (segundos desde el arranque del servidor, float).

| `t` | Campos | Cuándo |
|-----|--------|--------|
| `cpu` | `nucleos`: lista de floats 0–1 (uno por CPU lógica, en orden de `/proc/stat`) | cada 0,2 s, siempre |
| `inicio` | `id`, `backend` (`serial`, `openmp`, `mpi_estatico`, `mpi_dinamico`, `hibrido`), `procesos`, `hilos`, `n`, `afinidad` (`close`, `false` o `-`), `comando` | al lanzar una corrida |
| `avance` | `id`, `hecho`, `total`, `rango` (o `null`), `escenarios_s` | por cada línea `[prog] hecho=` |
| `bloque` | `id`, `rango`, `i0`, `i1` | por cada línea `[prog] rango= bloque=` (E2) |
| `fin` | `id`, `segundos`, `k`, `n`, `p`, `wilson` ([lo, hi]), `huella` (SHA-256 corto, 12 hex, del vector hist512), `trabajo_rangos` (lista de enteros o `null`), `speedup` (frente a la corrida serial de la misma carrera, o `null`) | al terminar bien |
| `error` | `id`, `mensaje` | al fallar |
| `estado` | `modo` (`vivo` o `replay`), `grabando` (bool), `ocupado` (bool) | al conectar y cuando cambia |

`id` es único por corrida, por ejemplo `c3-openmp`.

## 3. API HTTP

| Método y ruta | Cuerpo / parámetros | Respuesta |
|---------------|---------------------|-----------|
| `GET /` | — | `static/index.html` |
| `GET /static/<archivo>` | — | archivos de `static/` |
| `GET /api/stream` | — | SSE (§2) |
| `GET /api/configs` | — | `[{"id": "piura_miraflores_el_nino", "estacion": "...", "regimen": "...", "c": 6.0, "u": 50.0}, ...]` desde `config/*.yaml` |
| `POST /api/carrera` | `{"backends": ["serial","openmp","mpi_estatico","mpi_dinamico","hibrido"], "n": 20000000, "nucleos": 24, "config": "sintetico"}` | `{"carrera": "c3"}`; corre los backends **uno tras otro** (no en simultáneo, para que el speedup sea honesto) y emite eventos |
| `POST /api/hibrido` | `{"procesos": 4, "hilos": 6, "afinidad": "close"\|"false", "n": 20000000}` | `{"id": "..."}`; `close` reproduce a propósito el error de afinidad (`--bind-to none` + `close`), `false` es la corrección |
| `GET /api/riesgo` | `config`, `c`, `n` (por defecto 1e5), `hilos` (24) | `{"u": [...], "p": [...], "lo": [...], "hi": [...], "n": ..., "segundos": ...}`: curva P(Amax > u) desde hist512 con Wilson |
| `GET /api/convergencia` | `config`, `c`, `u`, `ns` (lista, por defecto 1e3..1e7) | `[{"n": ..., "p": ..., "lo": ..., "hi": ...}, ...]` |
| `POST /api/detener` | — | detiene la corrida en curso |
| `POST /api/grabar` | `{"activo": true\|false, "nombre": "ensayo"}` | graba todos los eventos SSE en `results/demo/sala/<nombre>.jsonl` |
| `POST /api/replay` | `{"nombre": "ensayo", "velocidad": 1.0}` | reproduce la grabación por el mismo SSE con sus tiempos (modo `replay`) |
| `GET /api/grabaciones` | — | lista de grabaciones disponibles |

Solo una corrida a la vez: si llega otra mientras `ocupado` es verdadero, responde `409`.

## 4. Afinidad

- OpenMP: `OMP_PROC_BIND=close`, `OMP_PLACES=cores`.
- MPI puro: `mpirun --bind-to core`.
- Híbrido: `mpirun --bind-to none` con `OMP_PROC_BIND=false` (corrección). La variante `close` existe solo para mostrar el error.

## 5. Respaldo

Toda la demo debe poder mostrarse sin simulador: el modo `replay` reproduce un `.jsonl` grabado en el ensayo con los mismos eventos y tiempos. La interfaz muestra un distintivo «REPLAY» cuando `estado.modo` es `replay`.
