# Resultados científicos (X6, banda bootstrap, X7)

> **Advertencia (V6).** La validación V6 contra los datos observados falla en los estadísticos de cola
> (desviación estándar −32 %, percentil 99 −42 %) en 16/16 grupos estación × régimen: el generador de
> lluvia subestima los extremos. Las probabilidades de esta carpeta pueden **subestimar** el riesgo
> hasta que la ola D recalibre; cada tabla lleva la misma nota en la columna `nota`.

La pregunta es `P(Amax > U)`: la probabilidad de que el máximo acumulado de la temporada (balance de
Lindley con capacidad de drenaje `C` mm/día) supere el umbral `U` mm. El simulador da `k`
(inundaciones) y `n` (escenarios); `p̂ = k/n` e IC de Wilson al 95 %. Semántica completa en
[`docs/contratos.md`](../../docs/contratos.md) §2 y §5.

## Archivos

| Archivo | Script | Contenido |
| --- | --- | --- |
| `x6.csv` | `scripts/run/corrida-oficial.py` | X6: una fila del contrato (con `hist512`) por estación × régimen × `C`, `U` oficial (50 mm). |
| `x6_manifiesto.json` | idem | Commit, hardware, backend, semillas por configuración y duración de cada punto, por sesión. |
| `bootstrap.csv`, `bootstrap_manifiesto.json` | `analizar-riesgo.py bootstrap` | Mismas corridas sobre `K` réplicas bootstrap de los parámetros (`data/processed/bootstrap_parametros.csv`). |
| `tablas/riesgo.csv`, `.md` | `analizar-riesgo.py analizar` | `p̂`, IC de Wilson, `p_hist` (control desde `hist512`) y banda epistémica (percentiles 2,5/50/97,5 de `p̂` entre réplicas). |
| `tablas/comparacion_enso.csv`, `.md` | idem | El Niño frente a normal por `C`: riesgo relativo, diferencia, solape de IC y de bandas. |
| `x7.csv`, `x7_manifiesto.json` | `scripts/run/sensibilidad.py` | X7: `U ∈ {30, 50, 80}` mm × régimen, con la `C` de cada YAML. |
| `tablas/sensibilidad.csv`, `.md` | idem | `p̂`, IC de Wilson y `p_hist` por estación × régimen × `U`. |
| `logs/*.log` | todos | Salida del simulador (comando, resumen, `[verif]`, código de salida). |

Figuras en `results/figures/`: `riesgo_<estacion>` (curva riesgo–capacidad con IC y banda),
`riesgo_hist_<estacion>` (distribución y excedencia de `Amax` desde `hist512`),
`riesgo_comparacion_enso`, `sensibilidad_<estacion>` y `sensibilidad_resumen`, en PNG y SVG. El eje
vertical es logarítmico: los puntos con `p̂ = 0` no se dibujan (siguen en las tablas).

**Semillas.** Cada punto usa la `semilla` y el `config_id` de su YAML, sin cambiarlos al variar `C`,
`U` o los parámetros (números aleatorios comunes). La curva riesgo–capacidad es monótona y las
diferencias entre réplicas bootstrap reflejan solo los parámetros. Los scripts son reanudables: un
punto (estación, régimen, `C`, `U`, `N`, parámetros) que ya está en el CSV no se vuelve a correr.

## Cómo regenerar

En Git Bash, desde la raíz del repositorio, con la imagen `pp-g8`. Se compila una vez y luego se
corre cada paso (los tiempos son del Core Ultra 9 275HX, OpenMP con 16 hilos: ≈0,31 µs por
escenario, ≈9,6× el serial; el híbrido 2 × 8 fue más lento en un solo equipo, 0,55 µs).

```bash
pp() { MSYS_NO_PATHCONV=1 docker run --rm --shm-size=1g -e PP_COMMIT="$(git rev-parse --short HEAD)" \
  -v "$PWD:/work" -w /work pp-g8 bash -c "$1"; }

pp 'cmake -S . -B build-c -DCMAKE_BUILD_TYPE=Release -DPP_BUILD_MPI=ON && cmake --build build-c -j 16'

# X6: 10 configuraciones × 14 capacidades × 1e7 escenarios (≈8 min)
pp 'python3 scripts/run/corrida-oficial.py --n 1e7 --backend openmp --hilos 16'

# Banda epistémica: K = 100 réplicas × 14 capacidades × 1e6 (≈80 min; con --capacidades 2,4,6,8,10,12, ≈40 min)
pp 'python3 scripts/run/analizar-riesgo.py bootstrap --k 100 --n 1e6 --hilos 16'

# Tablas y figuras de riesgo
pp 'python3 scripts/run/analizar-riesgo.py analizar'

# X7: 10 configuraciones × 3 umbrales × 1e7 (≈2 min), con tablas y figuras
pp 'python3 scripts/run/sensibilidad.py --n 1e7 --hilos 16'
```

Cada script acepta `--dry-run` (lista los comandos pendientes), `--configs`, `--salida`, `--logs`,
`--manifiesto`, `--build-dir` y `--backend hibrido --procesos P --hilos H` (lanza
`mpirun -np P --bind-to none`). `--help` documenta el resto.
