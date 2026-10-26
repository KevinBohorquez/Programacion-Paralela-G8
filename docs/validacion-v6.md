# Validación V6 frente a lo observado: diagnóstico de las colas (T13)

**Estado:** hallazgo científico documentado. El modelo y la calibración **no cambian**; la prueba
`v6_observado` sigue registrada en CTest pero **desactivada** por defecto (`-DPP_V6_OBSERVADO=ON` la activa).

## Resumen

- V6 contra el modelo (sintético) pasa: el generador produce exactamente la cadena de Markov + gamma
  que recibe.
- V6 contra las series SENAMHI falla en los 16 grupos estación × régimen. La frecuencia de lluvia,
  la media del monto y la racha media coinciden (error < 1,1 %); fallan la desviación (−12 a −48 %),
  el p99 (subestimado en 15/16, hasta −55 %), el p95 y el máximo diario medio por temporada, y KS rechaza al 5 % en 16/16.
- **No hay error de implementación.** La causa es estructural y tiene dos partes:
  1. **La gamma de 2 parámetros tiene la cola demasiado ligera** para la lluvia diaria de la costa:
     en 13 de 16 grupos el coeficiente de variación observado es 1,45–2,2 (α equivalente por momentos
     0,20–0,48), mientras que la gamma ajustada por verosimilitud (Thom o MLE exacta) da α = 0,45–0,75,
     porque la verosimilitud sigue el cuerpo de muchos días pequeños, no la cola. En Cañete y Chosica
     normal la brecha es menor (α por momentos 0,75–1,04 frente a 1,17–1,72), pero existe.
  2. **Heterogeneidad entre años dentro de un régimen.** En los grupos El Niño, la cola observada la
     ponen 1–3 temporadas (1983, 1998, a veces 2002/2017); los demás años "El Niño" son moderados.
     Un generador i.i.d. por temporada no puede reproducir a la vez la cola agrupada de los días y el
     máximo medio por temporada: si se le da la cola correcta, reparte esos extremos en todas las
     temporadas y sobrestima el máximo medio en +50 a +80 %.
- Ninguna alternativa probada (MLE, exponencial mixta, gamma + GPD, gamma por mes, gamma por año)
  hace pasar V6 en **ningún** grupo (0/16 en todas). Por eso no se cambia el núcleo.
- **Impacto en X6:** el sesgo de P(Amax > U) depende del régimen. En años normales el modelo
  **subestima** el riesgo (p. ej. El Tigre U = 50 mm: 0,25 frente a 0,52 observado); en años El Niño
  de Piura/Tumbes lo **sobrestima** (Miraflores 0,59 frente a 0,23; Puerto Pizarro 0,92 frente a 0,53).
  En consecuencia, el contraste El Niño / normal que sale del modelo está **exagerado**.

## Método

Script reproducible: [`scripts/run/diagnostico_v6.py`](../scripts/run/diagnostico_v6.py) (imagen `pp-g8`):

```bash
python3 scripts/run/diagnostico_v6.py --n 20000
```

Salidas: [`results/validacion/diagnostico_v6.log`](../results/validacion/diagnostico_v6.log) (texto por
grupo) y [`results/validacion/diagnostico_v6.csv`](../results/validacion/diagnostico_v6.csv) (96 filas:
16 grupos × 6 candidatos). La corrida de la prueba C++ queda en
[`results/validacion/d_v6_observado.log`](../results/validacion/d_v6_observado.log) y es idéntica, cifra
por cifra, a la de W0 ([`w0_v6_observado.log`](../results/validacion/w0_v6_observado.log)).

1. **Reproducir.** Se leen los montos de los días lluviosos con la misma ventana por zona, umbral
   (≥ 0,1 mm) y años de régimen que `calibrar.py` y `test_estadistico.py`.
2. **H1, error de implementación.** El script afirma que el número de días lluviosos y (α, θ) de Thom
   reproducen `parametros.csv` exactamente; además mide la resolución del registro y la masa que la
   gamma calibrada pone por debajo de 0,1 mm.
