# Guion de exposición de la semana 11 — Grupo 8

**Objetivo:** presentar el avance del simulador Monte Carlo de riesgo de inundación urbana: resultados de rendimiento en CPU, validación del modelo, riesgo por estación y estado del despliegue multinodo y de CUDA.
**Duración total:** alrededor de 15 minutos de exposición en 14 diapositivas, más la demostración final.
**Reparto:** Expositor 1, Expositor 2 y Expositor 3, unos 5 minutos cada uno, en ese orden; la demostración la presenta otra persona del grupo.

## Parte 1 — Expositor 1: problema, estado y arquitectura (≈ 5 min)

| Diapositiva | Qué decir | Tiempo |
| --- | --- | --- |
| cover | Buenos días. Somos el Grupo 8 y presentamos el avance de la semana 11 de nuestro simulador paralelo de riesgo de inundación urbana. Expondremos tres integrantes y cerraremos con una demostración. | 0:30 |
| problema | Queremos estimar la probabilidad de que el agua acumulada máxima supere un umbral U, dada una capacidad de drenaje C: P(Amax > U). La lluvia diaria se modela con una cadena de Markov de dos estados para la ocurrencia y una distribución gamma para los montos, calibradas con estaciones de SENAMHI. Cada escenario es independiente, por lo que el problema es naturalmente paralelo, pero necesitamos decenas de millones de escenarios para estimaciones precisas. | 1:15 |
| estado | El núcleo, los backends secuencial, OpenMP, MPI estático (E1), MPI dinámico (E2) e híbrido están implementados y probados. El 05/11 pasaron 20 de 20 pruebas de CTest, 115 pruebas unitarias (32 omitidas) y 40 de 40 pruebas de integración MPI. La línea base secuencial es T1 = 59,70 s con N = 2·10⁷ y semilla 20261015. | 1:00 |
| arquitectura | Usamos el generador Philox4x32-10, basado en contador: cada escenario obtiene sus números aleatorios a partir de su índice global, sin importar qué hilo o proceso lo ejecute. Gracias a eso, todos los backends producen exactamente el mismo conteo, k = 2 122 915 con N = 2·10⁷. OpenMP reparte escenarios entre hilos con reducción; E1 reparte bloques fijos entre procesos y E2 usa un maestro que entrega lotes bajo demanda; el híbrido combina procesos MPI con hilos OpenMP. | 1:15 |
| afinidad | Al medir el híbrido encontramos un problema de afinidad. Con `--bind-to none`, la opción `OMP_PROC_BIND=close` amontonaba los hilos de varios procesos en los mismos núcleos. La corrección fue usar `OMP_PROC_BIND=false` y dejar que el sistema distribuya los hilos; solo así las medidas híbridas son comparables. | 1:00 |

**Transición al Expositor 2:** «Con la arquitectura y la afinidad resueltas, mi compañero presenta cómo escala cada backend.»

**Preguntas probables**

- *¿Por qué los resultados son idénticos entre backends?* Porque Philox es un generador basado en contador: los números dependen del índice del escenario y de la semilla, no del orden de ejecución.
- *¿Qué hardware se usó?* Un Intel Core Ultra 9 275HX con 8 núcleos P y 16 núcleos E, sin SMT, bajo Docker Desktop sobre WSL2.
- *¿Por qué el problema de afinidad solo aparece en el híbrido?* Porque con `--bind-to none` cada proceso desconoce a los demás y `close` coloca sus hilos en los mismos primeros núcleos; con un solo proceso eso no ocurre.

## Parte 2 — Expositor 2: rendimiento (≈ 5 min)

| Diapositiva | Qué decir | Tiempo |
| --- | --- | --- |
| x1-fuerte | Esta es la escalabilidad fuerte: carga fija y 2, 4, 8 y 16 recursos. La corrida X1 del 26/10 coincidió con contenedores ajenos activos que inflaron los tiempos entre 0 y 50 %, por eso la gráfica muestra una estimación limpia construida con las matrices M1 y M2 y con OpenMP del 15/10, en la misma configuración. Con 16 recursos, el híbrido alcanza un speedup de 11,58, E1 11,38, OpenMP 10,94 y E2 10,50. | 1:15 |
| x2-debil | En escalabilidad débil la carga crece con el número de recursos. Con 16, la eficiencia es 0,70 para el híbrido, 0,69 para OpenMP, 0,60 para E1 y 0,52 para E2. La caída se explica en parte porque, a partir de 8 hilos, el trabajo empieza a ocupar núcleos E, más lentos que los P. | 1:00 |
| x3-carga | En el barrido de carga con 8 recursos, OpenMP y E1 se mantienen entre 7,0 y 7,3 de speedup. E2 queda por debajo porque el maestro solo reparte trabajo: de los 8 procesos, solo 7 simulan. | 0:45 |
| mpi-matriz | La matriz MPI se midió el 05/11 con el anfitrión en reposo y cinco repeticiones. E1 estático da speedups de 2,04, 4,12, 7,04 y 11,38 con 2, 4, 8 y 16 procesos. E2 dinámico da 1,02, 3,07, 6,18 y 10,50: con 2 procesos no acelera porque el maestro no simula y solo queda un trabajador. | 1:00 |
| hibrido-matriz | En el híbrido probamos todas las factorizaciones de 16 núcleos entre procesos e hilos. Todas dan un speedup cercano a 11,5, con eficiencia de 0,72, lo que indica que el reparto entre procesos e hilos casi no influye en este problema. | 1:00 |

