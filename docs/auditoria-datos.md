# Auditoria de calidad de datos (T08)

**Responsable:** Angela · **Revisor:** David

Series reales descargadas del portal oficial de SENAMHI (cuenta registrada) para las 8 estaciones de [`inventario_senamhi.csv`](../data/metadata/inventario_senamhi.csv) (criterio de seleccion en [`criterio-seleccion-estaciones.md`](criterio-seleccion-estaciones.md)), convertidas con [`importar_senamhi.py`](../scripts/run/importar_senamhi.py). El generador sintetico ([`generar_datos_sinteticos.py`](../scripts/run/generar_datos_sinteticos.py)) queda como respaldo si alguna estacion real deja de estar disponible.

## Regla de exclusion

Una combinacion estacion/anio es elegible si tiene menos de 10% de dias faltantes **en la temporada de su zona** (no en el anio completo; definicion 6.2 y 7.6): costa norte usa enero-abril (120/121 dias); Lima usa junio-setiembre (122 dias, propuesta confirmada por Kevin/Rhamses el 2026-10-15, ver `docs/plan-desarrollo-semana-8.md`). No tiene valores negativos sin corregir. Una estacion completa es elegible si al menos el 90% de sus anios cumplen la regla anterior.

## Resultado por estacion

| ID | Estacion | Anios auditados | Anios elegibles | % faltantes promedio | Estacion elegible |
| --- | --- | --- | --- | --- | --- |
| piura_miraflores | Miraflores | 43 | 40 | 3.49% | Si |
| piura_chulucanas | Chulucanas | 43 | 31 | 19.98% | No |
| piura_bernal | Bernal | 51 | 45 | 6.96% | No |
| tumbes_puertopizarro | Puerto Pizarro | 52 | 47 | 4.05% | Si |
| tumbes_eltigre | El Tigre | 50 | 47 | 4.53% | Si |
| lambayeque_lambayeque | Lambayeque | 86 | 74 | 8.90% | No |
| lima_chosica | Chosica | 25 | 23 | 3.93% | Si |
| lima_canete | Cañete | 75 | 39 | 42.57% | No |

**Estaciones elegibles: 4 de 8** (criterio de T08 exige >= 3). Cumple.

## Reproducir

Tuberia completa de T08-T10 en la imagen `pp-g8` (las series de `data/raw/` ya estan en Git):

```bash
python3 scripts/run/auditoria_datos.py
python3 scripts/run/clasificar_regimenes.py
python3 scripts/run/calibrar.py --semilla 20261015
python3 scripts/run/generar_configs.py
```

Produce `data/processed/auditoria_calidad.csv` (una fila por estacion/anio; versionado en Git, igual que el resto de `data/processed`). `generar_configs.py` elige las 5 estaciones de trabajo (`data/processed/estaciones_seleccionadas.csv`) y escribe `config/<estacion>_<regimen>.yaml`. Este documento se regenera con cada corrida: si el script cambia, las cifras de arriba deben volver a calcularse con el mismo comando.