3. **H2, estimador.** Thom frente a máxima verosimilitud exacta (`scipy.stats.gamma.fit`, `loc = 0`).
4. **H3, forma.** Exponencial mixta de 3 parámetros (EM, Woolhiser y Roldán 1982) y gamma con cola GPD
   por encima del p90 (GPD por máxima verosimilitud a los excesos).
5. **H4, heterogeneidad.** Mezcla de una gamma (Thom) por mes de la temporada, y una por año.
6. Para cada candidato se simula en numpy la cadena de Markov calibrada (día previo seco, como
   `simular_escenario`) con 20 000 temporadas, se calculan los 7 estadísticos de V6 y KS de dos
   muestras (5000 montos simulados) frente a lo observado, y se calcula Amax con el balance de Lindley
   de `balance_hidrico.cpp` (C = 6 mm/día) para U = 30/50/80 mm. La réplica numpy de la gamma actual
   coincide con la del ejecutable C++ dentro de ~1 punto porcentual (p. ej. Bernal El Niño: desviación
   −32,1 % frente a −32,2 %; máximo +46,6 % frente a +46,0 %).

## Diagnóstico por hipótesis

### H1: no es un error de implementación

- En los 16 grupos, `n_dias_lluvia` y (α, θ) de Thom se reproducen exactamente desde `data/raw`: la
  calibración y V6 usan el mismo umbral (≥ 0,1 mm), la misma ventana, los mismos años por régimen, y
  los momentos excluyen los días secos. La media del monto coincide en todos los grupos (|error| ≤ 0,8 %),
  lo que descarta un problema de unidades o de mezcla de regímenes.
- Única inconsistencia menor: la gamma calibrada pone entre 2,6 % y 13,5 % de sus montos por debajo de
  0,1 mm, montos que un pluviómetro registraría como día seco. Afecta al cuerpo, no a la cola; KS con lo
  simulado redondeado a 0,1 mm (columna `ks_p_01mm`) sigue rechazando en 15/16 grupos.

### H2: el estimador de Thom no es la causa

| Grupo | α Thom | α MLE | α momentos (1/CV²) |
| --- | --- | --- | --- |
| lambayeque_lambayeque / el_nino | 0,574 | 0,556 | 0,216 |
| lambayeque_lambayeque / normal | 0,735 | 0,721 | 0,260 |
| lima_canete / el_nino | 1,573 | 1,568 | 0,749 |
| lima_canete / normal | 1,717 | 1,713 | 1,041 |
| lima_chosica / el_nino | 0,736 | 0,722 | 0,202 |
| lima_chosica / normal | 1,169 | 1,161 | 0,906 |
| piura_bernal / el_nino | 0,471 | 0,450 | 0,218 |
| piura_bernal / normal | 0,640 | 0,624 | 0,335 |
| piura_chulucanas / el_nino | 0,467 | 0,445 | 0,300 |
| piura_chulucanas / normal | 0,492 | 0,471 | 0,230 |
| piura_miraflores / el_nino | 0,636 | 0,619 | 0,476 |
| piura_miraflores / normal | 0,747 | 0,733 | 0,272 |
| tumbes_eltigre / el_nino | 0,585 | 0,567 | 0,354 |
| tumbes_eltigre / normal | 0,556 | 0,538 | 0,344 |
| tumbes_puertopizarro / el_nino | 0,688 | 0,673 | 0,426 |
| tumbes_puertopizarro / normal | 0,736 | 0,722 | 0,338 |

Thom y MLE difieren en ≤ 5 % de α; con MLE la desviación y el p99 mejoran solo 1–2 puntos. La brecha
real es entre la verosimilitud (cuerpo) y los momentos (cola): una sola gamma no puede tener ambos.

### H3: la gamma es estructuralmente ligera; una distribución más pesada ayuda pero no basta

