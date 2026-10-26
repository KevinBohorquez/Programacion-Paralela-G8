"""T10 | Responsable: Angela.

Calibra p01, p11 (cadena de Markov humedo/seco) y alfa, theta (monto gamma de
los dias de lluvia) por estacion y regimen, a partir de las series diarias
auditadas (T08) y la clasificacion de regimen (T09). Genera ademas 100
remuestreos bootstrap por grupo (estacion x regimen) con una semilla
registrada, para que T35 construya bandas de incertidumbre.

Sigue la definicion del proyecto al pie de la letra (corregido tras el
hallazgo de V6 contra lo observado, que detecto una calibracion desviada):
solo la temporada de cada zona entra a la calibracion (costa norte:
enero-abril, D=120, definicion 6.2; Lima: junio-setiembre, propuesta
confirmada por Kevin/Rhamses el 2026-10-15 porque el evento que origina el
proyecto fue en agosto), un dia es "lluvioso" si precipitacion >= 0.1 mm, y
alfa/theta se ajustan con el metodo de Thom (1958), no por momentos. El
bootstrap remuestrea ANIOS con reemplazo (6.2/7.6: "remuestreo bootstrap de
los anios de la serie historica"), no bloques de dias.

Entradas:
    data/raw/<id_estacion>.csv        (T06: series SENAMHI versionadas; importar_senamhi.py)
    data/processed/auditoria_calidad.csv  (T08, para excluir anios no elegibles)
    data/processed/regimenes.csv      (T09)

Salidas:
    data/processed/parametros.csv          (una fila por estacion/regimen: estimacion puntual)
    data/processed/bootstrap_parametros.csv (100 filas por grupo: replicas 1-100)
    data/processed/calibracion_log.txt      (validacion: rangos y valores finitos)

Uso:
    python scripts/run/calibrar.py --semilla 20261015
"""

from __future__ import annotations

import argparse
import csv
import math
import random
import zlib
from collections import defaultdict
from pathlib import Path


def hash_estable(texto: str) -> int:
    """hash() de Python varia entre ejecuciones (PYTHONHASHSEED aleatorio por
    proceso): con la misma --semilla, dos corridas del script darian
    bootstrap_parametros.csv distintos. crc32 es determinista entre
    ejecuciones, maquinas y versiones de Python."""
    return zlib.crc32(texto.encode("utf-8"))

RAIZ = Path(__file__).resolve().parents[2]
INVENTARIO = RAIZ / "data" / "metadata" / "inventario_senamhi.csv"
RAW_DIR = RAIZ / "data" / "raw"
REGIMENES = RAIZ / "data" / "processed" / "regimenes.csv"
PARAMETROS_CSV = RAIZ / "data" / "processed" / "parametros.csv"
BOOTSTRAP_CSV = RAIZ / "data" / "processed" / "bootstrap_parametros.csv"
LOG_TXT = RAIZ / "data" / "processed" / "calibracion_log.txt"

N_BOOTSTRAP = 100


def cargar_regimenes() -> dict[tuple[str, int], str]:
    with REGIMENES.open(newline="", encoding="utf-8") as f:
        return {(f_["estacion"], int(f_["anio"])): f_["regimen"] for f_ in csv.DictReader(f)}


# Ventana por zona (confirmada por Kevin/Rhamses el 2026-10-15): costa norte
# usa enero-abril (D=120, definicion 6.2); Lima usa junio-setiembre (garua de
# invierno: el evento que origina el proyecto, Villa El Salvador, fue en
# agosto 2026). Excepcion: Chosica es un valle andino con lluvia convectiva
# de verano (huaico de 2017 en marzo), no garua costera -- usa enero-abril
# igual que costa norte (verificado: 8.1% de dias lluviosos en enero-abril
# vs 0.25% en junio-setiembre).
MESES_TEMPORADA_POR_ZONA = {
    "costa_norte": (1, 2, 3, 4),
    "lima": (6, 7, 8, 9),
}
MESES_TEMPORADA_OVERRIDE = {
    "lima_chosica": (1, 2, 3, 4),
}
UMBRAL_LLUVIA_MM = 0.1  # un dia es "lluvioso" si precipitacion >= 0.1 mm (definicion)


def cargar_zonas() -> dict[str, str]:
    with INVENTARIO.open(newline="", encoding="utf-8") as f:
        return {f_["id_estacion"]: f_["zona"] for f_ in csv.DictReader(f)}


def meses_temporada_de(id_est: str, zona: str) -> tuple[int, ...]:
    return MESES_TEMPORADA_OVERRIDE.get(id_est, MESES_TEMPORADA_POR_ZONA[zona])


