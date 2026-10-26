#!/usr/bin/env python3
# T33 | Responsable: Rhamses | Métricas de tiempo, speedup, eficiencia, throughput y Karp–Flatt.
"""Análisis de rendimiento de todos los backends a partir de los CSV de results/bench.

Entradas (cada una opcional; si falta se omite con un AVISO):
  secuencial_t1.csv (T14), openmp.csv (T16), mpi_resumen.csv (T21), hibrido_resumen.csv (T27),
  x1.csv, x2.csv, x3.csv (T26, T30, T31; ejecutar_barridos.py).

Por backend × recursos: media, desviación, CV, speedup S = T1/Tp, eficiencia E = S/p, eficiencia
sobre rangos de cómputo (E2: el rango 0 es maestro), throughput (escenarios/s), µs/escenario,
Karp–Flatt e = (1/S − 1/p)/(1 − 1/p) para p > 1, eficiencia de escalado débil T1(N)/Tp(pN) en X2,
marca de sobresuscripción y nota de núcleos P/E. X3: ajuste lineal t = a + b·N.

Salidas en --salida (por defecto results/bench/analisis):
  rendimiento.csv     una fila por punto con todas las métricas.
  rendimiento_x3.csv  ajuste lineal de X3 (si hay X3).
  rendimiento.md      tablas Markdown listas para el informe.
  rendimiento.tex     las mismas tablas como tabular LaTeX (booktabs).

Ejemplo:
    python3 scripts/bench/analizar-rendimiento.py --bench results/bench --salida results/bench/analisis
"""
import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _comun_analisis as ca  # noqa: E402

CAMPOS = ["fuente", "experimento", "backend", "variante", "procesos", "hilos", "recursos", "recursos_computo",
          "n", "repeticiones", "media", "desviacion", "cv", "t1", "fuente_t1", "speedup", "eficiencia",
          "eficiencia_computo", "throughput", "us_por_escenario", "karp_flatt", "eficiencia_debil",
          "sobresuscrito", "nota_nucleos", "cpu", "nucleos_fisicos", "commit"]
CAMPOS_X3 = ["backend", "variante", "recursos", "puntos", "pendiente", "intercepto", "r2", "us_por_escenario"]

# (clave, encabezado Markdown, encabezado LaTeX, formato)
COLUMNAS = [
    ("backend", "backend", "backend", "s"), ("variante", "variante", "variante", "s"),
    ("recursos", "p", "$p$", "d"), ("media", "T (s)", "$T$ (s)", ".3f"), ("desviacion", "sd (s)", "sd (s)", ".3f"),
    ("cv", "CV %", "CV \\%", "%"), ("speedup", "S", "$S$", ".2f"), ("eficiencia", "E", "$E$", ".2f"),
    ("eficiencia_computo", "E cómputo", "$E_c$", ".2f"), ("throughput", "esc/s", "esc/s", ".3g"),
    ("karp_flatt", "Karp–Flatt", "$e$", ".3f"), ("marcas", "marcas", "marcas", "s"),
]
COLUMNAS_X2 = [c for c in COLUMNAS if c[0] in ("backend", "variante", "recursos", "media", "desviacion", "marcas")]
COLUMNAS_X2.insert(3, ("n", "N", "$N$", "d"))
COLUMNAS_X2.insert(-1, ("eficiencia_debil", "E débil", "$E_w$", ".2f"))
COLUMNAS_X3 = [("backend", "backend", "backend", "s"), ("variante", "variante", "variante", "s"),
               ("recursos", "p", "$p$", "d"), ("puntos", "puntos", "puntos", "d"),
               ("us_por_escenario", "µs/escenario", "$\\mu$s/escenario", ".4f"),
               ("intercepto", "a (s)", "$a$ (s)", ".3f"), ("r2", "R²", "$R^2$", ".4f")]
TITULOS = {"openmp": "OpenMP (T16)", "mpi": "MPI E1/E2 (T21)", "hibrido": "Híbrido MPI + OpenMP (T27)",
           "x1": "X1 escalabilidad fuerte", "x2": "X2 escalabilidad débil", "x3": "X3 tiempo frente a N"}


def analizar(bench):
    registros, t1 = ca.cargar_registros(bench)
    return ca.calcular(registros, t1)


def _marcas(r):
    m = []
    if r.get("sobresuscrito"):
        m.append("sobresuscrito")
    if r.get("nota_nucleos"):
        m.append(r["nota_nucleos"])
    return "; ".join(m)