La exponencial mixta mejora el AIC frente a la gamma en 13 de 16 grupos (de +25 a +197 puntos; la gamma
gana solo en Cañete, ambos regímenes, y Chosica normal) y, en la réplica numpy, reduce los fallos en
desviación (16 → 7), p95 (11 → 2) y KS (15 → 9). La cola GPD arregla desviación y p99 pero sesga la
media (hasta +17 %, > 10 % en 11 grupos) porque el cuerpo gamma
truncado no compensa. Ninguna de las dos pasa el máximo diario por temporada (10 y 14 fallos).

### H4: la heterogeneidad entre años explica el máximo por temporada

- Una gamma por mes casi no cambia nada (desviación: 15 fallos; p99: 14): la intensidad no varía mucho
  entre enero y abril dentro de un mismo régimen.
- Una gamma por año reduce los errores de la desviación y del p99 (los años extremos aportan su propia
  escala), lo que confirma que la cola agrupada viene de pocos años. Pero no es un generador utilizable
  (hasta 50 parámetros por grupo) y aun así pasa 0/16.
- Años que aportan los días ≥ p99 en El Niño: Bernal {1998}; Miraflores {1983, 1998}; Puerto Pizarro
  {1983, 1998, 2002}. En Miraflores El Niño, 1983 y 1998 suman 2457 de 3247 mm del grupo (76 %).
  El grupo "El Niño" (ICEN > 0,4 durante ≥ 3 meses, ENFEN 2012) mezcla eventos extraordinarios con
  eventos débiles; el modelo i.i.d. por temporada les da a todos la misma intensidad media.

## Antes y después por grupo

"Antes" es el modelo actual (gamma de Thom, idéntico en `w0_v6_observado.log` y en `d_v6_observado.log`).
Como el modelo no se cambia, "después" es igual a "antes"; la segunda tabla muestra, como referencia,
lo que lograría la mejor alternativa probada (exponencial mixta). Errores relativos simulado frente a
observado; en negrita lo que excede 10 % o KS p < 0,05.

### Valores observados

| Grupo | freq | media | sd | p95 | p99 | racha | máx. temp. |
| --- | --- | --- | --- | --- | --- | --- | --- |
| lambayeque_lambayeque / el_nino | 0,105 | 3,95 | 8,51 | 13,7 | 43,6 | 1,53 | 16,3 |
| lambayeque_lambayeque / normal | 0,075 | 1,92 | 3,76 | 7,1 | 17,6 | 1,39 | 7,08 |
| lima_canete / el_nino | 0,106 | 0,416 | 0,481 | 1,2 | 2,12 | 1,59 | 1,26 |
| lima_canete / normal | 0,189 | 0,358 | 0,351 | 1,0 | 1,88 | 1,75 | 1,16 |
| lima_chosica / el_nino | 0,069 | 2,80 | 6,22 | 7,99 | 33,4 | 1,16 | 12,4 |
| lima_chosica / normal | 0,088 | 1,99 | 2,09 | 5,8 | 7,16 | 1,30 | 4,69 |
| piura_bernal / el_nino | 0,114 | 8,12 | 17,4 | 40,8 | 78,9 | 1,66 | 23,8 |
| piura_bernal / normal | 0,069 | 2,48 | 4,28 | 10,0 | 15,7 | 1,43 | 7,58 |
| piura_chulucanas / el_nino | 0,472 | 13,9 | 25,3 | 56,4 | 136 | 3,25 | 98,2 |
| piura_chulucanas / normal | 0,279 | 5,45 | 11,3 | 25,6 | 61,3 | 2,48 | 40,3 |
| piura_miraflores / el_nino | 0,175 | 11,9 | 17,2 | 50,2 | 77,1 | 2,03 | 36,2 |
| piura_miraflores / normal | 0,068 | 4,14 | 7,93 | 13,5 | 39,6 | 1,43 | 11,9 |
| tumbes_eltigre / el_nino | 0,464 | 10,2 | 17,1 | 44,3 | 80,1 | 2,75 | 74,1 |
| tumbes_eltigre / normal | 0,311 | 6,71 | 11,4 | 30,0 | 53,2 | 2,35 | 41,8 |
| tumbes_puertopizarro / el_nino | 0,268 | 15,5 | 23,8 | 66,2 | 118 | 1,65 | 64,5 |
| tumbes_puertopizarro / normal | 0,194 | 6,89 | 11,9 | 27,0 | 64,2 | 1,71 | 39,4 |