def cargar_anios_por_grupo(
    regimen_por_anio: dict[tuple[str, int], str], zona_por_estacion: dict[str, str]
) -> dict[tuple[str, str], list[tuple[int, list[float | None]]]]:
    """Devuelve, por (estacion, regimen), la lista de (anio, serie_de_la_temporada)
    -- la temporada de la zona de cada anio elegible, en orden de fecha. Cada
    anio es la unidad de remuestreo bootstrap (definicion 6.2/7.6: "remuestreo
    bootstrap de los anios de la serie historica")."""
    grupos: dict[tuple[str, str], list[tuple[int, list[float | None]]]] = defaultdict(list)
    for ruta in sorted(RAW_DIR.glob("*.csv")):
        id_est = ruta.stem
        meses_temporada = meses_temporada_de(id_est, zona_por_estacion.get(id_est, "costa_norte"))
        with ruta.open(newline="", encoding="utf-8") as f:
            filas = list(csv.DictReader(f))

        por_temporada: dict[tuple[int, str], list[tuple[str, float | None]]] = defaultdict(list)
        for fila in filas:
            fecha = fila["fecha"]
            anio = int(fecha[:4])
            mes = int(fecha[5:7])
            if mes not in meses_temporada:
                continue  # fuera de la temporada de la zona: no entra a la calibracion
            regimen = regimen_por_anio.get((id_est, anio))
            if regimen is None:
                continue  # anio excluido por T08/T09
            valor = fila["precipitacion_mm"]
            if valor == "" or float(valor) < 0:
                v = None
            else:
                v = float(valor)
            por_temporada[(anio, regimen)].append((fecha, v))

        for (anio, regimen), dias in sorted(por_temporada.items()):
            dias.sort(key=lambda t: t[0])
            grupos[(id_est, regimen)].append((anio, [v for _, v in dias]))
    return grupos


def aplanar(anios: list[tuple[int, list[float | None]]]) -> list[float | None]:
    """Concatena las series de varios anios separandolas con None, para que
    las transiciones Markov no crucen de un anio a otro."""
    serie: list[float | None] = []
    for _, dias in anios:
        serie.append(None)
        serie.extend(dias)
    return serie


def estimar_markov(serie: list[float | None]) -> tuple[float, float]:
    """p01 = P(lluvia hoy | seco ayer); p11 = P(lluvia hoy | lluvia ayer).
    Los pares con un dia faltante se excluyen (no se asume seco ni lluvia)."""
    c01 = c0 = c11 = c1 = 0
    for ayer, hoy in zip(serie, serie[1:]):
        if ayer is None or hoy is None:
            continue
        seco_ayer = ayer < UMBRAL_LLUVIA_MM
        llueve_hoy = hoy >= UMBRAL_LLUVIA_MM
        if seco_ayer:
            c0 += 1
            c01 += int(llueve_hoy)
        else:
            c1 += 1
            c11 += int(llueve_hoy)
    p01 = c01 / c0 if c0 else 0.0
    p11 = c11 / c1 if c1 else 0.0
    return p01, p11


def estimar_gamma(montos_lluvia: list[float]) -> tuple[float, float]:
    """Metodo de Thom (1958), aproximacion de maxima verosimilitud estandar
    para ajustar una gamma a montos de lluvia: con D = ln(media) - media(ln(x)),
    alfa = (1 + sqrt(1 + 4D/3)) / (4D) y theta = media / alfa."""
    n = len(montos_lluvia)
    if n < 2:
        return 1.0, 1.0
    media = sum(montos_lluvia) / n
    if media <= 0:
        return 1.0, 1.0
    log_media = sum(math.log(x) for x in montos_lluvia) / n
    d_stat = math.log(media) - log_media
    if d_stat <= 0:
        # Degenerado (todos los montos casi iguales): sin informacion de forma.
        return 1.0, media
    alfa = (1.0 + math.sqrt(1.0 + 4.0 * d_stat / 3.0)) / (4.0 * d_stat)
    theta = media / alfa
    return alfa, theta


