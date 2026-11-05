# Sensibilidad de P(Amax > U) al umbral U y al régimen (X7)

> V6 (validación contra datos observados) falla en estadísticos de cola (sd -32 %, p99 -42 %) en 16/16 grupos: el modelo subestima los extremos y estas probabilidades pueden subestimar el riesgo hasta que la ola D recalibre.
> p_hist: la misma probabilidad leída de hist512 (control).

| estacion | regimen | capacidad | umbral | n | k | p_hat | wilson_inf | wilson_sup | p_hist |
|---|---|---|---|---|---|---|---|---|---|
| lima_chosica | normal | 6 | 30 | 10000000 | 0 | 0 | 0 | 3.841e-07 | 0 |
| lima_chosica | normal | 6 | 50 | 10000000 | 0 | 0 | 0 | 3.841e-07 | 0 |
| lima_chosica | normal | 6 | 80 | 10000000 | 0 | 0 | 0 | 3.841e-07 | 0 |
| lima_chosica | el_nino | 6 | 30 | 10000000 | 3070 | 0.000307 | 0.0002963 | 0.0003181 | 0.000307 |
| lima_chosica | el_nino | 6 | 50 | 10000000 | 16 | 1.6e-06 | 9.849e-07 | 2.599e-06 | 1.6e-06 |
| lima_chosica | el_nino | 6 | 80 | 10000000 | 0 | 0 | 0 | 3.841e-07 | 0 |
| piura_bernal | normal | 6 | 30 | 10000000 | 2882 | 0.0002882 | 0.0002779 | 0.0002989 | 0.0002882 |
| piura_bernal | normal | 6 | 50 | 10000000 | 14 | 1.4e-06 | 8.34e-07 | 2.35e-06 | 1.4e-06 |
| piura_bernal | normal | 6 | 80 | 10000000 | 0 | 0 | 0 | 3.841e-07 | 0 |
| piura_bernal | el_nino | 6 | 30 | 10000000 | 4692735 | 0.4693 | 0.469 | 0.4696 | 0.4693 |
| piura_bernal | el_nino | 6 | 50 | 10000000 | 1873438 | 0.1873 | 0.1871 | 0.1876 | 0.1873 |
| piura_bernal | el_nino | 6 | 80 | 10000000 | 411950 | 0.0412 | 0.04107 | 0.04132 | 0.0412 |
| piura_miraflores | normal | 6 | 30 | 10000000 | 86071 | 0.008607 | 0.00855 | 0.008665 | 0.008607 |
| piura_miraflores | normal | 6 | 50 | 10000000 | 2787 | 0.0002787 | 0.0002685 | 0.0002892 | 0.0002787 |
| piura_miraflores | normal | 6 | 80 | 10000000 | 23 | 2.3e-06 | 1.533e-06 | 3.451e-06 | 2.3e-06 |
| piura_miraflores | el_nino | 6 | 30 | 10000000 | 8653605 | 0.8654 | 0.8651 | 0.8656 | 0.8654 |
| piura_miraflores | el_nino | 6 | 50 | 10000000 | 5932147 | 0.5932 | 0.5929 | 0.5935 | 0.5932 |
| piura_miraflores | el_nino | 6 | 80 | 10000000 | 2576703 | 0.2577 | 0.2574 | 0.2579 | 0.2577 |
| tumbes_eltigre | normal | 6 | 30 | 10000000 | 6574197 | 0.6574 | 0.6571 | 0.6577 | 0.6574 |
| tumbes_eltigre | normal | 6 | 50 | 10000000 | 2518951 | 0.2519 | 0.2516 | 0.2522 | 0.2519 |
| tumbes_eltigre | normal | 6 | 80 | 10000000 | 442550 | 0.04426 | 0.04413 | 0.04438 | 0.04426 |
| tumbes_eltigre | el_nino | 6 | 30 | 10000000 | 9923724 | 0.9924 | 0.9923 | 0.9924 | 0.9924 |
| tumbes_eltigre | el_nino | 6 | 50 | 10000000 | 9081361 | 0.9081 | 0.908 | 0.9083 | 0.9081 |
| tumbes_eltigre | el_nino | 6 | 80 | 10000000 | 6324659 | 0.6325 | 0.6322 | 0.6328 | 0.6325 |
| tumbes_puertopizarro | normal | 6 | 30 | 10000000 | 3536812 | 0.3537 | 0.3534 | 0.354 | 0.3537 |
| tumbes_puertopizarro | normal | 6 | 50 | 10000000 | 729795 | 0.07298 | 0.07282 | 0.07314 | 0.07298 |
| tumbes_puertopizarro | normal | 6 | 80 | 10000000 | 57529 | 0.005753 | 0.005706 | 0.0058 | 0.005753 |
| tumbes_puertopizarro | el_nino | 6 | 30 | 10000000 | 9920910 | 0.9921 | 0.992 | 0.9921 | 0.9921 |
| tumbes_puertopizarro | el_nino | 6 | 50 | 10000000 | 9201396 | 0.9201 | 0.92 | 0.9203 | 0.9201 |
| tumbes_puertopizarro | el_nino | 6 | 80 | 10000000 | 6734797 | 0.6735 | 0.6732 | 0.6738 | 0.6735 |