**Transición al Expositor 3:** «El rendimiento está medido; ahora veremos si los resultados del modelo son confiables y qué dicen sobre el riesgo.»

**Preguntas probables**

- *¿Por qué E2 no acelera con 2 procesos?* Porque el proceso 0 es el maestro y no simula; con 2 procesos hay un solo trabajador, que hace todo el trabajo más la comunicación.
- *¿Por qué la eficiencia supera 1 con 2 y 4 procesos?* No es superlinealidad real. T1 se midió el 15/10 y las matrices el 05/11; una diferencia de 2–4 % entre días (estado térmico, frecuencia, carga del sistema) basta para explicarlo. La diferencia es pequeña (2,04 y 4,12) y se confirmará midiendo T1 el mismo día que las matrices.
- *¿Por qué se contaminó X1?* Durante esa corrida había contenedores de otros proyectos activos en el mismo anfitrión, compitiendo por CPU. Lo detectamos al comparar con M1 y M2 medidas en reposo y la invalidamos como referencia; por eso mostramos la estimación limpia.

## Parte 3 — Expositor 3: validación, riesgo y multinodo (≈ 5 min)

| Diapositiva | Qué decir | Tiempo |
| --- | --- | --- |
| validacion | La validación estadística V6 compara el modelo con lo observado en cada estación. El hallazgo principal es que el sesgo depende del régimen: el modelo subestima el riesgo en años normales y lo sobrestima en años El Niño en Piura y Tumbes. Esto significa que el contraste entre El Niño y años normales que produce el modelo está exagerado, y lo reportamos así. Lo declaramos como una limitación del modelo, no como un error de la paralelización. | 1:15 |
| riesgo-x6 | La corrida X6 tiene 170 puntos con N = 10⁷, y además un bootstrap de K = 100 réplicas con N = 10⁶ para medir la incertidumbre de los parámetros. En Tumbes El Tigre, con C = 6 y U = 50, el año normal da 0,25 con banda de 0,10 a 0,47, frente a 0,52 observado. El semiancho de Wilson es de unas ±0,0003; la incertidumbre que domina es la de los parámetros, no la de Monte Carlo. | 1:15 |
| riesgo-enso | En el mismo punto, El Niño da 0,91 con banda de 0,56 a 0,99, frente a 0,83 observado. En la sensibilidad X7, al subir U de 30 a 80 mm, el riesgo normal cae de 0,66 a 0,04 y el de El Niño de 0,99 a 0,63: el umbral pesa mucho más en años normales. Para la gestión del drenaje, esto indica que el umbral elegido cambia la conclusión sobre todo en años normales. | 1:15 |
| multinodo | Preparamos un stack de Docker Swarm para tres equipos físicos y un script de despliegue que crea el clúster, distribuye la imagen y lanza E1 y E2 con `mpirun` entre los tres nodos. Por ahora solo está validado como simulación en un solo anfitrión; la corrida real en tres PC está pendiente. En cuanto a GPU, la extensión CUDA EXT1 está diseñada en el inventario de GPU sobre una RTX 4060, y su implementación es la siguiente etapa. | 1:15 |

**Transición a la demostración:** «Para terminar, nuestro compañero mostrará el simulador en funcionamiento.»

**Preguntas probables**

- *¿El multinodo es real?* Todavía no. El stack y el script existen y funcionaron en una simulación con varios contenedores en un solo equipo; la corrida en tres PC físicas está pendiente.
- *¿En qué estado está CUDA?* Está diseñada: el inventario de GPU fija el equipo (RTX 4060), las restricciones (WDDM, lanzamiento por lotes, precisión) y el barrido previsto. La implementación del kernel y la reducción es la siguiente etapa; hoy no hay resultados de GPU.
- *Si el modelo tiene sesgo, ¿sirven los resultados?* Sí, siempre que se lean con su banda de incertidumbre y con el sesgo declarado por régimen; no los presentamos como pronóstico exacto.

## Demostración (presentador de la demostración, distinto de los tres expositores)

**Introducción:** «A continuación mostramos una ejecución del simulador para ver en la práctica lo que acabamos de presentar.»

*[Espacio reservado: el presentador de la demostración redacta y dice su propio mensaje.]*

**Cierre:** «Gracias. Quedamos atentos a sus preguntas.»

## Mensajes clave

- Todos los backends CPU dan el mismo conteo (k = 2 122 915) gracias a Philox.
- Con 16 recursos, el speedup está entre 10,5 y 11,6, medido con el anfitrión en reposo.
- El híbrido rinde igual en todas sus factorizaciones de 16 núcleos (S ≈ 11,5).
- El modelo tiene un sesgo que depende del régimen, y la incertidumbre de los parámetros domina sobre la de Monte Carlo.
- Swarm y CUDA son la siguiente etapa: el primero está listo y simulado; el segundo, diseñado.

## No decir

- Que CUDA está implementado o que hay resultados de GPU.
- Que el Swarm se ejecutó en tres PC reales.
- Ninguna mención a una decisión «NO-GO» sobre CUDA.
- Cifras de X1 del 26/10 como si fueran medidas limpias.