### Modelo actual (gamma de Thom): antes = después

Valores del ejecutable C++ (`pp_v6_generador`, 20 000 temporadas, `d_v6_observado.log`):

| Grupo | freq | media | sd | p95 | p99 | racha | máx. temp. | KS p |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| lambayeque_lambayeque / el_nino | −1 % | −0 % | **−39 %** | +5 % | **−44 %** | −0 % | −8 % | **3e-05** |
| lambayeque_lambayeque / normal | +1 % | −1 % | **−41 %** | **−10 %** | **−42 %** | −0 % | **−17 %** | **5e-07** |
| lima_canete / el_nino | −0 % | −0 % | **−31 %** | **−11 %** | **−27 %** | +1 % | **−13 %** | **0,0009** |
| lima_canete / normal | +0 % | +0 % | **−22 %** | **−11 %** | **−32 %** | −0 % | −9 % | **3e-12** |
| lima_chosica / el_nino | +1 % | −1 % | **−48 %** | **+16 %** | **−55 %** | −0 % | **−33 %** | **0,04** |
| lima_chosica / normal | −0 % | −0 % | **−12 %** | −3 % | **+18 %** | −0 % | **+17 %** | **0,04** |
| piura_bernal / el_nino | +0 % | −0 % | **−32 %** | **−22 %** | **−30 %** | −0 % | **+46 %** | **2e-05** |
| piura_bernal / normal | +0 % | −0 % | **−28 %** | **−14 %** | −9 % | −0 % | +1 % | **0,0002** |
| piura_chulucanas / el_nino | −0 % | −0 % | **−20 %** | −4 % | **−30 %** | +0 % | −2 % | **3e-09** |
| piura_chulucanas / normal | −0 % | +0 % | **−32 %** | **−18 %** | **−41 %** | −1 % | **−22 %** | **3e-12** |
| piura_miraflores / el_nino | +1 % | −0 % | **−14 %** | **−17 %** | **−11 %** | −0 % | **+44 %** | **0,0008** |
| piura_miraflores / normal | +0 % | −0 % | **−40 %** | +1 % | **−45 %** | −0 % | +1 % | **2e-05** |
| tumbes_eltigre / el_nino | −0 % | −0 % | **−22 %** | **−17 %** | **−23 %** | +1 % | **−17 %** | **1e-05** |
| tumbes_eltigre / normal | +0 % | +0 % | **−22 %** | **−18 %** | **−21 %** | −1 % | **−10 %** | **5e-11** |
| tumbes_puertopizarro / el_nino | −0 % | −0 % | **−22 %** | **−20 %** | **−27 %** | −0 % | **+16 %** | **3e-08** |
| tumbes_puertopizarro / normal | +1 % | −0 % | **−32 %** | **−15 %** | **−43 %** | −0 % | **−25 %** | **2e-07** |

(Un error mostrado como −10 % en negrita excede 10 % antes de redondear.)

### Referencia: exponencial mixta (no adoptada)