def _fmt(valor, formato):
    if valor is None or valor == "":
        return "–"
    if formato == "s":
        return str(valor)
    if formato == "d":
        return str(int(valor))
    if formato == "%":
        return f"{100 * valor:.1f}"
    return format(valor, formato)


def _tex(texto):
    for a, b in (("\\", "\\textbackslash{}"), ("&", "\\&"), ("%", "\\%"), ("_", "\\_"), ("#", "\\#"),
                 ("–", "--"), (">", "$>$")):
        texto = texto.replace(a, b)
    return texto


def tabla_md(filas, columnas):
    lineas = ["| " + " | ".join(c[1] for c in columnas) + " |",
              "|" + "|".join("---" if c[3] == "s" else "---:" for c in columnas) + "|"]
    for f in filas:
        lineas.append("| " + " | ".join(_fmt(f.get(c[0]), c[3]) for c in columnas) + " |")
    return "\n".join(lineas)


def tabla_tex(filas, columnas, titulo):
    alin = "".join("l" if c[3] == "s" else "r" for c in columnas)
    lineas = [f"% {titulo}", f"\\begin{{tabular}}{{{alin}}}", "\\toprule",
              " & ".join(c[2] for c in columnas) + " \\\\", "\\midrule"]
    for f in filas:
        lineas.append(" & ".join(_tex(_fmt(f.get(c[0]), c[3])) for c in columnas) + " \\\\")
    lineas += ["\\bottomrule", "\\end{tabular}"]
    return "\n".join(lineas)


def secciones(registros):
    """[(título, filas, columnas)] por fuente, en orden fijo."""
    for r in registros:
        r["marcas"] = _marcas(r)
    out = []
    for fuente in ca.FUENTES:
        filas = sorted((r for r in registros if r["fuente"] == fuente),
                       key=lambda r: (r["backend"] != "serial", r["backend"], str(r["variante"]),
                                      r["recursos"], r["n"]))
        if not filas:
            continue
        out.append((TITULOS[fuente], filas, COLUMNAS_X2 if fuente == "x2" else COLUMNAS))
    return out


def escribir(registros, ajustes, salida):
    salida = Path(salida)
    salida.mkdir(parents=True, exist_ok=True)
    rutas = [salida / "rendimiento.csv", salida / "rendimiento.md", salida / "rendimiento.tex"]
    with open(rutas[0], "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS, extrasaction="ignore")
        w.writeheader()
        w.writerows({k: ("" if r.get(k) is None else r.get(k)) for k in CAMPOS} for r in registros)
    if ajustes:
        rutas.append(salida / "rendimiento_x3.csv")
        with open(rutas[-1], "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=CAMPOS_X3, extrasaction="ignore")
            w.writeheader()
            w.writerows(ajustes)
    secs = secciones(registros)
    if ajustes:
        secs.append(("X3: ajuste lineal t = a + b·N", ajustes, COLUMNAS_X3))
    pie = ca.pie(registros)
    md = ["# Análisis de rendimiento (T33)", "",
          f"Procedencia: {pie}.", "",
          "S = T1/Tp; E = S/p; E cómputo = S/(rangos que simulan × hilos) (E2: el rango 0 es maestro); "
          "Karp–Flatt e = (1/S − 1/p)/(1 − 1/p); E débil = T1(N)/Tp(pN); CV = sd/media.", ""]
    tex = [f"% Análisis de rendimiento (T33). Procedencia: {pie}", "% Requiere \\usepackage{booktabs}", ""]
    if not secs:
        md.append("_Sin datos de rendimiento: no se encontró ningún CSV de entrada._")
    for titulo, filas, cols in secs:
        md += [f"## {titulo}", "", tabla_md(filas, cols), ""]
        tex += [tabla_tex(filas, cols, titulo), ""]
    rutas[1].write_text("\n".join(md) + "\n", encoding="utf-8")
    rutas[2].write_text("\n".join(tex) + "\n", encoding="utf-8")
    for r in rutas:
        print(f"escrito {r}")
    return rutas


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bench", type=Path, default=ca.RAIZ / "results" / "bench")
    ap.add_argument("--salida", type=Path, default=ca.RAIZ / "results" / "bench" / "analisis")
    a = ap.parse_args(argv)
    registros = analizar(a.bench)
    return escribir(registros, ca.ajustes_x3(registros), a.salida)


if __name__ == "__main__":
    main()
