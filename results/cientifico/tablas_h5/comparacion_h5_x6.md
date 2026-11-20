# Riesgo X6 sin H5 y con H5 (C = 6 mm/día)

> Sin H5: kappa = inf (modelo de master). Con H5: kappa calibrado por estación × régimen (rama lita-h5-kappa). Misma semilla, mismo n y mismos (p01, p11, alfa, theta).
> banda = percentiles 2,5–97,5 del bootstrap de parámetros (100 réplicas, n = 10^6).

| estacion | regimen | capacidad | umbral | p_sin_h5 | banda_sin_h5 | p_con_h5 | banda_con_h5 | cambio_absoluto | razon |
|---|---|---|---|---|---|---|---|---|---|
| lima_chosica | el_nino | 6 | 50 | 1.6e-06 | 0–0.002815 | 0.01463 | 0–0.04321 | 0.01463 | 9146 |
| lima_chosica | normal | 6 | 50 | 0 | 0–0 | 5e-07 | 0–3.473e-05 | 5e-07 | — |
| piura_bernal | el_nino | 6 | 50 | 0.1873 | 0.0005255–0.681 | 0.2273 | 0.023–0.5321 | 0.03992 | 1.213 |
| piura_bernal | normal | 6 | 50 | 1.4e-06 | 0–9.315e-05 | 0.003302 | 6.515e-05–0.01217 | 0.0033 | 2358 |
| piura_miraflores | el_nino | 6 | 50 | 0.5932 | 0.001444–0.9517 | 0.4972 | 0.04533–0.9361 | -0.09603 | 0.8381 |
| piura_miraflores | normal | 6 | 50 | 0.0002787 | 0–0.01145 | 0.03206 | 0.0006471–0.08147 | 0.03178 | 115 |
| tumbes_eltigre | el_nino | 6 | 50 | 0.9081 | 0.5597–0.9906 | 0.603 | 0.4204–0.7322 | -0.3051 | 0.664 |
| tumbes_eltigre | normal | 6 | 50 | 0.2519 | 0.1001–0.4681 | 0.3039 | 0.2145–0.4053 | 0.052 | 1.206 |
| tumbes_puertopizarro | el_nino | 6 | 50 | 0.9201 | 0.2187–0.9938 | 0.662 | 0.2871–0.8542 | -0.2581 | 0.7195 |
| tumbes_puertopizarro | normal | 6 | 50 | 0.07298 | 0.01957–0.1819 | 0.1966 | 0.1218–0.2662 | 0.1236 | 2.694 |