| Grupo | freq | media | sd | p95 | p99 | racha | máx. temp. | KS p |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| lambayeque_lambayeque / el_nino | −1 % | +0 % | **−15 %** | **+36 %** | **−19 %** | −0 % | **+22 %** | 0,1 |
| lambayeque_lambayeque / normal | +1 % | −0 % | −5 % | +5 % | +8 % | −0 % | **+11 %** | **0,01** |
| lima_canete / el_nino | −0 % | −0 % | +8 % | +4 % | +10 % | +0 % | **+17 %** | **1e-05** |
| lima_canete / normal | +0 % | −0 % | +2 % | +7 % | **−13 %** | −0 % | **+13 %** | **1e-30** |
| lima_chosica / el_nino | +0 % | +1 % | **+15 %** | +8 % | **+15 %** | −0 % | −0 % | 0,08 |
| lima_chosica / normal | −0 % | −0 % | +2 % | +3 % | **+35 %** | −0 % | **+28 %** | 0,2 |
| piura_bernal / el_nino | −0 % | +0 % | **−14 %** | −4 % | −10 % | −0 % | **+80 %** | 0,4 |
| piura_bernal / normal | +0 % | +0 % | **−11 %** | +4 % | **+15 %** | −0 % | **+18 %** | 0,06 |
| piura_chulucanas / el_nino | +0 % | +0 % | −9 % | +10 % | **−22 %** | +1 % | +8 % | 0,4 |
| piura_chulucanas / normal | −0 % | −1 % | **−11 %** | +4 % | **−21 %** | −1 % | +2 % | **0,005** |
| piura_miraflores / el_nino | +0 % | −0 % | +2 % | −3 % | +7 % | −1 % | **+69 %** | 0,5 |
| piura_miraflores / normal | +0 % | +0 % | −8 % | **+29 %** | −5 % | −0 % | **+32 %** | **0,01** |
| tumbes_eltigre / el_nino | −0 % | +0 % | −10 % | −5 % | −10 % | +1 % | −3 % | **0,02** |
| tumbes_eltigre / normal | +0 % | −0 % | −10 % | −6 % | **−11 %** | −1 % | +2 % | **0,007** |
| tumbes_puertopizarro / el_nino | −0 % | −0 % | −0 % | −2 % | −3 % | −0 % | **+50 %** | **0,04** |
| tumbes_puertopizarro / normal | +1 % | −0 % | −5 % | +6 % | **−11 %** | −0 % | +6 % | **0,03** |

Resumen de los 6 candidatos en la réplica numpy (grupos que pasan V6 completo y fallos por
estadístico, de 16; la réplica de la gamma actual da KS p = 0,06 en Chosica El Niño, donde el C++ da 0,04):

| Candidato | Pasan | sd | p95 | p99 | máx. temp. | KS | media |
| --- | --- | --- | --- | --- | --- | --- | --- |
| gamma Thom (actual) | 0 | 16 | 11 | 15 | 11 | 15 | 0 |
| gamma MLE | 0 | 16 | 11 | 14 | 10 | 15 | 0 |
| exponencial mixta | 0 | 7 | 2 | 11 | 10 | 9 | 0 |
| gamma + GPD (p90) | 0 | 5 | 5 | 4 | 14 | 15 | 11 |
| gamma por mes | 0 | 15 | 9 | 14 | 10 | 14 | 0 |
| gamma por año | 0 | 8 | 8 | 10 | 11 | 13 | 0 |

## Decisión

Se documenta como hallazgo (opción b) y **no se cambia** el modelo, la calibración, `data/processed/*`
ni `config/*.yaml`:

- El error no es de código ni de calibración: la calibración reproduce la definición del proyecto
  (Markov de 2 estados + gamma, Thom, temporada por zona) y el generador la implementa bien (V6
  sintético, V1 y V7 pasan).
- Cambiar a MLE no tiene efecto material. Cambiar la distribución del núcleo (exponencial mixta)
  mejora los momentos pero sigue sin pasar V6 en ningún grupo, porque el fallo del máximo por temporada
  viene de la heterogeneidad entre años. Además cambiaría el formato de configuración, la referencia
  analítica de V6/V7 y todos los resultados de X6 que se están produciendo con las configuraciones actuales.
- La corrección de fondo, un parámetro de intensidad aleatorio por temporada (gamma con escala por año,
  o separar "El Niño extraordinario" de "El Niño moderado"), cambia la definición del modelo y queda
  como trabajo futuro.

`v6_observado` sigue desactivada en el CTest por defecto (ver `CMakeLists.txt`); su resultado está
documentado aquí y no es un fallo del código.

## Impacto en el riesgo X6