def remuestrear_anios(
    anios: list[tuple[int, list[float | None]]], rng: random.Random
) -> list[float | None]:
    """Bootstrap de anios (definicion 6.2/7.6): remuestrea los anios
    disponibles CON REEMPLAZO, mismo tamanio de muestra, y concatena sus
    series de temporada (separadas por None) para recalibrar sobre eso."""
    elegidos = [anios[rng.randrange(0, len(anios))] for _ in range(len(anios))]
    return aplanar(elegidos)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--semilla", type=int, default=20261015, help="Semilla de remuestreo (se registra en el CSV).")
    args = parser.parse_args()

    if not REGIMENES.exists():
        print(f"No existe {REGIMENES}; ejecutar scripts/run/clasificar_regimenes.py primero.")
        return 2
    if not RAW_DIR.exists() or not any(RAW_DIR.glob("*.csv")):
        print(f"No hay series en {RAW_DIR}; ejecutar scripts/run/generar_datos_sinteticos.py primero.")
        return 2

    regimen_por_anio = cargar_regimenes()
    zona_por_estacion = cargar_zonas()
    grupos = cargar_anios_por_grupo(regimen_por_anio, zona_por_estacion)

    PARAMETROS_CSV.parent.mkdir(parents=True, exist_ok=True)
    filas_parametros = []
    filas_bootstrap = []
    lineas_log = []

    for (id_est, regimen), anios in sorted(grupos.items()):
        serie = aplanar(anios)
        p01, p11 = estimar_markov(serie)
        montos_lluvia = [v for v in serie if v is not None and v >= UMBRAL_LLUVIA_MM]
        alfa, theta = estimar_gamma(montos_lluvia)
        n_dias = len(serie)
        n_faltantes = sum(1 for v in serie if v is None)
        n_anios = len(anios)

        finito = all(math.isfinite(x) for x in (p01, p11, alfa, theta))
        en_rango = 0.0 <= p01 <= 1.0 and 0.0 <= p11 <= 1.0 and alfa > 0 and theta > 0
        estado = "OK" if finito and en_rango else "FALLA"
        lineas_log.append(
            f"[{id_est}/{regimen}] n_anios={n_anios} n_dias={n_dias} faltantes={n_faltantes} "
            f"p01={p01:.4f} p11={p11:.4f} alfa={alfa:.4f} theta={theta:.4f} estado={estado}"
        )

        filas_parametros.append(
            {
                "estacion": id_est,
                "regimen": regimen,
                "n_anios": n_anios,
                "n_dias": n_dias,
                "n_dias_lluvia": len(montos_lluvia),
                "p01": round(p01, 6),
                "p11": round(p11, 6),
                "alfa": round(alfa, 6),
                "theta": round(theta, 6),
                "semilla_remuestreo": args.semilla,
                "n_bootstrap": N_BOOTSTRAP,
                "estado_validacion": estado,
            }
        )

        rng = random.Random(args.semilla ^ hash_estable(f"{id_est}/{regimen}"))
        for replica in range(1, N_BOOTSTRAP + 1):
            muestra = remuestrear_anios(anios, rng)
            p01_b, p11_b = estimar_markov(muestra)
            montos_b = [v for v in muestra if v is not None and v >= UMBRAL_LLUVIA_MM]
            alfa_b, theta_b = estimar_gamma(montos_b)
            filas_bootstrap.append(
                {
                    "estacion": id_est,
                    "regimen": regimen,
                    "replica": replica,
                    "semilla_remuestreo": args.semilla,
                    "p01": round(p01_b, 6),
                    "p11": round(p11_b, 6),
                    "alfa": round(alfa_b, 6),
                    "theta": round(theta_b, 6),
                }
            )

    with PARAMETROS_CSV.open("w", newline="", encoding="utf-8") as out:
        campos = [
            "estacion", "regimen", "n_anios", "n_dias", "n_dias_lluvia", "p01", "p11", "alfa", "theta",
            "semilla_remuestreo", "n_bootstrap", "estado_validacion",
        ]
        escritor = csv.DictWriter(out, fieldnames=campos)
        escritor.writeheader()
        escritor.writerows(filas_parametros)

    with BOOTSTRAP_CSV.open("w", newline="", encoding="utf-8") as out:
        campos = ["estacion", "regimen", "replica", "semilla_remuestreo", "p01", "p11", "alfa", "theta"]
        escritor = csv.DictWriter(out, fieldnames=campos)
        escritor.writeheader()
        escritor.writerows(filas_bootstrap)

    LOG_TXT.write_text("\n".join(lineas_log) + "\n", encoding="utf-8")

    print(f"{PARAMETROS_CSV.relative_to(RAIZ)}: {len(filas_parametros)} grupos estacion/regimen")
    print(f"{BOOTSTRAP_CSV.relative_to(RAIZ)}: {len(filas_bootstrap)} replicas ({N_BOOTSTRAP} por grupo)")
    fallas = [l for l in lineas_log if "FALLA" in l]
    if fallas:
        print("Fallas de validacion:\n" + "\n".join(fallas))
        return 3
    print("Validacion OK: todos los parametros son finitos y estan en rango.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
