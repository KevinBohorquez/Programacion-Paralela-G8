# Sensibilidad de P(Amax > U) al umbral U y al régimen (X7)

> Modelo con escala aleatoria por temporada (H5, kappa calibrado por grupo): V6 frente a lo observado pasa en 16/16 grupos (7 estadísticos y KS); ver docs/validacion-v6.md.
> p_hist: la misma probabilidad leída de hist512 (control).

| estacion | regimen | capacidad | umbral | n | k | p_hat | wilson_inf | wilson_sup | p_hist |
|---|---|---|---|---|---|---|---|---|---|
| lima_chosica | normal | 6 | 30 | 10000000 | 442 | 4.42e-05 | 4.027e-05 | 4.852e-05 | 4.42e-05 |
| lima_chosica | normal | 6 | 50 | 10000000 | 5 | 5e-07 | 2.136e-07 | 1.171e-06 | 5e-07 |
| lima_chosica | normal | 6 | 80 | 10000000 | 0 | 0 | 0 | 3.841e-07 | 0 |
| lima_chosica | el_nino | 6 | 30 | 10000000 | 412005 | 0.0412 | 0.04108 | 0.04132 | 0.0412 |
| lima_chosica | el_nino | 6 | 50 | 10000000 | 146333 | 0.01463 | 0.01456 | 0.01471 | 0.01463 |
| lima_chosica | el_nino | 6 | 80 | 10000000 | 41645 | 0.004164 | 0.004125 | 0.004205 | 0.004164 |
| piura_bernal | normal | 6 | 30 | 10000000 | 159596 | 0.01596 | 0.01588 | 0.01604 | 0.01596 |
| piura_bernal | normal | 6 | 50 | 10000000 | 33016 | 0.003302 | 0.003266 | 0.003337 | 0.003302 |
| piura_bernal | normal | 6 | 80 | 10000000 | 4782 | 0.0004782 | 0.0004648 | 0.0004919 | 0.0004782 |
| piura_bernal | el_nino | 6 | 30 | 10000000 | 3601760 | 0.3602 | 0.3599 | 0.3605 | 0.3602 |
| piura_bernal | el_nino | 6 | 50 | 10000000 | 2272667 | 0.2273 | 0.227 | 0.2275 | 0.2273 |
| piura_bernal | el_nino | 6 | 80 | 10000000 | 1254919 | 0.1255 | 0.1253 | 0.1257 | 0.1255 |
| piura_miraflores | normal | 6 | 30 | 10000000 | 797666 | 0.07977 | 0.0796 | 0.07993 | 0.07977 |
| piura_miraflores | normal | 6 | 50 | 10000000 | 320587 | 0.03206 | 0.03195 | 0.03217 | 0.03206 |
| piura_miraflores | normal | 6 | 80 | 10000000 | 103642 | 0.01036 | 0.0103 | 0.01043 | 0.01036 |
| piura_miraflores | el_nino | 6 | 30 | 10000000 | 7146925 | 0.7147 | 0.7144 | 0.715 | 0.7147 |
| piura_miraflores | el_nino | 6 | 50 | 10000000 | 4971881 | 0.4972 | 0.4969 | 0.4975 | 0.4972 |
| piura_miraflores | el_nino | 6 | 80 | 10000000 | 2832919 | 0.2833 | 0.283 | 0.2836 | 0.2833 |
| tumbes_eltigre | normal | 6 | 30 | 10000000 | 4880430 | 0.488 | 0.4877 | 0.4884 | 0.488 |
| tumbes_eltigre | normal | 6 | 50 | 10000000 | 3038980 | 0.3039 | 0.3036 | 0.3042 | 0.3039 |
| tumbes_eltigre | normal | 6 | 80 | 10000000 | 1637591 | 0.1638 | 0.1635 | 0.164 | 0.1638 |
| tumbes_eltigre | el_nino | 6 | 30 | 10000000 | 7435325 | 0.7435 | 0.7433 | 0.7438 | 0.7435 |
| tumbes_eltigre | el_nino | 6 | 50 | 10000000 | 6030314 | 0.603 | 0.6027 | 0.6033 | 0.603 |
| tumbes_eltigre | el_nino | 6 | 80 | 10000000 | 4611004 | 0.4611 | 0.4608 | 0.4614 | 0.4611 |
| tumbes_puertopizarro | normal | 6 | 30 | 10000000 | 3347923 | 0.3348 | 0.3345 | 0.3351 | 0.3348 |
| tumbes_puertopizarro | normal | 6 | 50 | 10000000 | 1966270 | 0.1966 | 0.1964 | 0.1969 | 0.1966 |
| tumbes_puertopizarro | normal | 6 | 80 | 10000000 | 1006063 | 0.1006 | 0.1004 | 0.1008 | 0.1006 |
| tumbes_puertopizarro | el_nino | 6 | 30 | 10000000 | 8066620 | 0.8067 | 0.8064 | 0.8069 | 0.8067 |
| tumbes_puertopizarro | el_nino | 6 | 50 | 10000000 | 6620284 | 0.662 | 0.6617 | 0.6623 | 0.662 |
| tumbes_puertopizarro | el_nino | 6 | 80 | 10000000 | 4967905 | 0.4968 | 0.4965 | 0.4971 | 0.4968 |