P(Amax > U) con el balance de Lindley (C = 6 mm/día). Lo observado es la fracción de temporadas
históricas con Amax > U (un día faltante cuenta como 0 mm, así que es una cota inferior), con su
intervalo de Wilson al 95 %. El modelo usa 20 000 temporadas simuladas con la gamma actual.
Estaciones de trabajo (`data/processed/estaciones_seleccionadas.csv`), U = 50 mm:

| Grupo | Observado (k/n) | Wilson 95 % | Modelo actual | Sesgo |
| --- | --- | --- | --- | --- |
| lima_chosica / el_nino | 0/7 | [0; 0,35] | 0,000 | dentro |
| lima_chosica / normal | 0/16 | [0; 0,19] | 0,000 | dentro |
| piura_bernal / el_nino | 2/17 = 0,118 | [0,03; 0,34] | 0,185 | dentro (por encima) |
| piura_bernal / normal | 0/28 | [0; 0,12] | 0,000 | dentro |
| piura_miraflores / el_nino | 3/13 = 0,231 | [0,08; 0,50] | 0,589 | **sobrestima** |
| piura_miraflores / normal | 1/27 = 0,037 | [0,007; 0,18] | 0,000 | **subestima** |
| tumbes_eltigre / el_nino | 15/18 = 0,833 | [0,61; 0,94] | 0,908 | dentro (por encima) |
| tumbes_eltigre / normal | 15/29 = 0,517 | [0,34; 0,69] | 0,247 | **subestima** |
| tumbes_puertopizarro / el_nino | 9/17 = 0,529 | [0,31; 0,74] | 0,918 | **sobrestima** |
| tumbes_puertopizarro / normal | 10/30 = 0,333 | [0,19; 0,51] | 0,071 | **subestima** |

Para U = 30 y 80 mm el patrón es el mismo (ver `diagnostico_v6.log`). Dirección del sesgo:

- **Régimen normal: el modelo subestima P(Amax > U).** La cola ligera de la gamma genera pocos días
  intensos; con C = 6 mm/día se necesitan días muy por encima de la capacidad para acumular.
- **Régimen El Niño en Piura/Tumbes: el modelo sobrestima P(Amax > U).** La gamma se calibra con todos
  los años El Niño juntos, así que la intensidad de 1983/1998 se reparte en todas las temporadas
  simuladas, cuando en la realidad la mayoría de los años El Niño son moderados.
- Por lo tanto, la razón de riesgo El Niño / normal del modelo está **inflada** frente a lo histórico.
  Una cola más pesada (exponencial mixta) acerca el régimen normal (Puerto Pizarro 0,28; El Tigre 0,36)
  pero empeora El Niño (Puerto Pizarro
  0,94, Miraflores 0,68): no hay corrección i.i.d. que arregle ambos.

## Qué debe decir el informe

1. V6 frente al modelo pasa: el generador implementa correctamente la cadena de Markov + gamma.
2. V6 frente a lo observado reproduce frecuencia, media y rachas (< 1,1 % de error), pero no las colas:
   desviación −12 a −48 %, p99 hasta −55 %, KS rechaza en 16/16 grupos. Se descartaron con datos un error
   de implementación y el estimador (Thom ≈ MLE).
3. La causa es del modelo de la definición: una gamma de 2 parámetros, i.i.d. por temporada, no captura
   la cola pesada de la lluvia costera ni la diferencia entre eventos El Niño extraordinarios y moderados.
4. Las probabilidades de X6 deben leerse como **riesgo condicionado al modelo**: en años normales son una
   cota inferior probable del riesgo real; en años El Niño de Piura/Tumbes, una cota superior probable.
   El contraste El Niño / normal está exagerado. La banda epistémica del bootstrap (T35) **no** cubre este
   sesgo, porque remuestrea años pero sigue ajustando una sola gamma.
5. Trabajo futuro: intensidad aleatoria por temporada, o separar El Niño extraordinario de moderado,
   y volver a correr V6.
