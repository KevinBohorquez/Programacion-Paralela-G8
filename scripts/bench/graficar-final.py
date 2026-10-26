#!/usr/bin/env python3
# T45 | Responsable: Rhamses | Figuras finales de rendimiento y riesgo.
"""Figuras finales del informe con unidades, estilo común y pie de procedencia (commit + hardware).

Rendimiento (desde results/bench, con las métricas de _comun_analisis, las mismas de T33):
  final_speedup                speedup frente a recursos de todos los backends, con la recta ideal.
  final_eficiencia             eficiencia E = S/p (ideal 1).
  final_karp_flatt             fracción serial experimental de Karp–Flatt (p > 1).
  final_x2_debil               eficiencia de escalado débil T1(N)/Tp(pN) de X2.
  final_x3_tiempo              tiempo frente a N de X3 con su ajuste lineal.
  final_hibrido_factorizacion  speedup por factorización procesos × hilos, agrupado por núcleos totales.
  final_e1_e2                  MPI E1 (estático) frente a E2 (dinámico): speedup y eficiencia (total y cómputo).
Ciencia (desde results/cientifico/tablas), solo si analizar-riesgo.py / sensibilidad.py no dejaron ya
sus figuras en --figuras (en ese caso se reutilizan y no se duplican):
  final_riesgo_<estacion>      P(Amax > U) frente a la capacidad C, normal frente a El Niño, banda de Wilson 95 %.
  final_sensibilidad           P(Amax > U) frente a C para U = 30/50/80 mm por estación.

Cada figura se escribe como PNG (200 dpi) y SVG en --figuras/final_*.{png,svg}. Las entradas
ausentes se omiten con un AVISO.

Ejemplo:
    python3 scripts/bench/graficar-final.py --bench results/bench --cientifico results/cientifico
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _comun_analisis as ca  # noqa: E402

COLOR = {"serial": "#555555", "openmp": "#2a78d6", "mpi_estatico": "#eb6834", "mpi_dinamico": "#1baf7a",
         "hibrido": "#6250d6"}
MARCADOR = {"openmp": "o", "mpi_estatico": "s", "mpi_dinamico": "^", "hibrido": "D"}
ESTILO_VARIANTE = {"dynamic:1": "--", "dynamic:64": "-."}  # schedules OpenMP; el resto, línea continua
NOMBRE_REGIMEN = {"normal": "Normal", "el_nino": "El Niño"}
COLOR_REGIMEN = {"normal": "#2a78d6", "el_nino": "#eb6834"}
SERIES_U = ["#2a78d6", "#eda100", "#e34948", "#1baf7a"]
ETIQUETA_P = "Recursos p (hilos, procesos o procesos × hilos)"


def _plt():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"figure.figsize": (7.5, 4.6), "axes.grid": True, "grid.alpha": 0.3,
                         "axes.spines.top": False, "axes.spines.right": False, "font.size": 10,
                         "legend.fontsize": 8, "svg.fonttype": "none"})
    return plt


def guardar(fig, carpeta, nombre, pie):
    fig.text(0.01, 0.005, pie, fontsize=6.5, color="#666666", ha="left", va="bottom")
    fig.tight_layout(rect=(0, 0.03, 1, 1))
    for ext in ("png", "svg"):
        fig.savefig(Path(carpeta) / f"{nombre}.{ext}", dpi=200)
    import matplotlib.pyplot as plt
    plt.close(fig)


# ---------- series de rendimiento ----------
def series_fuertes(registros, metrica):
    """{(fuente, backend, variante): [(p, valor, sobresuscrito)]}; el híbrido se reduce al mejor p×h."""
    series = {}
    for r in registros:
        if r["experimento"] not in ("openmp", "mpi", "hibrido", "x1") or r["backend"] == "serial":
            continue
        v = r.get(metrica)
        if v is None:
            continue
        clave = (r["fuente"], r["backend"], "mejor p×h" if r["backend"] == "hibrido" else r["variante"])
        series.setdefault(clave, {})
        previo = series[clave].get(r["recursos"])
        if previo is None or (r.get("speedup") or 0) > previo[1]:
            series[clave][r["recursos"]] = (v, r.get("speedup") or 0, r["sobresuscrito"])
    return {k: sorted((p, v, s) for p, (v, _, s) in d.items()) for k, d in sorted(series.items())}


def _etiqueta(fuente, backend, variante):
    txt = backend if variante in ("-", "", None) else f"{backend} {variante}"
    return f"{txt} [X1]" if fuente == "x1" else txt


def _trazar_series(ax, series):
    for (fuente, backend, variante), pts in series.items():
        xs, ys = [p for p, _, _ in pts], [v for _, v, _ in pts]
        ax.plot(xs, ys, ESTILO_VARIANTE.get(variante, "-"), marker=MARCADOR.get(backend, "o"), ms=4,
                color=COLOR.get(backend, "#333333"), label=_etiqueta(fuente, backend, variante),
                mfc="none" if fuente == "x1" else None)
        sobre = [(p, v) for p, v, s in pts if s]
        if sobre:
            ax.scatter(*zip(*sobre), s=60, facecolors="none", edgecolors="#e34948", zorder=5)


def _eje_p(ax, xs):
    ax.set_xscale("log", base=2)
    ticks = sorted(set(xs))
    ax.set_xticks(ticks)
    ax.set_xticklabels([str(t) for t in ticks])
    ax.set_xlabel(ETIQUETA_P)


def fig_fuerte(plt, registros, metrica, nombre, ylabel, titulo, ideal, carpeta, pie):
    series = series_fuertes(registros, metrica)
    if not series:
        return False
    fig, ax = plt.subplots()
    xs = [p for pts in series.values() for p, _, _ in pts]
    _trazar_series(ax, series)
    if ideal == "lineal":
        xs = sorted(set(xs) | {1})
        ax.plot(xs, xs, ":", color="black", lw=1, label="ideal (S = p)")
    elif ideal is not None:
        ax.axhline(ideal, ls=":", color="black", lw=1, label=f"ideal ({ideal:g})")
    _eje_p(ax, xs)
    ax.set_ylabel(ylabel)
    ax.set_title(titulo + " (círculo rojo = sobresuscrito)")
    ax.legend(ncol=2)
    guardar(fig, carpeta, nombre, pie)
    return True


def fig_x2(plt, registros, carpeta, pie):
    rs = [r for r in registros if r["experimento"] == "x2" and r.get("eficiencia_debil") is not None
          and r["backend"] != "serial"]
    if not rs:
        return False
    fig, ax = plt.subplots()
    grupos = {}
    for r in rs:
        grupos.setdefault((r["backend"], r["variante"]), []).append(r)
    for (b, v), g in sorted(grupos.items()):
        g.sort(key=lambda r: r["recursos"])
        ax.plot([r["recursos"] for r in g], [r["eficiencia_debil"] for r in g], marker=MARCADOR.get(b, "o"),
                color=COLOR.get(b, "#333333"), label=_etiqueta("x2", b, v))
    ax.axhline(1.0, ls=":", color="black", lw=1, label="ideal (1)")
    _eje_p(ax, [r["recursos"] for r in rs])
    ax.set_ylabel("Eficiencia débil T1(N) / Tp(p·N) (adim.)")
    ax.set_title("X2: escalabilidad débil (carga por recurso constante)")
    ax.legend()
    guardar(fig, carpeta, "final_x2_debil", pie)
    return True


def fig_x3(plt, registros, carpeta, pie):
    rs = [r for r in registros if r["experimento"] == "x3"]
    if not rs:
        return False
    fig, ax = plt.subplots()
    ajustes = {(a["backend"], a["variante"], a["recursos"]): a for a in ca.ajustes_x3(registros)}
    grupos = {}
    for r in rs:
        grupos.setdefault((r["backend"], r["variante"], r["recursos"]), []).append(r)
    for clave, g in sorted(grupos.items()):
        g.sort(key=lambda r: r["n"])
        b = clave[0]
        xs = [r["n"] / 1e6 for r in g]
        etiqueta = f"{_etiqueta('x3', b, clave[1])}, p={clave[2]}"
        aj = ajustes.get(clave)
        if aj:
            etiqueta += f" ({aj['us_por_escenario']:.3f} µs/esc., R²={aj['r2']:.3f})"
            ax.plot(xs, [aj["intercepto"] + aj["pendiente"] * r["n"] for r in g], ":",
                    color=COLOR.get(b, "#333333"), lw=1)
        ax.errorbar(xs, [r["media"] for r in g], yerr=[r["desviacion"] for r in g], marker=MARCADOR.get(b, "o"),
                    ls="none", capsize=2, color=COLOR.get(b, "#333333"), label=etiqueta)
    ax.set_xlabel("Escenarios N (millones)")
    ax.set_ylabel("Tiempo de pared (s)")
    ax.set_title("X3: tiempo frente a la carga (punteado = ajuste lineal)")
    ax.legend()
    guardar(fig, carpeta, "final_x3_tiempo", pie)
    return True


def fig_hibrido(plt, registros, carpeta, pie):
    rs = [r for r in registros if r["backend"] == "hibrido" and r["fuente"] == "hibrido" and r.get("speedup")]
    if not rs:
        rs = [r for r in registros if r["backend"] == "hibrido" and r["fuente"] == "x1" and r.get("speedup")]
    if not rs:
        return False
    fig, ax = plt.subplots(figsize=(8, 4.6))
    x, pos, etiquetas = 0.0, [], []
    for b in sorted({r["recursos"] for r in rs}):
        grupo = sorted((r for r in rs if r["recursos"] == b), key=lambda r: r["procesos"])
        inicio = x
        for r in grupo:
            err = r["desviacion"] / r["media"] * r["speedup"] if r["media"] else 0.0
            ax.bar(x, r["speedup"], width=0.8, yerr=err, capsize=2, color=COLOR["hibrido"],
                   edgecolor="white", hatch="//" if r["sobresuscrito"] else None)
            pos.append(x)
            etiquetas.append(r["variante"])
            x += 1
        ax.hlines(b, inicio - 0.4, x - 0.6, colors="black", linestyles=":", lw=1)
        ax.text((inicio + x - 1) / 2, b, f"B={b}", ha="center", va="bottom", fontsize=8)
        x += 0.8
    ax.set_xticks(pos)
    ax.set_xticklabels(etiquetas, rotation=45, ha="right", fontsize=8)
    ax.set_xlabel("procesos × hilos (agrupado por núcleos totales B; punteado = ideal S = B)")
    ax.set_ylabel("Speedup S = T1/Tp (adim.)")
    ax.set_title("Híbrido MPI + OpenMP: speedup por factorización")
    ax.grid(axis="x", visible=False)
    guardar(fig, carpeta, "final_hibrido_factorizacion", pie)
    return True


def fig_e1_e2(plt, registros, carpeta, pie):
    rs = [r for r in registros if r["backend"] in ("mpi_estatico", "mpi_dinamico") and r.get("speedup")]
    if any(r["fuente"] == "mpi" for r in rs):
        rs = [r for r in rs if r["fuente"] == "mpi"]
    if not rs:
        return False
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 4.4))
    for b, nombre in (("mpi_estatico", "E1 estático"), ("mpi_dinamico", "E2 dinámico")):
        g = sorted((r for r in rs if r["backend"] == b), key=lambda r: r["recursos"])
        if not g:
            continue
        ps = [r["recursos"] for r in g]
        a1.plot(ps, [r["speedup"] for r in g], marker=MARCADOR[b], color=COLOR[b], label=nombre)
        a2.plot(ps, [r["eficiencia"] for r in g], marker=MARCADOR[b], color=COLOR[b], label=f"{nombre}: S/P")
        if b == "mpi_dinamico":
            a2.plot(ps, [r["eficiencia_computo"] for r in g], "--", marker=MARCADOR[b], color=COLOR[b],
                    mfc="none", label="E2 dinámico: S/(P−1) rangos de cómputo")
    ps = sorted({r["recursos"] for r in rs})
    a1.plot(ps, ps, ":", color="black", lw=1, label="ideal (S = P)")
    a2.axhline(1.0, ls=":", color="black", lw=1, label="ideal (1)")
    for ax, ylabel in ((a1, "Speedup S = T1/Tp (adim.)"), (a2, "Eficiencia (adim.)")):
        _eje_p(ax, ps)
        ax.set_xlabel("Procesos MPI P")
        ax.set_ylabel(ylabel)
        ax.legend()
    a1.set_title("MPI: E1 frente a E2, speedup")
    a2.set_title("MPI: eficiencia (E2 con maestro sin cómputo)")
    guardar(fig, carpeta, "final_e1_e2", pie)
    return True


# ---------- ciencia ----------
def _pie_cientifico(cientifico, respaldo):
    filas = ca.leer_csv(Path(cientifico) / "x6.csv") if (Path(cientifico) / "x6.csv").exists() else None
    if not filas:
        return f"{respaldo} · datos: results/cientifico/tablas"
    commits = sorted({f.get("commit", "") for f in filas if f.get("commit")})
    hw = sorted({f.get("hardware") or f.get("cpu", "") for f in filas if f.get("hardware") or f.get("cpu")})
    return f"commit {', '.join(commits) or 'desconocido'} · {'; '.join(hw) or 'hardware desconocido'}"


def figs_riesgo(plt, cientifico, carpeta, pie, resultado):
    filas = ca.leer_csv(Path(cientifico) / "tablas" / "riesgo.csv")
    if not filas:
        resultado["omitidas"].append("final_riesgo")
        return
    for est in sorted({f["estacion"] for f in filas}):
        existente = Path(carpeta) / f"riesgo_{est}.png"
        if existente.exists():
            resultado["reutilizadas"].append(existente.name)
            continue
        fig, ax = plt.subplots()
        grupos = {}
        for f in filas:
            if f["estacion"] == est:
                grupos.setdefault((f["regimen"], f.get("umbral", "")), []).append(f)
        for (reg, u), g in sorted(grupos.items()):
            g.sort(key=lambda f: ca.num(f["capacidad"]))
            cs = [ca.num(f["capacidad"]) for f in g]
            color = COLOR_REGIMEN.get(reg, "#333333")
            ax.plot(cs, [ca.num(f["p_hat"]) for f in g], marker="o", ms=3, color=color,
                    label=f"{NOMBRE_REGIMEN.get(reg, reg)} (U = {u} mm)")
            ax.fill_between(cs, [ca.num(f["wilson_inf"], 0.0) for f in g], [ca.num(f["wilson_sup"], 0.0) for f in g],
                            color=color, alpha=0.2, lw=0)
        ax.set_xlabel("Capacidad de drenaje C (mm/día)")
        ax.set_ylabel("P(Amax > U) (probabilidad)")
        ax.set_title(f"Riesgo de inundación: {est} (banda = IC de Wilson 95 %)")
        ax.legend()
        guardar(fig, carpeta, f"final_riesgo_{est}", pie)
        resultado["escritas"].append(f"final_riesgo_{est}")


def fig_sensibilidad(plt, cientifico, carpeta, pie, resultado):
    existentes = sorted(p.name for p in Path(carpeta).glob("sensibilidad_*.png")) if Path(carpeta).exists() else []
    if existentes:
        resultado["reutilizadas"] += existentes
        return
    filas = ca.leer_csv(Path(cientifico) / "tablas" / "sensibilidad.csv")
    if not filas:
        resultado["omitidas"].append("final_sensibilidad")
        return
    estaciones = sorted({f["estacion"] for f in filas})
    fig, ejes = plt.subplots(1, len(estaciones), figsize=(4.2 * len(estaciones) + 1, 4.4), squeeze=False)
    umbrales = sorted({ca.num(f["umbral"]) for f in filas})
    for ax, est in zip(ejes[0], estaciones):
        for i, u in enumerate(umbrales):
            for reg, ls in (("normal", "-"), ("el_nino", "--")):
                g = sorted((f for f in filas if f["estacion"] == est and f["regimen"] == reg
                            and ca.num(f["umbral"]) == u), key=lambda f: ca.num(f["capacidad"]))
                if g:
                    ax.plot([ca.num(f["capacidad"]) for f in g], [ca.num(f["p_hat"]) for f in g], ls, marker="o",
                            ms=3, color=SERIES_U[i % len(SERIES_U)],
                            label=f"U = {u:g} mm, {NOMBRE_REGIMEN.get(reg, reg)}")
        ax.set_title(est)
        ax.set_xlabel("Capacidad de drenaje C (mm/día)")
        ax.set_ylabel("P(Amax > U) (probabilidad)")
    ejes[0][-1].legend()
    fig.suptitle("Sensibilidad de P(Amax > U) al umbral U (X7; continuo = normal, discontinuo = El Niño)")
    guardar(fig, carpeta, "final_sensibilidad", pie)
    resultado["escritas"].append("final_sensibilidad")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bench", type=Path, default=ca.RAIZ / "results" / "bench")
    ap.add_argument("--cientifico", type=Path, default=ca.RAIZ / "results" / "cientifico")
    ap.add_argument("--figuras", type=Path, default=ca.RAIZ / "results" / "figures")
    a = ap.parse_args(argv)
    plt = _plt()
    registros, t1 = ca.cargar_registros(a.bench)
    ca.calcular(registros, t1)
    carpeta = Path(a.figuras)
    carpeta.mkdir(parents=True, exist_ok=True)
    pie = ca.pie(registros)
    resultado = {"escritas": [], "omitidas": [], "reutilizadas": []}
    tareas = [
        ("final_speedup", lambda: fig_fuerte(plt, registros, "speedup", "final_speedup",
                                             "Speedup S = T1/Tp (adim.)", "Escalabilidad fuerte: speedup",
                                             "lineal", carpeta, pie)),
        ("final_eficiencia", lambda: fig_fuerte(plt, registros, "eficiencia", "final_eficiencia",
                                                "Eficiencia E = S/p (adim.)", "Escalabilidad fuerte: eficiencia",
                                                1.0, carpeta, pie)),
        ("final_karp_flatt", lambda: fig_fuerte(plt, registros, "karp_flatt", "final_karp_flatt",
                                                "Fracción serial e de Karp–Flatt (adim.)",
                                                "Karp–Flatt: e = (1/S − 1/p)/(1 − 1/p)", None, carpeta, pie)),
        ("final_x2_debil", lambda: fig_x2(plt, registros, carpeta, pie)),
        ("final_x3_tiempo", lambda: fig_x3(plt, registros, carpeta, pie)),
        ("final_hibrido_factorizacion", lambda: fig_hibrido(plt, registros, carpeta, pie)),
        ("final_e1_e2", lambda: fig_e1_e2(plt, registros, carpeta, pie)),
    ]
    for nombre, tarea in tareas:
        if tarea():
            resultado["escritas"].append(nombre)
        else:
            ca.aviso(f"sin datos para {nombre}; se omite")
            resultado["omitidas"].append(nombre)
    pie_c = _pie_cientifico(a.cientifico, pie)
    figs_riesgo(plt, a.cientifico, carpeta, pie_c, resultado)
    fig_sensibilidad(plt, a.cientifico, carpeta, pie_c, resultado)
    print(f"escritas en {carpeta}: {', '.join(resultado['escritas']) or 'ninguna'}")
    print(f"omitidas: {', '.join(resultado['omitidas']) or 'ninguna'}")
    print(f"reutilizadas: {', '.join(resultado['reutilizadas']) or 'ninguna'}")
    return resultado


if __name__ == "__main__":
    main()
