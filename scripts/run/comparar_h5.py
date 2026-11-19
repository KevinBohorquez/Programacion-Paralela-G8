#!/usr/bin/env python3
"""T13 | Responsable: Lita | Compara el riesgo X6/X7 sin H5 (kappa = inf) y con H5 (kappa calibrado).

Lee las tablas que ya generaron analizar-riesgo.py y sensibilidad.py para los dos modelos y escribe
una tabla por estación × régimen en la capacidad de referencia (6 mm/día) y para cada umbral de X7:

    python3 scripts/run/comparar_h5.py
    python3 scripts/run/comparar_h5.py --sin results/cientifico/tablas --con results/cientifico/tablas_h5

No corre simulaciones: solo cruza resultados ya medidos.
"""
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("_comun_cientifico", RAIZ / "scripts/run/_comun_cientifico.py")
comun = importlib.util.module_from_spec(_spec)
sys.modules["_comun_cientifico"] = comun
_spec.loader.exec_module(comun)

CAMPOS_X6 = ["estacion", "regimen", "capacidad", "umbral", "p_sin_h5", "banda_sin_h5", "p_con_h5",
             "banda_con_h5", "cambio_absoluto", "razon"]
CAMPOS_X7 = ["estacion", "regimen", "umbral", "p_sin_h5", "p_con_h5", "cambio_absoluto", "razon"]
CAMPOS_ENSO = ["estacion", "riesgo_relativo_sin_h5", "riesgo_relativo_con_h5"]


def _indice(filas, campos):
    return {tuple(f[c] if c in ("estacion", "regimen") else comun.num(f[c]) for c in campos): f for f in filas}


def _p(f):
    return float(f["p_hat"])


def _banda(f):
    if not f.get("banda_inf"):
        return "—"
    return f"{float(f['banda_inf']):.4g}–{float(f['banda_sup']):.4g}"


def _razon(con, sin):
    return con / sin if sin > 0 else float("nan")


def comparar(sin: Path, con: Path, capacidad: float) -> tuple[list, list, list]:
    claves = ("estacion", "regimen", "capacidad", "umbral")
    r_sin = _indice(comun.leer_resultados(sin / "riesgo.csv"), claves)
    r_con = _indice(comun.leer_resultados(con / "riesgo.csv"), claves)
    x6 = []
    for clave in sorted(set(r_sin) & set(r_con)):
        if clave[2] != comun.num(capacidad):
            continue
        a, b = r_sin[clave], r_con[clave]
        x6.append({"estacion": clave[0], "regimen": clave[1], "capacidad": clave[2], "umbral": clave[3],
                   "p_sin_h5": _p(a), "banda_sin_h5": _banda(a), "p_con_h5": _p(b), "banda_con_h5": _banda(b),
                   "cambio_absoluto": _p(b) - _p(a), "razon": _razon(_p(b), _p(a))})

    s_sin = _indice(comun.leer_resultados(sin / "sensibilidad.csv"), claves)
    s_con = _indice(comun.leer_resultados(con / "sensibilidad.csv"), claves)
    x7 = []
    for clave in sorted(set(s_sin) & set(s_con)):
        a, b = _p(s_sin[clave]), _p(s_con[clave])
        x7.append({"estacion": clave[0], "regimen": clave[1], "umbral": clave[3], "p_sin_h5": a,
                   "p_con_h5": b, "cambio_absoluto": b - a, "razon": _razon(b, a)})

    e_sin = _indice(comun.leer_resultados(sin / "comparacion_enso.csv"), ("estacion", "capacidad", "umbral"))
    e_con = _indice(comun.leer_resultados(con / "comparacion_enso.csv"), ("estacion", "capacidad", "umbral"))
    rr = lambda f: float(f["riesgo_relativo"]) if f["riesgo_relativo"] else "—"  # noqa: E731
    enso = [{"estacion": c[0], "riesgo_relativo_sin_h5": rr(e_sin[c]), "riesgo_relativo_con_h5": rr(e_con[c])}
            for c in sorted(set(e_sin) & set(e_con)) if c[1] == comun.num(capacidad)]
    return x6, x7, enso


def main(argv=None):
    ap = argparse.ArgumentParser(description="Compara X6/X7 sin H5 y con H5 (T13).")
    ap.add_argument("--sin", type=Path, default=RAIZ / "results/cientifico/tablas")
    ap.add_argument("--con", type=Path, default=RAIZ / "results/cientifico/tablas_h5")
    ap.add_argument("--capacidad", type=float, default=6.0, help="capacidad de referencia (mm/día)")
    ap.add_argument("--destino", type=Path, default=None, help="por defecto, la carpeta de --con")
    args = ap.parse_args(argv)
    destino = args.destino or args.con
    x6, x7, enso = comparar(args.sin, args.con, args.capacidad)
    comun.escribir_tabla(destino / "comparacion_h5_x6.csv", x6, CAMPOS_X6)
    comun.escribir_tabla(destino / "comparacion_h5_x7.csv", x7, CAMPOS_X7)
    notas = ["Sin H5: kappa = inf (modelo de master). Con H5: kappa calibrado por estación × régimen "
             "(rama lita-h5-kappa). Misma semilla, mismo n y mismos (p01, p11, alfa, theta).",
             "banda = percentiles 2,5–97,5 del bootstrap de parámetros (100 réplicas, n = 10^6)."]
    comun.escribir_markdown(destino / "comparacion_h5_x6.md",
                            f"Riesgo X6 sin H5 y con H5 (C = {args.capacidad:g} mm/día)", x6, CAMPOS_X6, notas)
    comun.escribir_markdown(destino / "comparacion_h5_x7.md", "Sensibilidad X7 al umbral sin H5 y con H5",
                            x7, CAMPOS_X7, notas[:1])
    comun.escribir_markdown(destino / "comparacion_h5_enso.md",
                            f"Riesgo relativo El Niño / normal sin H5 y con H5 (C = {args.capacidad:g} mm/día)",
                            enso, CAMPOS_ENSO, notas[:1])
    print(f"[h5] {len(x6)} filas X6, {len(x7)} filas X7, {len(enso)} estaciones ENSO -> {destino}")


if __name__ == "__main__":
    main()
