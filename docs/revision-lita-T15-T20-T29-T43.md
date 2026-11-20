# Revisión de T15, T20, T29 y T43, y estado de T23, T27 y T32

**Revisora:** Lita (R4) · **Fecha:** 19/11/2026 (S13) · **Versión revisada:** `origin/master`, commit `e4e34a4` (fusión de los PR #8 y #9)

Esta revisión reemplaza la del 05/11, que se hizo sobre `miguel-docker-bench` antes de que se fusionara y cuando la decisión sobre CUDA todavía era la anterior. Los criterios salen de `cronograma/cronograma-interno.xlsx` (hoja «Tareas», columnas «Criterio de terminado» y «Evidencia verificable»).

## Resumen

| Tarea | Responsable | Veredicto | Motivo principal |
| --- | --- | --- | --- |
| T15 Backend OpenMP | Ashley | **Aprobada** | V1 idéntico al secuencial con 1/2/4/8 hilos y cuatro schedules; reducción sin escrituras compartidas |
| T20 MPI E2 dinámico | David | **Aprobada con observaciones** | Termina sin bloqueo y procesa exactamente N con 1–16 procesos; falta versionar el log con los bloques de cada rango |
| T29 Decisión CUDA | David | **Aprobada con observaciones** | La decisión vigente está en `master`, pero perdió la evidencia E1–E5 y no fija un criterio de salida con fecha |
| T43 Integrar extensiones | David | **Pendiente** | `master` está en verde y la decisión está integrada, pero no hay registro de integración EXT1/EXT2 (V2/V8 aún no existen) |

## Verificación ejecutada

PC de Lita: i5-12400F (6C/12T), 15,8 GB, Windows 11 Pro, Docker Desktop 29.8.2 (WSL2), imagen `pp-g8` del 06/11 (el `Dockerfile` no cambió desde el 15/10).

```bash
D "cmake -S . -B build/docker -DCMAKE_BUILD_TYPE=Release -DPP_BUILD_MPI=ON && cmake --build build/docker -j"
D "ctest --test-dir build/docker --output-on-failure"
D "python3 -m pytest -q tests/unit"
D "PP_BIN_DIR=build/docker/src/backends python3 -m pytest -q tests/integration"
```

| Suite | Resultado |
| --- | --- |
| Compilación Release con MPI | Sin errores ni advertencias |
| CTest | **21/21 pasan** (`v6_observado` deshabilitada por diseño): humo, V1, V6 sintética, `pp_mpi_estatico_np1…np16`, `pp_mpi_dinamico_np1…np16` e híbrido 1x2…8x2 |
| `tests/integration` | **42 pasan**, 3 omitidas |
| `tests/unit` | **167 pasan, 16 fallan**. Los 16 fallos son todos `test_v6_frente_a_observado` (8 estaciones × 2 regímenes): la V6 contra datos observados que ya se conoce como fallida (colas subestimadas, ver `results/cientifico/README.md`). |

E2 con `--progreso --verificar`, N = 10007 y `--lote 1000`, 4 procesos (extracto):

```text
[prog] rango=2 bloque=0,1000
[prog] rango=3 bloque=1000,2000
[prog] rango=1 bloque=2000,3000
…
[prog] rango=3 bloque=10000,10007
[verif] rango=0 bloques=11 n_local=0
[verif] rango=1 bloques=3 n_local=3000
[verif] rango=2 bloques=4 n_local=4000
[verif] rango=3 bloques=4 n_local=3007
[verif] suma_n=10007 suma_n_rangos=10007 suma_hist=10007 k=1060 estado=OK
[verif] v1_referencia=OK k_ref=1060
```

**Observaciones generales (fuera de las cuatro tareas):**
1. El CI no ejecuta `tests/unit`, por eso está en verde aunque la suite falla. El paso 2 de `AGENTS.md` pide correrla, y quien lo siga verá 16 fallos sin explicación. `docs/validacion-v6.md` ya decidió no cambiar el modelo y desactivó `v6_observado` en CTest, pero la versión pytest de la misma prueba sigue activa. Propuesta para T13 (Lita, R4): marcar `test_v6_frente_a_observado` como `xfail(strict=False)` con el motivo y un enlace a `docs/validacion-v6.md`, y agregar `tests/unit` al CI.
2. `results/cientifico/README.md` dice que las probabilidades «pueden **subestimar** el riesgo hasta que la ola D recalibre». En cambio, `docs/validacion-v6.md` concluye que el modelo **no se recalibra** y que el sesgo depende del régimen: subestima en años normales y sobrestima en El Niño de Piura y Tumbes, lo que exagera el contraste El Niño/normal. Hay que alinear la advertencia del README y la columna `nota` de las tablas con el diagnóstico (Angela, T35), y llevar esa limitación a las secciones 08 y 09 del informe (Rhamses, T36).

**CI de `master`:** la corrida del commit `e4e34a4` terminó en verde ([run 42143061721](https://github.com/KevinBohorquez/Programacion-Paralela-G8/actions/runs/42143061721)). La anterior (`b0b3a5c`, fusión del PR #8) falló en el trabajo MPI por falta de numpy/scipy; el PR #9 lo corrigió.

## T15 · Backend OpenMP con reducción de k, n e histograma

**Criterio:** V1 da conteos e histograma idénticos al secuencial para 1/2/4 hilos.

- `src/backends/openmp/ejecutor.cpp:68`: `reduction(+ : k, n)` y `reduction(+ : hist[:NBINS])`. El bucle no tiene escrituras compartidas. La variante con `--progreso` (`:78`) usa la misma reducción y solo suma a un contador atómico cada `PASO_PROGRESO` escenarios.
- `ejecutor.cpp:61`: el índice global `base + j`, con `base = config_id * n_total`, no depende del hilo ni del schedule. Por eso el resultado es igual bit a bit.
- Evidencia: `results/validacion/t17_v1_equivalencia.txt` (1/2/4/8 hilos × `static`, `dynamic`, `dynamic:7`, `guided`), reproducida hoy en las pruebas de integración.

**Observaciones (no bloquean):**
1. `aplicar_schedule` (`ejecutor.cpp:22`) usa `std::atoi`: `--schedule dynamic:abc` se acepta en silencio como chunk 0 en vez de fallar. Conviene `std::stoi` con comprobación de que se consumió toda la cadena.
2. `omp_set_num_threads` y `omp_set_schedule` cambian el estado global del proceso. El híbrido reutiliza esta biblioteca, así que cualquier llamada posterior hereda ese estado.

## T20 · MPI E2 dinámico con REQ/WORK/STOP

**Criterio:** sin bloqueos; 2/4/8/16 procesos terminan y procesan exactamente N escenarios.
**Evidencia pedida:** log de 2/4/8/16 procesos sin bloqueo, con cada rango único y suma = N.

- `src/backends/mpi/dinamico.cpp:36-52`: el maestro responde cada REQ con un WORK o un STOP y envía exactamente un STOP por trabajador (`--activos`). Ningún trabajador puede quedar esperando, y el maestro sale cuando todos recibieron STOP.
- `cobertura_exacta` (`dinamico.cpp:20`) comprueba que los rangos asignados cubren [0, N) sin solape ni huecos. `comun.cpp:151` exige además suma de `n_local` = N, suma del histograma = n y k ≤ n.
- `--lote 0` se rechaza (`src/io/configuracion.cpp:151`).
- CTest corre `pp_mpi_dinamico_np1…np16` con N primo (10007) y `--verificar` (V1 frente al secuencial). CI de `master` en verde.
- Con `--progreso`, el maestro imprime en stderr una línea `[prog] rango=R bloque=i0,i1` por asignación (`src/io/progreso.cpp:47`). Ese es justo el log de «cada rango único» que pide la evidencia.

**Observaciones:**
1. **Falta versionar la evidencia.** El log de `[prog] … bloque=` existe como función, pero no hay un archivo en `results/validacion/` con 2/4/8/16 procesos. Basta con guardar la salida de `pp_mpi_dinamico --n 10007 --lote 1000 --progreso --verificar` para cada número de procesos.
2. En la línea `[verif] rango=0`, `bloques` es el total que repartió el maestro, no trabajo propio (su `n_local` es 0). Conviene aclararlo en el log o en `docs/contratos.md` para que no se lea como desbalance.
3. `siguiente + cfg.lote` (`dinamico.cpp:41`) puede desbordar si `lote` se acerca a 2⁶⁴. Es teórico, pero se evita validando `lote <= n` en `configuracion.cpp`.
4. El rango 0 no simula en E2. Con P procesos, E2 tiene P−1 trabajadores y E1 tiene P. Así se explica el speedup de 1,02 con 2 procesos en `results/bench/mpi_resumen.csv`, y el informe debe decirlo cada vez que compare E1 con E2 (T32, T33).
5. El cronograma sigue marcando T20 como «No iniciado».

## T29 · Decisión interna de CUDA

**Criterio:** acta de decisión con evidencias, GPU disponible y tareas EXT activadas.
**Evidencia pedida:** `docs/decision-cuda.md` con fecha, evidencia, decisión y tareas T38–T41 activadas o descartadas.

- `docs/decision-cuda.md` está en `master`: fecha 05/11/2026, decisión (CUDA se incluye como extensión en desarrollo), GPU disponible (RTX 4060 de Lita y RTX 5090 Laptop de Miguel), plan por pasos, criterios V2/V8, restricciones (WDDM, TDR, Docker con GPU) y riesgos.
- La versión anterior de la decisión, del 26/10 (`1ee5fd0`), se reemplazó el 05/11 (`a7f481f`). El guion de S11 se alineó con el cambio.

**Observaciones:**
1. **Falta la evidencia E1–E5.** El criterio dice «tras revisar E1–E5», y la versión anterior de la decisión tenía esa tabla. La versión vigente la quitó y ya no justifica con datos por qué se activa la extensión. Hay que reponer una tabla corta con el estado de E1–E5 y su evidencia.
2. **Falta un criterio de salida con fecha.** La decisión es un GO condicionado, pero no dice qué pasa si EXT1 no pasa V2/V8 a tiempo. El cronograma ya prevé la salida («si no, se reporta CUDA como C4 aislado»). Propuesta: EXT1 validada antes del 24/11; si no, CUDA queda fuera del informe de S14. EXT2 solo si EXT1 está validada y hay clúster; si no, C4 aislado.
3. **Datos desactualizados.** La tabla §6 dice «nvcc pendiente de instalar» en el PC de Lita. Hoy está CUDA 13.3 en WSL (Ubuntu-24.04), controlador 621.01, y `cudaGetDeviceProperties` confirma 24 SM.
4. El criterio menciona un «Acta en Seguimiento», pero el cronograma solo tiene las hojas `Entregables`, `Tareas` y `Riesgos`. Hay que corregir el texto del criterio o aceptar el MD como acta.
5. El cronograma marca T29 como «No iniciado».

## T43 · Integrar solo extensiones que superen sus pruebas

**Criterio:** registro de integración indica EXT1/EXT2 y resultados V2/V8; `main` pasa CI.
**Evidencia pedida:** PR de integración, enlace a CI verde y `docs/decision-cuda.md` actualizado con el estado de EXT1/EXT2.

- Cumplido: la decisión y los marcadores CUDA están en `master`, y el CI de `e4e34a4` está en verde.
- No cumplido: no hay registro de integración. EXT1 no tiene código (los siete archivos CUDA siguen con una línea y `PP_BUILD_CUDA` vale `OFF`), así que no existen resultados V2/V8 que registrar.

**Para cerrarla (S13–S14):**
1. Esperar el PR de EXT1 (T38–T40) con V2/V8 en `results/validacion/`.
2. Si pasa, integrarlo con `PP_BUILD_CUDA=OFF` por defecto, para que el CI sin GPU siga en verde. Si no pasa a tiempo, registrar «EXT1 no integrada» con el motivo.
3. Agregar a `docs/decision-cuda.md` una sección «Registro de integración» con el PR, la corrida de CI, V2/V8 y el estado de EXT1/EXT2.
4. Hacer esto **antes** de la etiqueta `entrega-final` (T44).

## Estado de las tareas propias (autoevaluación, no revisión)

Las tareas T23, T27 y T32 son de Lita, así que esta sección no es una revisión: indica qué falta para que su revisor (David en T23, Miguel en T27, Ashley en T32) pueda aprobarlas.

### T23 · Inventario GPU — falta actualizar

| Requisito del criterio | Estado |
| --- | --- |
| Modelo, memoria, controlador y entorno | ⚠️ El documento es del 15/10: controlador 572.83, «nvcc no instalado», «Docker no instalado», WSL «Ubuntu 26.04». Hoy: controlador 621.01, CUDA 13.3 en WSL Ubuntu-24.04, Docker Desktop 29.8.2. |
| SM confirmados | ⚠️ Figura como dato de ficha técnica. Confirmado hoy con `cudaGetDeviceProperties`: 24 SM, CC 8.9, 8187 MiB, 1536 hilos/SM, máx. 24 bloques/SM, 48 KiB de memoria compartida por bloque. |
| Otros equipos | ⚠️ Las filas de los demás integrantes dicen «Pendiente». La RTX 5090 Laptop de Miguel solo aparece en `decision-cuda.md`. |
| Decisión con fecha y alternativa CPU | ⚠️ El §4 remite a T29 pero no dice explícitamente que, sin GPU validada, todas las campañas siguen en CPU. |

**Qué hacer:** actualizar la tabla §1 y la salida §2 con los datos de hoy; agregar la fila de Miguel y «sin GPU NVIDIA» para quienes no tengan; agregar una línea con la fecha y la alternativa CPU. Dato útil para X5: con 24 SM, las configuraciones de 2/4/8/16 bloques **no llenan la GPU** (cada bloque ocupa un SM como máximo). Conviene añadir un punto de referencia con la grilla completa (por ejemplo 24 × k bloques) para no concluir que la GPU es lenta.

### T27 · Medir híbrido con 2/4/8/16 núcleos — cumple; faltan dos observaciones

`results/bench/hibrido.csv` (84 filas) y `hibrido_resumen.csv`: cuatro presupuestos, **todas** las factorizaciones p × t (13), igual N = 2·10⁷ y semilla, calentamiento más cinco repeticiones, k = 2 122 915 en todas (equivalencia con el serial), commit `6f6cf0bdd784` (en `master`), CPU, núcleos y sobresuscripción registrados. Figuras `results/figures/hibrido_speedup` y `hibrido_eficiencia` en PNG y SVG. Medido en el PC de Miguel (Core Ultra 9 275HX), el mismo equipo que T1, M1 y X6.

**Observaciones antes de marcarla completa:**
1. **Eficiencia mayor que 1 con 2 y 4 núcleos** (1,01–1,04). La T1 de referencia (`secuencial_t1.csv`) es del 16/10, con el commit `43be549ae855`, que no está en la historia de `master`. El híbrido es del 05/11. Un speedup superlineal sostenido apunta a una base T1 de otra sesión (turbo o núcleo P/E distinto), no a un efecto real. Hay que remedir T1 en la misma sesión que M1 y M2, o declararlo en el informe.
2. **Repetición atípica en 8x1:** la repetición 4 tarda 10,55 s frente a ≈8,3 s del resto (CV ≈ 11 %). Por la regla 4 de `AGENTS.md` es interferencia: hay que remedir ese punto o informar la mediana.
3. **Sin afinidad fija** (`OMP_PROC_BIND=false`, `--bind-to none`) en un procesador con núcleos P y E. Está registrado, pero el informe debe decir que no se controló en qué tipo de núcleo cayó cada hilo.
4. Marcar T27 en el cronograma y anotar que la medición se hizo en el PC de Miguel.

### T32 · E1 frente a E2 en CPU heterogéneas — no iniciada; el script no cubre el criterio

**Criterio:** CSV de igual N y asignación de procesos; tiempo, balance y coste de mensajes calculados; mapa rank–nodo.

`scripts/bench/comparar_mpi_heterogeneo.py` existe y tiene pruebas unitarias, pero tiene dos huecos frente al criterio:
1. **El desbalance de E1 vale 1 por construcción.** El script lo calcula como máximo/media de `n_local`, y en E1 cada rango recibe N/P. En E1 el desbalance real está en el **tiempo** de cada rango, y el simulador no lo reporta: `comun.cpp` reúne `inicio`, `fin`, `bloques`, `n_local`, `coherente` e `hilos`, pero no el tiempo de cómputo por rango.
2. **No hay coste de mensajes.** En E2 el número de mensajes se puede derivar (por trabajador: `bloques + 1` REQ, `bloques` WORK y un STOP), pero no se calcula ni se mide el tiempo de espera del trabajador.

**Propuesta (sin depender de nadie, coordinando con David porque `comun.cpp` es suyo):** agregar `t_computo` por rango al `MPI_Gather` y a la línea `[verif] rango=`, calcular `t_espera = t_total − t_computo` y contar mensajes en E2; luego extender el script para que lea esas columnas.

**Sobre la heterogeneidad sin red local:** el criterio pide «CPU heterogéneas», no necesariamente equipos distintos. Hay tres opciones:

| Opción | Quién | Heterogeneidad | Comentario |
| --- | --- | --- | --- |
| A. Núcleos P frente a E en el 275HX | Miguel corre, Lita prepara | **Real** (dos microarquitecturas en la misma CPU) | Un nodo lógico con `--cpuset-cpus` en núcleos P y otro en núcleos E. Es la mejor evidencia sin red. |
| B. Contenedores con distinta cuota de CPU en el PC de Lita | Lita sola | Emulada (`--cpus`) | Reproduce el efecto (un nodo más lento), pero hay que declararlo como emulación. Con 6 núcleos físicos: 2/4/8 procesos; 16 queda sobresuscrito. |
| C. Clúster real por VPN (Tailscale o ZeroTier) | Lita y Miguel | Real entre equipos | Funciona sin LAN, pero Swarm sobre Docker Desktop y WSL2 detrás de NAT es frágil, y la latencia de Internet infla el coste de mensajes. Solo si sobra tiempo. |

## Acciones sugeridas

| Acción | Responsable sugerido |
| --- | --- |
| Actualizar el cronograma: T15, T20, T21, T22, T24, T26, T27, T29 y T37 completadas; T23 y T43 en curso | Rhamses (T07) |
| Versionar el log de E2 con `--progreso` para 2/4/8/16 procesos (T20, obs. 1) | David |
| Reponer la evidencia E1–E5 y el criterio de salida con fecha en `decision-cuda.md` (T29, obs. 1–3) | David, con datos de Lita |
| Registro de integración de EXT1/EXT2 antes de `entrega-final` (T43) | David |
| Remedir T1 en la misma sesión que M1/M2 y el punto 8x1 del híbrido (T27, obs. 1–2) | Miguel |
| Actualizar el inventario (T23) y agregar `t_computo` y mensajes por rango para T32 | Lita |
