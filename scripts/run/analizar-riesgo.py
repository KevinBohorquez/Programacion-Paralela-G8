#!/usr/bin/env python3
"""T35 | Responsable: Angela | Riesgo, IC de Wilson, banda bootstrap y curva riesgo–capacidad.

Dos subcomandos:

bootstrap  Corre el simulador en K juegos de parámetros remuestreados (data/processed/
           bootstrap_parametros.csv, salida de calibrar.py) por estación × régimen y por capacidad C,
           con N moderado. Escribe un YAML temporal por réplica (copia del YAML de la estación con
           p01, p11, alfa y theta de la réplica; misma semilla y config_id) y agrega las filas a
           results/cientifico/bootstrap.csv. Reanudable y con --dry-run, como corrida-oficial.py.

analizar   Desde el CSV de X6 (y del bootstrap, si existe) escribe:
           - results/cientifico/tablas/riesgo.csv y .md: p̂ = k/n = P(Amax > U) e IC de Wilson al 95 %
             por estación × régimen × C, más la banda epistémica (percentiles 2,5/50/97,5 de p̂ entre
             réplicas bootstrap) y p_hist (la misma probabilidad leída de hist512, control);
           - results/cientifico/tablas/comparacion_enso.csv y .md: El Niño frente a normal por C;
           - results/figures/riesgo_<estacion>.png/svg: curva P(Amax > U) frente a C con IC y banda;
           - results/figures/riesgo_comparacion_enso.png/svg: riesgo relativo El Niño / normal;
           - results/figures/riesgo_hist_<estacion>.png/svg: distribución de Amax desde hist512.

El IC de Wilson mide solo el error Monte Carlo (N escenarios); la banda bootstrap mide la
incertidumbre de los parámetros calibrados (incluye además el error Monte Carlo de N moderado).

Uso (en la imagen pp-g8):
    python3 scripts/run/analizar-riesgo.py bootstrap --k 100 --n 1e6
    python3 scripts/run/analizar-riesgo.py analizar
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import math
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _comun_cientifico as comun  # noqa: E402

ORDEN_REGIMEN = {"normal": 0, "el_nino": 1}
COLOR_REGIMEN = {"normal": "#2a78d6", "el_nino": "#eb6834"}
NOMBRE_REGIMEN = {"normal": "Normal", "el_nino": "El Niño"}
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
CAMPOS_RIESGO = ["estacion", "regimen", "capacidad", "umbral", "n", "k", "p_hat", "wilson_inf",
                 "wilson_sup", "p_hist", "banda_inf", "banda_med", "banda_sup", "replicas", "n_boot",
                 "nota"]
CAMPOS_ENSO = ["estacion", "capacidad", "umbral", "p_normal", "p_el_nino", "riesgo_relativo",
               "diferencia", "ic_solapan", "banda_solapan"]


# --- Bootstrap -----------------------------------------------------------------------------------

def generar_plan_bootstrap(configs: list[Path], filas_boot: list[dict], k: int, capacidades: list[float],
                           n: float, destino: Path, umbral: float | None = None) -> list[comun.Punto]:
    """K réplicas (las de menor número) por configuración; un YAML por réplica y un punto por C."""
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    por_grupo = defaultdict(list)
    for f in filas_boot:
        por_grupo[(f["estacion"], f["regimen"])].append(f)
    plan = []
    for ruta in configs:
        base = comun.leer_yaml_plano(ruta)
        est, reg = base.get("estacion", ""), base.get("regimen", "")
        replicas = sorted(por_grupo.get((est, reg), []), key=lambda f: int(f["replica"]))[:k]
        if len(replicas) < k:
            print(f"aviso: {est}/{reg} tiene {len(replicas)} réplicas bootstrap (< K = {k})")
        cs = sorted({float(c) for c in capacidades} | {float(base.get("capacidad", 0))})
        for f in replicas:
            rep = f"{int(f['replica']):03d}"
            datos = dict(base)
            datos.update({p: f[p] for p in comun.PARAMETROS})
            yaml = comun.escribir_yaml_plano(
                destino / f"{est}_{reg}_b{rep}.yaml", datos,
                f"Réplica bootstrap {f['replica']} de {est}/{reg} (generado por analizar-riesgo.py "
                f"desde {Path(ruta).as_posix()} y bootstrap_parametros.csv).")
            plan += [comun.punto_desde_config(yaml, capacidad=c, umbral=umbral, n=n, replica=rep)
                     for c in cs]
    return plan


def banda_bootstrap(filas: list[dict], niveles=(2.5, 50.0, 97.5)) -> dict:
    """{(estacion, regimen, C, U): (p_inf, p_med, p_sup, réplicas)} con percentiles de p̂ = k/n."""
    grupos = defaultdict(dict)
    for i, f in enumerate(filas):
        clave = (f["estacion"], f["regimen"], comun.num(f["capacidad"]), comun.num(f["umbral"]))
        params = tuple(f.get(p) for p in comun.PARAMETROS)
        replica = tuple(comun.num(x) for x in params) if all(params) else i
        previo = grupos[clave].get(replica)
        if previo is None or int(f["n"]) >= int(previo["n"]):
            grupos[clave][replica] = f
    banda = {}
    for clave, reps in grupos.items():
        ps = [int(f["k"]) / int(f["n"]) for f in reps.values()]
        banda[clave] = (*(comun.percentil(ps, q) for q in niveles), len(ps))
    return banda


# --- Tablas --------------------------------------------------------------------------------------

def _mejores(filas: list[dict]) -> dict:
    """Una fila por (estación, régimen, C, U): la de mayor n (la última si empatan)."""
    mejor = {}
    for f in filas:
        clave = (f["estacion"], f["regimen"], comun.num(f["capacidad"]), comun.num(f["umbral"]))
        if clave not in mejor or int(f["n"]) >= int(mejor[clave]["n"]):
            mejor[clave] = f
    return mejor


def _orden(clave):
    est, reg, c, u = clave
    return est, ORDEN_REGIMEN.get(reg, 9), reg, u, c


def tabla_riesgo(filas_x6: list[dict], filas_boot: list[dict]) -> list[dict]:
    banda = banda_bootstrap(filas_boot) if filas_boot else {}
    n_boot = {}
    for f in filas_boot:
        n_boot[(f["estacion"], f["regimen"], comun.num(f["capacidad"]), comun.num(f["umbral"]))] = int(f["n"])
    tabla = []
    for clave, f in sorted(_mejores(filas_x6).items(), key=lambda kv: _orden(kv[0])):
        k, n = int(f["k"]), int(f["n"])
        inf, sup = comun.wilson(k, n)
        b = banda.get(clave)
        tabla.append({
            "estacion": clave[0], "regimen": clave[1], "capacidad": clave[2], "umbral": clave[3],
            "n": n, "k": k, "p_hat": k / n if n else float("nan"), "wilson_inf": inf, "wilson_sup": sup,
            "p_hist": comun.excedencia_hist(comun.parse_hist(f.get("hist512", "")), clave[3])
            if f.get("hist512") else "",
            "banda_inf": b[0] if b else "", "banda_med": b[1] if b else "",
            "banda_sup": b[2] if b else "", "replicas": b[3] if b else "",
            "n_boot": n_boot.get(clave, ""), "nota": comun.NOTA_V6})
    return tabla


def comparacion_enso(tabla: list[dict]) -> list[dict]:
    idx = {(t["estacion"], t["regimen"], t["capacidad"], t["umbral"]): t for t in tabla}
    filas = []
    for (est, reg, c, u), nor in sorted(idx.items(), key=lambda kv: _orden(kv[0])):
        nin = idx.get((est, "el_nino", c, u))
        if reg != "normal" or nin is None:
            continue
        pn, pe = nor["p_hat"], nin["p_hat"]
        hay_banda = nor["banda_inf"] != "" and nin["banda_inf"] != ""
        filas.append({
            "estacion": est, "capacidad": c, "umbral": u, "p_normal": pn, "p_el_nino": pe,
            "riesgo_relativo": pe / pn if pn > 0 else float("nan"), "diferencia": pe - pn,
            "ic_solapan": int(nor["wilson_sup"] >= nin["wilson_inf"] and nin["wilson_sup"] >= nor["wilson_inf"]),
            "banda_solapan": int(nor["banda_sup"] >= nin["banda_inf"] and nin["banda_sup"] >= nor["banda_inf"])
            if hay_banda else ""})
    return filas


# --- Figuras -------------------------------------------------------------------------------------

def _plt():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
                         "axes.grid": True, "grid.color": "#e4e3df", "grid.linewidth": 0.6,
                         "axes.edgecolor": "#8a8984", "axes.labelcolor": "#0b0b0b",
                         "xtick.color": "#52514e", "ytick.color": "#52514e",
                         "figure.facecolor": "#fcfcfb", "axes.facecolor": "#fcfcfb",
                         "legend.frameon": False, "svg.fonttype": "none"})
    return plt


def guardar(fig, destino: Path, nombre: str, nota: bool = True) -> list[Path]:
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    if nota:
        fig.text(0.01, -0.02, "Nota: V6 falla en las colas (sd −32 %, p99 −42 %); el riesgo puede estar "
                 "subestimado.", fontsize=7, color="#52514e", ha="left", va="top")
    rutas = []
    for ext in ("png", "svg"):
        ruta = destino / f"{nombre}.{ext}"
        fig.savefig(ruta, dpi=150, bbox_inches="tight")
        rutas.append(ruta)
    fig.clf()
    import matplotlib.pyplot as plt
    plt.close(fig)
    return rutas


def _umbral_figuras(tabla: list[dict], umbral: float | None) -> float:
    if umbral is not None:
        return comun.num(umbral)
    cuenta = defaultdict(int)
    for t in tabla:
        cuenta[t["umbral"]] += 1
    return max(cuenta, key=lambda u: (cuenta[u], u == 50.0))


def figura_curva(tabla: list[dict], estacion: str, umbral: float, destino: Path) -> list[Path]:
    plt = _plt()
    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    for reg in sorted({t["regimen"] for t in tabla}, key=lambda r: ORDEN_REGIMEN.get(r, 9)):
        filas = [t for t in tabla if t["estacion"] == estacion and t["regimen"] == reg
                 and t["umbral"] == umbral and t["p_hat"] > 0]
        if not filas:
            continue
        color = COLOR_REGIMEN.get(reg, "#52514e")
        cs = [t["capacidad"] for t in filas]
        bandas = [t for t in filas if t["banda_inf"] != "" and t["banda_sup"] > 0]
        if bandas:
            ax.fill_between([t["capacidad"] for t in bandas], [max(t["banda_inf"], 1e-12) for t in bandas],
                            [t["banda_sup"] for t in bandas], color=color, alpha=0.18, linewidth=0,
                            label=f"{NOMBRE_REGIMEN.get(reg, reg)}: banda bootstrap 95 %")
        ps = [t["p_hat"] for t in filas]
        err = [[p - t["wilson_inf"] for p, t in zip(ps, filas)], [t["wilson_sup"] - p for p, t in zip(ps, filas)]]
        ax.errorbar(cs, ps, yerr=err, color=color, linewidth=1.6, marker="o", markersize=4,
                    capsize=2, label=f"{NOMBRE_REGIMEN.get(reg, reg)}: p̂ e IC Wilson 95 %")
    ax.set_yscale("log")
    ax.set_xlabel("Capacidad de drenaje C (mm/día)")
    ax.set_ylabel(f"P(Amax > {umbral:g} mm)")
    ax.set_title(f"Riesgo–capacidad: {estacion}", loc="left", fontsize=11)
    ax.legend(fontsize=8)
    return guardar(fig, destino, f"riesgo_{estacion}")


def figura_enso(comp: list[dict], umbral: float, destino: Path) -> list[Path]:
    plt = _plt()
    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    for i, est in enumerate(sorted({c["estacion"] for c in comp})):
        filas = [c for c in comp if c["estacion"] == est and c["umbral"] == umbral
                 and math.isfinite(c["riesgo_relativo"]) and c["riesgo_relativo"] > 0]
        if filas:
            ax.plot([c["capacidad"] for c in filas], [c["riesgo_relativo"] for c in filas],
                    color=SERIES[i % len(SERIES)], linewidth=1.6, marker="o", markersize=4, label=est)
    ax.axhline(1.0, color="#8a8984", linewidth=0.8, linestyle="--")
    ax.set_yscale("log")
    ax.set_xlabel("Capacidad de drenaje C (mm/día)")
    ax.set_ylabel("Riesgo relativo El Niño / normal")
    ax.set_title(f"El Niño frente a normal (U = {umbral:g} mm)", loc="left", fontsize=11)
    ax.legend(fontsize=8)
    return guardar(fig, destino, "riesgo_comparacion_enso")


def figura_hist(filas_x6: list[dict], estacion: str, capacidad: float, umbral: float,
                destino: Path) -> list[Path]:
    plt = _plt()
    mejores = _mejores(filas_x6)
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9.6, 3.9))
    for reg in ("normal", "el_nino"):
        f = mejores.get((estacion, reg, capacidad, umbral))
        if f is None or not f.get("hist512"):
            continue
        hist = comun.parse_hist(f["hist512"])
        n = sum(hist)
        color, nombre = COLOR_REGIMEN[reg], NOMBRE_REGIMEN[reg]
        ax1.step(range(len(hist)), [h / n for h in hist], where="post", color=color, linewidth=1.4,
                 label=nombre)
        surv = [comun.excedencia_hist(hist, a) for a in range(1, len(hist))]
        xs = [a for a, s in zip(range(1, len(hist)), surv) if s > 0]
        ax2.plot(xs, [s for s in surv if s > 0], color=color, linewidth=1.6, label=nombre)
    for ax in (ax1, ax2):
        ax.axvline(umbral, color="#52514e", linewidth=0.8, linestyle="--")
        ax.set_xlabel("Amax: máximo acumulado en la temporada (mm)")
        ax.legend(fontsize=8)
    ax1.set_ylabel("Fracción de escenarios (clases de 1 mm)")
    ax1.set_yscale("log")
    ax2.set_ylabel("P(Amax > a)")
    ax2.set_yscale("log")
    fig.suptitle(f"Amax en {estacion} (C = {capacidad:g} mm/día; línea discontinua: U = {umbral:g} mm)",
                 x=0.01, ha="left", fontsize=11)
    ax1.set_title("Distribución", loc="left", fontsize=10)
    ax2.set_title("Excedencia", loc="left", fontsize=10)
    fig.tight_layout()
    return guardar(fig, destino, f"riesgo_hist_{estacion}")


def analizar(filas_x6: list[dict], filas_boot: list[dict], tablas: Path, figuras: Path,
             umbral: float | None = None, capacidad_hist: float = 6.0) -> dict:
    tabla = tabla_riesgo(filas_x6, filas_boot)
    comp = comparacion_enso(tabla)
    tablas = Path(tablas)
    notas = [comun.NOTA_V6,
             "IC de Wilson al 95 % = error Monte Carlo; banda = percentiles 2,5–97,5 de p̂ entre réplicas "
             "bootstrap de los parámetros (incertidumbre epistémica)."]
    comun.escribir_tabla(tablas / "riesgo.csv", tabla, CAMPOS_RIESGO)
    comun.escribir_markdown(tablas / "riesgo.md", "Riesgo de inundación P(Amax > U) por estación, "
                            "régimen y capacidad (X6)", tabla, CAMPOS_RIESGO[:-1], notas)
    comun.escribir_tabla(tablas / "comparacion_enso.csv", comp, CAMPOS_ENSO)
    comun.escribir_markdown(tablas / "comparacion_enso.md", "El Niño frente a normal (X6)", comp,
                            CAMPOS_ENSO, notas[:1])
    u = _umbral_figuras(tabla, umbral)
    rutas = []
    for est in sorted({t["estacion"] for t in tabla}):
        rutas += figura_curva(tabla, est, u, figuras)
        cs = sorted({t["capacidad"] for t in tabla if t["estacion"] == est and t["umbral"] == u})
        if cs:
            c = min(cs, key=lambda x: abs(x - capacidad_hist))
            rutas += figura_hist(filas_x6, est, c, u, figuras)
    if comp:
        rutas += figura_enso(comp, u, figuras)
    return {"tabla": tabla, "comparacion": comp, "figuras": rutas}


# --- CLI -----------------------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="modo", required=True)

    b = sub.add_parser("bootstrap", help="corre el simulador en réplicas bootstrap de los parámetros")
    comun.agregar_args_ejecucion(b, "results/cientifico/bootstrap.csv",
                                 "results/cientifico/bootstrap_manifiesto.json", 1e6)
    b.add_argument("--bootstrap", type=Path, default=Path("data/processed/bootstrap_parametros.csv"))
    b.add_argument("--k", type=int, default=100, help="réplicas por estación × régimen")
    b.add_argument("--capacidades", default=",".join(map(str, comun.CAPACIDADES_X6)))
    b.add_argument("--umbral", type=float, default=None)
    b.add_argument("--dir-configs", type=Path, default=Path("_build/bootstrap_configs"),
                   help="carpeta de los YAML temporales por réplica")

    a = sub.add_parser("analizar", help="tablas y figuras desde X6 (+ bootstrap)")
    a.add_argument("--x6", type=Path, default=Path("results/cientifico/x6.csv"))
    a.add_argument("--bootstrap-csv", type=Path, default=Path("results/cientifico/bootstrap.csv"))
    a.add_argument("--tablas", type=Path, default=Path("results/cientifico/tablas"))
    a.add_argument("--figuras", type=Path, default=Path("results/figures"))
    a.add_argument("--umbral", type=float, default=None, help="U de las figuras (por defecto, el más común)")
    a.add_argument("--capacidad-hist", type=float, default=6.0, help="C del histograma de Amax")
    args = ap.parse_args(argv)

    if args.modo == "bootstrap":
        configs = args.configs or comun.configs_por_defecto()
        if not comun.verificar_binario(args):
            return 2
        plan = generar_plan_bootstrap(configs, comun.leer_resultados(args.bootstrap), args.k,
                                      comun.lista_numeros(args.capacidades), args.n, args.dir_configs,
                                      args.umbral)
        resumen = comun.ejecutar_plan(
            plan, salida=args.salida, logs=args.logs, manifiesto=args.manifiesto,
            experimento="bootstrap", backend=args.backend, build_dir=args.build_dir, hilos=args.hilos,
            procesos=args.procesos, runner=comun.runner_de(args), dry_run=args.dry_run,
            extra={"k": args.k, "n": int(args.n), "capacidades": args.capacidades,
                   "fuente": Path(args.bootstrap).as_posix()})
        return 1 if resumen["errores"] else 0

    filas_x6 = comun.leer_resultados(args.x6)
    if not filas_x6:
        print(f"error: {args.x6} no existe o está vacío")
        return 2
    filas_boot = comun.leer_resultados(args.bootstrap_csv)
    if not filas_boot:
        print(f"aviso: sin {args.bootstrap_csv}; la tabla sale sin banda epistémica")
    r = analizar(filas_x6, filas_boot, args.tablas, args.figuras, args.umbral, args.capacidad_hist)
    print(f"[riesgo] {len(r['tabla'])} filas en {args.tablas}/riesgo.csv; {len(r['figuras'])} figuras en "
          f"{args.figuras}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
