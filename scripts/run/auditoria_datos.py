"""T08 | Responsable: Angela.

Audita faltantes, duplicados, valores negativos y atipicos de cada serie
diaria, restringido a la temporada enero-abril (D=120 dias, definicion 6.2),
y aplica la regla de exclusion tal cual el documento de definicion (7.6):
una estacion/anio es elegible si tiene menos de 10% de dias faltantes EN LA
TEMPORADA (no en el anio completo).

Salidas:
    data/processed/auditoria_calidad.csv  (una fila por estacion/anio)
    docs/auditoria-datos.md               (resumen legible, ya incluye la
                                            tabla con los resultados de esta
                                            corrida para no depender de que el
                                            lector ejecute el script)

Uso:
    python scripts/run/auditoria_datos.py
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
INVENTARIO = RAIZ / "data" / "metadata" / "inventario_senamhi.csv"
RAW_DIR = RAIZ / "data" / "raw"
SALIDA_CSV = RAIZ / "data" / "processed" / "auditoria_calidad.csv"
SALIDA_MD = RAIZ / "docs" / "auditoria-datos.md"

UMBRAL_FALTANTES = 0.10
UMBRAL_ATIPICO_MM = 150.0  # mm en un dia; por encima se marca para revision manual, no se descarta.

# Ventana de temporada por zona: costa norte usa enero-abril (definicion 6.2,
# El Nino costero); Lima usa junio-setiembre (garua de invierno: el evento
# que origina el proyecto, Villa El Salvador, fue en agosto 2026 -- ver
# referencia [20] de la definicion). Propuesta confirmada por Kevin/Rhamses
# el 2026-10-15.
MESES_TEMPORADA_POR_ZONA = {
    "costa_norte": (1, 2, 3, 4),
    "lima": (6, 7, 8, 9),
}

# Chosica es un valle andino (Rimac, ~860 m) con lluvia convectiva de verano
# -- el huaico de 2017 que la hizo famosa fue en marzo -- no garua costera
# como el resto de Lima (verificado en los datos: 8.1% de dias lluviosos en
# enero-abril vs 0.25% en junio-setiembre). Usa la temporada de costa norte
# en vez de la de su zona. Ajuste confirmado por Kevin/Rhamses el 2026-10-15.
MESES_TEMPORADA_OVERRIDE = {
    "lima_chosica": (1, 2, 3, 4),
}


def meses_temporada_de(id_est: str, zona: str) -> tuple[int, ...]:
    return MESES_TEMPORADA_OVERRIDE.get(id_est, MESES_TEMPORADA_POR_ZONA[zona])


def dias_temporada(anio: int, meses_temporada: tuple[int, ...]) -> int:
    """Dias de la temporada. Enero-abril: 120 o 121 en anio bisiesto (29 de
    febrero). Junio-setiembre: 122, sin bisiesto."""
    if meses_temporada == (1, 2, 3, 4):
        bisiesto = anio % 4 == 0 and (anio % 100 != 0 or anio % 400 == 0)
        return 31 + (29 if bisiesto else 28) + 31 + 30
    return 30 + 31 + 31 + 30  # jun+jul+ago+set


def auditar_estacion(id_est: str, ruta: Path, zona: str) -> list[dict]:
    meses_temporada = meses_temporada_de(id_est, zona)
    with ruta.open(newline="", encoding="utf-8") as f:
        filas_crudas = list(csv.DictReader(f))

    por_anio: dict[int, list[dict]] = defaultdict(list)
    vistos: dict[tuple[int, str], int] = defaultdict(int)
    duplicados_por_anio: dict[int, int] = defaultdict(int)

    for fila in filas_crudas:
        fecha = dt.date.fromisoformat(fila["fecha"])
        if fecha.month not in meses_temporada:
            continue  # fuera de la temporada de la zona: no entra a la auditoria (6.2 / 7.6)
        clave = (fecha.year, fila["fecha"])
        vistos[clave] += 1
        if vistos[clave] > 1:
            duplicados_por_anio[fecha.year] += 1
        por_anio[fecha.year].append(fila)

    resultados = []
    for anio in sorted(por_anio):
        filas_anio = por_anio[anio]
        esperados = dias_temporada(anio, meses_temporada)
        faltantes = sum(1 for r in filas_anio if r["precipitacion_mm"] == "")
        negativos = sum(1 for r in filas_anio if r["precipitacion_mm"] not in ("",) and float(r["precipitacion_mm"]) < 0)
        atipicos = sum(
            1 for r in filas_anio
            if r["precipitacion_mm"] not in ("",) and float(r["precipitacion_mm"]) > UMBRAL_ATIPICO_MM
        )
        observados = len(filas_anio) - duplicados_por_anio.get(anio, 0)
        pct_faltantes = faltantes / esperados if esperados else 1.0
        elegible = pct_faltantes < UMBRAL_FALTANTES and negativos == 0

        resultados.append(
            {
                "estacion": id_est,
                "anio": anio,
                "dias_esperados": esperados,
                "dias_observados": observados,
                "dias_faltantes": faltantes,
                "pct_faltantes": round(pct_faltantes, 4),
                "duplicados": duplicados_por_anio.get(anio, 0),
                "valores_negativos": negativos,
                "atipicos_gt_150mm": atipicos,
                "elegible": elegible,
                "regla_exclusion": "" if elegible else (
                    "faltantes>=10%" if pct_faltantes >= UMBRAL_FALTANTES else "valores_negativos_sin_corregir"
                ),
            }
        )
    return resultados


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()

    if not INVENTARIO.exists():
        print(f"No existe {INVENTARIO}; ejecutar T06 primero.")
        return 2
    if not RAW_DIR.exists() or not any(RAW_DIR.glob("*.csv")):
        print(f"No hay series en {RAW_DIR}; ejecutar scripts/run/generar_datos_sinteticos.py primero.")
        return 2

    with INVENTARIO.open(newline="", encoding="utf-8") as f:
        estaciones = list(csv.DictReader(f))

    todas_filas: list[dict] = []
    for fila in estaciones:
        id_est = fila["id_estacion"]
        zona = fila["zona"]
        ruta = RAW_DIR / f"{id_est}.csv"
        if not ruta.exists():
            print(f"Aviso: falta {ruta}, se omite {id_est} ({fila['nombre_estacion']}).")
            continue
        todas_filas.extend(auditar_estacion(id_est, ruta, zona))

    SALIDA_CSV.parent.mkdir(parents=True, exist_ok=True)
    campos = [
        "estacion", "anio", "dias_esperados", "dias_observados", "dias_faltantes",
        "pct_faltantes", "duplicados", "valores_negativos", "atipicos_gt_150mm",
        "elegible", "regla_exclusion",
    ]
    with SALIDA_CSV.open("w", newline="", encoding="utf-8") as out:
        escritor = csv.DictWriter(out, fieldnames=campos)
        escritor.writeheader()
        escritor.writerows(todas_filas)

    nombres = {f["id_estacion"]: f["nombre_estacion"] for f in estaciones}
    por_estacion: dict[str, list[dict]] = defaultdict(list)
    for fila in todas_filas:
        por_estacion[fila["estacion"]].append(fila)

    resumen_lineas = []
    estaciones_elegibles = 0
    for id_est, filas in por_estacion.items():
        anios_elegibles = sum(1 for f in filas if f["elegible"])
        anios_totales = len(filas)
        pct_prom = sum(f["pct_faltantes"] for f in filas) / anios_totales if anios_totales else 0.0
        estacion_elegible = anios_elegibles / anios_totales >= 0.9 if anios_totales else False
        if estacion_elegible:
            estaciones_elegibles += 1
        resumen_lineas.append(
            f"| {id_est} | {nombres.get(id_est, '?')} | {anios_totales} | {anios_elegibles} | "
            f"{pct_prom * 100:.2f}% | {'Si' if estacion_elegible else 'No'} |"
        )

    SALIDA_MD.parent.mkdir(parents=True, exist_ok=True)
    SALIDA_MD.write_text(
        "# Auditoria de calidad de datos (T08)\n\n"
        "**Responsable:** Angela · **Revisor:** David\n\n"
        "Series reales descargadas del portal oficial de SENAMHI (cuenta registrada) "
        "para las 8 estaciones de [`inventario_senamhi.csv`](../data/metadata/inventario_senamhi.csv) "
        "(criterio de seleccion en [`criterio-seleccion-estaciones.md`](criterio-seleccion-estaciones.md)), "
        "convertidas con [`importar_senamhi.py`](../scripts/run/importar_senamhi.py). "
        "El generador sintetico ([`generar_datos_sinteticos.py`](../scripts/run/generar_datos_sinteticos.py)) "
        "queda como respaldo si alguna estacion real deja de estar disponible.\n\n"
        "## Regla de exclusion\n\n"
        f"Una combinacion estacion/anio es elegible si tiene menos de {UMBRAL_FALTANTES*100:.0f}% "
        "de dias faltantes **en la temporada de su zona** (no en el anio completo; definicion 6.2 y 7.6): "
        "costa norte usa enero-abril (120/121 dias); Lima usa junio-setiembre (122 dias, propuesta "
        "confirmada por Kevin/Rhamses el 2026-10-15, ver `docs/plan-desarrollo-semana-8.md`). No tiene "
        "valores negativos sin corregir. Una estacion completa es elegible si al menos el 90% de sus "
        "anios cumplen la regla anterior.\n\n"
        "## Resultado por estacion\n\n"
        "| ID | Estacion | Anios auditados | Anios elegibles | % faltantes promedio | Estacion elegible |\n"
        "| --- | --- | --- | --- | --- | --- |\n"
        + "\n".join(resumen_lineas) + "\n\n"
        f"**Estaciones elegibles: {estaciones_elegibles} de {len(por_estacion)}** "
        f"(criterio de T08 exige >= 3). "
        + ("Cumple." if estaciones_elegibles >= 3 else "No cumple; revisar el inventario de T06.") + "\n\n"
        "## Reproducir\n\n"
        "Tuberia completa de T08-T10 en la imagen `pp-g8` (las series de `data/raw/` ya estan en Git):\n\n"
        "```bash\n"
        "python3 scripts/run/auditoria_datos.py\n"
        "python3 scripts/run/clasificar_regimenes.py\n"
        "python3 scripts/run/calibrar.py --semilla 20261015\n"
        "python3 scripts/run/generar_configs.py\n"
        "```\n\n"
        "Produce `data/processed/auditoria_calidad.csv` (una fila por estacion/anio; "
        "versionado en Git, igual que el resto de `data/processed`). `generar_configs.py` elige las 5 "
        "estaciones de trabajo (`data/processed/estaciones_seleccionadas.csv`) y escribe "
        "`config/<estacion>_<regimen>.yaml`. "
        "Este documento se regenera con cada corrida: si el script cambia, "
        "las cifras de arriba deben volver a calcularse con el mismo comando.\n",
        encoding="utf-8",
    )

    print(f"Auditoria escrita en {SALIDA_CSV.relative_to(RAIZ)} y {SALIDA_MD.relative_to(RAIZ)}")
    print(f"Estaciones elegibles: {estaciones_elegibles} de {len(por_estacion)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
