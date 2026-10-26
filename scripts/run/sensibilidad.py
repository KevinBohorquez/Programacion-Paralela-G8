#!/usr/bin/env python3
"""T42 | Responsable: Angela | Experimento X7: sensibilidad del riesgo al umbral U y al régimen.

Corre el simulador para U ∈ {30, 50, 80} mm en las 10 configuraciones estación × régimen (normal y
El Niño), con la capacidad C de cada YAML o, con --capacidades, una grilla de C. Agrega las filas del
contrato a results/cientifico/x7.csv (reanudable, --dry-run, manifiesto y logs como X6) y luego
escribe results/cientifico/tablas/sensibilidad.csv/.md y las figuras
results/figures/sensibilidad_<estacion>.png/svg y sensibilidad_resumen.png/svg.

La tabla incluye p_hist: P(Amax > U) leída del histograma hist512 de la misma fila. Para U entero
debe coincidir con p̂ = k/n; es un control de consistencia entre el criterio de inundación y el
histograma.

Uso (en la imagen pp-g8, tras compilar en build-c):
    python3 scripts/run/sensibilidad.py --dry-run
    python3 scripts/run/sensibilidad.py --n 1e7
    python3 scripts/run/sensibilidad.py --solo-analisis      # tablas y figuras desde x7.csv
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _comun_cientifico as comun  # noqa: E402

UMBRALES_X7 = (30, 50, 80)
ORDEN_REGIMEN = {"normal": 0, "el_nino": 1}
NOMBRE_REGIMEN = {"normal": "Normal", "el_nino": "El Niño"}
ESTILO_REGIMEN = {"normal": "-", "el_nino": "--"}
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
CAMPOS = ["estacion", "regimen", "capacidad", "umbral", "n", "k", "p_hat", "wilson_inf", "wilson_sup",
          "p_hist", "nota"]


def generar_plan(configs: list[Path], umbrales: list[float], n: float,
                 capacidades: list[float] | None = None) -> list[comun.Punto]:
    plan = []
    for ruta in configs:
        base = comun.punto_desde_config(ruta, n=n)
        cs = sorted({float(c) for c in capacidades}) if capacidades else [base.capacidad]
        for c in cs:
            for u in sorted({float(x) for x in umbrales}):
                plan.append(comun.punto_desde_config(ruta, capacidad=c, umbral=u, n=n))
    return plan


def tabla(filas: list[dict]) -> list[dict]:
    mejor = {}
    for f in filas:
        clave = (f["estacion"], f["regimen"], comun.num(f["capacidad"]), comun.num(f["umbral"]))
        if clave not in mejor or int(f["n"]) >= int(mejor[clave]["n"]):
            mejor[clave] = f
    salida = []
    for (est, reg, c, u), f in sorted(mejor.items(),
                                      key=lambda kv: (kv[0][0], ORDEN_REGIMEN.get(kv[0][1], 9), kv[0][2], kv[0][3])):
        k, n = int(f["k"]), int(f["n"])
        inf, sup = comun.wilson(k, n)
        hist = comun.parse_hist(f.get("hist512", ""))
        salida.append({"estacion": est, "regimen": reg, "capacidad": c, "umbral": u, "n": n, "k": k,
                       "p_hat": k / n, "wilson_inf": inf, "wilson_sup": sup,
                       "p_hist": comun.excedencia_hist(hist, u) if hist else "", "nota": comun.NOTA_V6})
    return salida


def _plt():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                         "axes.grid": True, "grid.color": "#e4e3df", "grid.linewidth": 0.6,
                         "axes.edgecolor": "#8a8984", "xtick.color": "#52514e", "ytick.color": "#52514e",
                         "figure.facecolor": "#fcfcfb", "axes.facecolor": "#fcfcfb",
                         "legend.frameon": False, "svg.fonttype": "none"})
    return plt


def _guardar(plt, fig, destino: Path, nombre: str) -> list[Path]:
    destino.mkdir(parents=True, exist_ok=True)
    fig.text(0.01, -0.02, "Nota: V6 falla en las colas (sd −32 %, p99 −42 %); el riesgo puede estar "
             "subestimado.", fontsize=7, color="#52514e", ha="left", va="top")
    rutas = []
    for ext in ("png", "svg"):
        rutas.append(destino / f"{nombre}.{ext}")
        fig.savefig(rutas[-1], dpi=150, bbox_inches="tight")
    plt.close(fig)
    return rutas


def figuras(t: list[dict], destino: Path) -> list[Path]:
    """Por estación: p̂ e IC frente a U, una línea por régimen (y por C si hay varias)."""
    plt = _plt()
    destino = Path(destino)
    rutas = []
    estaciones = sorted({r["estacion"] for r in t})
    for est in estaciones:
        fig, ax = plt.subplots(figsize=(6.4, 4.2))
        series = defaultdict(list)
        for r in t:
            if r["estacion"] == est and r["p_hat"] > 0:
                series[(r["regimen"], r["capacidad"])].append(r)
        cs = sorted({c for _, c in series})
        for (reg, c), filas in sorted(series.items(), key=lambda kv: (ORDEN_REGIMEN.get(kv[0][0], 9), kv[0][1])):
            color = SERIES[(0 if reg == "normal" else 1) if len(cs) == 1 else cs.index(c) % len(SERIES)]
            us, ps = [r["umbral"] for r in filas], [r["p_hat"] for r in filas]
            err = [[p - r["wilson_inf"] for p, r in zip(ps, filas)], [r["wilson_sup"] - p for p, r in zip(ps, filas)]]
            etiqueta = NOMBRE_REGIMEN.get(reg, reg) + (f", C = {c:g}" if len(cs) > 1 else "")
            ax.errorbar(us, ps, yerr=err, color=color, linestyle=ESTILO_REGIMEN.get(reg, "-"),
                        linewidth=1.6, marker="o", markersize=4, capsize=2, label=etiqueta)
        ax.set_yscale("log")
        ax.set_xticks(sorted({r["umbral"] for r in t}))
        ax.set_xlabel("Umbral de inundación U (mm)")
        ax.set_ylabel("P(Amax > U)")
        titulo_c = f" (C = {cs[0]:g} mm/día)" if len(cs) == 1 else ""
        ax.set_title(f"Sensibilidad a U: {est}{titulo_c}", loc="left", fontsize=11)
        ax.legend(fontsize=8)
        rutas += _guardar(plt, fig, destino, f"sensibilidad_{est}")

    # Resumen: todas las estaciones, a la C más común, normal (continua) y El Niño (discontinua).
    cuenta = defaultdict(int)
    for r in t:
        cuenta[r["capacidad"]] += 1
    c0 = max(cuenta, key=lambda c: (cuenta[c], c == 6.0))
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    for i, est in enumerate(estaciones):
        for reg in ("normal", "el_nino"):
            filas = [r for r in t if r["estacion"] == est and r["regimen"] == reg
                     and r["capacidad"] == c0 and r["p_hat"] > 0]
            if filas:
                ax.plot([r["umbral"] for r in filas], [r["p_hat"] for r in filas],
                        color=SERIES[i % len(SERIES)], linestyle=ESTILO_REGIMEN[reg], linewidth=1.6,
                        marker="o", markersize=4, label=f"{est} · {NOMBRE_REGIMEN[reg]}")
    ax.set_yscale("log")
    ax.set_xticks(sorted({r["umbral"] for r in t}))
    ax.set_xlabel("Umbral de inundación U (mm)")
    ax.set_ylabel("P(Amax > U)")
    ax.set_title(f"Sensibilidad a U y régimen (C = {c0:g} mm/día)", loc="left", fontsize=11)
    ax.legend(fontsize=7, ncol=2)
    rutas += _guardar(plt, fig, destino, "sensibilidad_resumen")
    return rutas


def analizar(salida: Path, tablas: Path, destino_figuras: Path) -> dict:
    t = tabla(comun.leer_resultados(salida))
    comun.escribir_tabla(Path(tablas) / "sensibilidad.csv", t, CAMPOS)
    comun.escribir_markdown(Path(tablas) / "sensibilidad.md",
                            "Sensibilidad de P(Amax > U) al umbral U y al régimen (X7)", t, CAMPOS[:-1],
                            [comun.NOTA_V6, "p_hist: la misma probabilidad leída de hist512 (control)."])
    return {"tabla": t, "figuras": figuras(t, destino_figuras) if t else []}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    comun.agregar_args_ejecucion(ap, "results/cientifico/x7.csv",
                                 "results/cientifico/x7_manifiesto.json", 1e7)
    ap.add_argument("--umbrales", default=",".join(map(str, UMBRALES_X7)))
    ap.add_argument("--capacidades", default="", help="grilla de C opcional (por defecto, la del YAML)")
    ap.add_argument("--tablas", type=Path, default=Path("results/cientifico/tablas"))
    ap.add_argument("--figuras", type=Path, default=Path("results/figures"))
    ap.add_argument("--solo-analisis", action="store_true", help="no corre; solo tablas y figuras")
    args = ap.parse_args(argv)

    errores = 0
    if not args.solo_analisis:
        configs = args.configs or comun.configs_por_defecto()
        if not comun.verificar_binario(args):
            return 2
        plan = generar_plan(configs, comun.lista_numeros(args.umbrales), args.n,
                            comun.lista_numeros(args.capacidades) or None)
        resumen = comun.ejecutar_plan(
            plan, salida=args.salida, logs=args.logs, manifiesto=args.manifiesto, experimento="x7",
            backend=args.backend, build_dir=args.build_dir, hilos=args.hilos, procesos=args.procesos,
            runner=comun.runner_de(args), dry_run=args.dry_run,
            extra={"umbrales": args.umbrales, "capacidades": args.capacidades, "n": int(args.n)})
        errores = resumen["errores"]
        if args.dry_run:
            return 0
    if not comun.leer_resultados(args.salida):
        print(f"error: {args.salida} no existe o está vacío")
        return 2
    r = analizar(args.salida, args.tablas, args.figuras)
    print(f"[x7] {len(r['tabla'])} filas en {args.tablas}/sensibilidad.csv; {len(r['figuras'])} figuras")
    return 1 if errores else 0


if __name__ == "__main__":
    sys.exit(main())
