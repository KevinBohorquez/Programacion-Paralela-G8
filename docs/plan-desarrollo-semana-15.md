# Plan de desarrollo hasta la semana 15

## Alcance

Este plan cubre S09–S15. Cada tarea del cronograma tiene un propietario que produce un artefacto comprobable; la columna «Revisor» de Excel designa a quien revisa el resultado, no a un coautor requerido. Cada integrante puede preparar su artefacto con datos sintéticos y contratos publicados mientras llegan las salidas de otras tareas. Solo la integración final depende de que los contratos se cumplan.

CUDA es una extensión en desarrollo (`docs/decision-cuda.md`): EXT1 (kernel validado con V2/V8) y después EXT2 (GPU como trabajador MPI). La extensión es desacoplada: el núcleo CPU y sus experimentos mantienen su alcance aunque la GPU no esté lista.

## Responsables y entregas propias

| Persona | Semana | Tareas | Producto independiente |
| --- | --- | --- | --- |
| **David** | S09 | T19, T20 | Dos ejecutables MPI: reparto estático con reducción y cola dinámica con REQ/WORK/STOP; pruebas de finalización. |
| **David** | S10 | T24, T29 | Híbrido MPI + OpenMP con nivel de hilos comprobado; decisión sobre la extensión CUDA registrada en `docs/decision-cuda.md`. |
| **David** | S13 | T43, T44 | Integración estable de extensiones que pasen pruebas; etiqueta `entrega-final` y guía de reproducción. |
| **David** | S14–S15 | T49, T52, T53 | Informe y paquete final publicados en el repositorio; coordinación y registro de exposición. |
| **Angela** | S09–S11 | Preparación de T35 | Datos de prueba y script de agregación científica por estación, capacidad, régimen y bootstrap, ejecutable sin el clúster. |
| **Angela** | S12 | T35 | Tablas de probabilidad, IC Wilson, banda epistémica y curva riesgo–capacidad desde CSV X6. |
| **Angela** | S13 | T42 | Sensibilidad de `U = 30/50/80 mm` y régimen normal/El Niño; CSV y gráficos reproducibles. |
| **Ashley** | S09 | T21 | Suite V1/V3/V4 y barrido MPI de 2/4/8/16 procesos, con carga fija, cinco repeticiones y hardware descrito. |
| **Ashley** | S10–S12 | T37 | Diagrama y explicación verificable de MPI, hilos OpenMP, reducciones, afinidad y llamadas MPI. |
| **Ashley** | S14 | T48 | Anexo de reproducción con comandos de compilación, ejecución, pruebas y esquema de CSV. |
| **Lita** | S09 | T23 | Inventario GPU y alternativa de ejecución documentada, sin implementar aún CUDA. |
| **Lita** | S10 | T27 | Matriz híbrida de 2/4/8/16 núcleos totales mediante procesos × hilos; CSV y gráfico. |
| **Lita** | S11 | T32 | Comparación MPI estático/dinámico sobre nodos heterogéneos, con los mismos procesos y carga. |
| **Lita** | S11–S13, extensión CUDA en desarrollo | T38–T41 | Kernel, V2/V8, barrido de 2/4/8/16 bloques CUDA y 128/256/512 hilos por bloque; comparación CPU sola frente a CPU + GPU. |
| **Miguel** | S09 | T22 | Compose que ejecuta E1 y E2 en contenedores y guarda CSV. |
| **Miguel** | S10 | T25, T26 | Swarm en tres equipos físicos y ejecutor parametrizable de benchmarks con captura de CPU, GPU, red y commit. |
| **Miguel** | S11 | T30, T31 | X1–X3: escalabilidad fuerte y débil y barrido de carga. Para CPU: 2/4/8/16 hilos, procesos o núcleos totales según backend, sin mezclar cargas. |
| **Miguel** | S12 | T34 | Corrida oficial X6 en CPU con resultados y logs respaldados. |
| **Miguel** | S15 | T51 | Demostración en clúster probada el día anterior, con salida precalculada de respaldo. |
| **Rhamses** | S10 | T28 | Borrador de problema, modelo, metodología y entorno usando los contratos vigentes. |
| **Rhamses** | S11 | T33 | Análisis de tiempos, speedup, eficiencia, throughput y Karp–Flatt con media, desviación y límites del hardware. |
| **Rhamses** | S12 | T36 | Sección de resultados científicos con tablas y curvas generadas por los scripts. |
| **Rhamses** | S13 | T45 | Figuras finales de rendimiento, riesgo y sensibilidad con datos y unidades correctos. |
| **Rhamses** | S14 | T46, T47 | Informe IEEE integrado y bibliografía vinculada a decisiones técnicas concretas. |
| **Rhamses** | S15 | T50 | Presentación y guion de exposición, con una gráfica por conclusión principal. |

## Comparación de 2, 4, 8 y 16 recursos

| Implementación | Configuración solicitada | Precisión de la interpretación |
| --- | --- | --- |
| Secuencial | 1 núcleo | Línea base medida en el mismo tipo de CPU. |
| OpenMP | 2/4/8/16 hilos | Equivalen a núcleos físicos solo si hay suficientes núcleos y afinidad estable. |
| MPI E1 y E2 | 2/4/8/16 procesos | Registrar distribución por nodo y núcleos asignados a cada proceso. |
| MPI + OpenMP | 2/4/8/16 núcleos CPU totales | Elegir pares `procesos × hilos` cuyo producto sea el presupuesto; comparar más de una factorización cuando sea posible. |
| CUDA (en desarrollo) | 2/4/8/16 bloques y 128/256/512 hilos por bloque | Un bloque no es un núcleo físico GPU. Registrar SM y ocupación observada; no atribuir a «16 núcleos CUDA» una configuración de 16 bloques. |
| CPU + GPU (en desarrollo) | CPU sola frente a CPU + GPU | Mantener carga fija y declarar por separado recursos CPU y GPU. |

Una configuración que exceda los núcleos físicos disponibles se etiqueta como sobresuscrita y se analiza aparte. Todos los puntos comparables usan igual `N`, parámetros y semilla, una corrida de calentamiento y cinco medidas. Antes de calcular speedup se comprueba equivalencia de resultados. Los CSV guardan commit, hardware, afinidad, procesos, hilos, bloques, tiempos y conteos.

## Entregables por semana

| Semana | Entregable | Evidencia exigida |
| --- | --- | --- |
| S09 | E4 MPI | E1/E2, V1/V3/V4 y matriz de procesos 2/4/8/16. |
| S10 | E5 híbrido | Swarm multinodo, matriz procesos × hilos y decisión de extensiones. |
| S11 | E6 rendimiento | X1–X4 CPU, cinco repeticiones y análisis por recurso. |
| S12 | E7 resultados | X6 y curvas con incertidumbre; CUDA cuando pase V2/V8. |
| S13 | E8 sensibilidad y código | X7, etiqueta final y guía de reproducción. |
| S14 | E9 informe | Informe IEEE y anexo de reproducción. |
| S15 | E10 exposición | Presentación, demostración y paquete final. |
