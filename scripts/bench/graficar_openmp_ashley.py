#!/usr/bin/env python3
# T18 | Responsable: Ashley | Generador aceptado de la tabla y los gráficos OpenMP (entrada de medir_openmp.py; ver docs/protocolo-graficos-openmp.md).
"""Tiempo, speedup y eficiencia de OpenMP (2/4/8/16 hilos) a partir de results/bench/openmp.csv (T16).

  speedup = T1 / Tp         (T1 = media secuencial; Tp = media con p hilos)
  eficiencia = speedup / p

Reglas (plan S08): se exigen 5 muestras por punto, misma N y semilla, un solo hardware y equivalencia
con el secuencial (V1). No inventa datos: sin CSV o con CSV incompleto, termina con error. Los puntos
sobresuscritos (hilos > núcleos físicos) se dibujan con marcador hueco y se analizan aparte.

Salidas: results/bench/openmp_agregado.csv y results/figures/openmp_{tiempo,speedup,eficiencia}.png
(--svg agrega .svg). Con --plantilla dibuja ejes vacíos rotulados «PENDIENTE» (sin curvas ni cifras).

T1: por defecto se usa la fila backend=serial del propio CSV (T16, mismo build y máquina). Si T14 entrega
results/bench/secuencial_t1.csv, pásela con --t1-csv (columnas t1..t5, o una columna tiempo_s por repetición).
"""
import argparse
import csv
import math
import statistics
import sys
import textwrap
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
PUNTOS = (2, 4, 8, 16)


def leer_csv(ruta):
    if not Path(ruta).exists():
        sys.exit(f"No existe {ruta}. Ejecute primero scripts/bench/medir_openmp.py (T16) en la máquina de referencia. "
                 "No se genera ningún gráfico sin datos reales.")
    with open(ruta, newline="") as f:
        return list(csv.DictReader(f))


def tiempos(fila):
    ts = [fila.get(f"t{i}", "") for i in range(1, 6)]
    if any(t == "" for t in ts):
        sys.exit(f"faltan muestras en backend={fila['backend']} hilos={fila['hilos']} schedule={fila['schedule']}: se exigen 5 tiempos")
    return [float(t) for t in ts]


def t1_desde_csv(ruta):
    filas = leer_csv(ruta)
    if all(f"t{i}" in filas[0] for i in range(1, 6)):
        ts = [float(filas[0][f"t{i}"]) for i in range(1, 6)]
    elif "tiempo_s" in filas[0] and len(filas) >= 5:
        ts = [float(f["tiempo_s"]) for f in filas[:5]]
    else:
        sys.exit(f"{ruta}: formato no reconocido (se esperan columnas t1..t5 o 5 filas con tiempo_s)")
    return statistics.mean(ts), statistics.stdev(ts)


def agregar(filas, t1_ext):
    serial = [f for f in filas if f["backend"] == "serial"]
    omp = [f for f in filas if f["backend"] == "openmp"]
    if not omp:
        sys.exit("el CSV no tiene filas de OpenMP")
    for clave in ("n", "semilla", "cpu", "nucleos_fisicos"):
        if len({f[clave] for f in filas}) != 1:
            sys.exit(f"el CSV mezcla distintos valores de '{clave}': no se pueden comparar (misma carga, semilla y hardware)")
    if any(f["equivalente_serial"] != "1" for f in filas):
        sys.exit("hay filas con V1 fallida (equivalente_serial != 1): corrija el backend antes de graficar rendimiento")
    if t1_ext:
        t1, s1 = t1_ext
        origen_t1 = "T14 (--t1-csv)"
    elif serial:
        ts = tiempos(serial[0])
        t1, s1, origen_t1 = statistics.mean(ts), statistics.stdev(ts), "fila serial de T16"
    else:
        sys.exit("no hay T1: falta la fila serial en el CSV y no se pasó --t1-csv")
    fisicos = int(filas[0]["nucleos_fisicos"])
    salida = []
    for f in omp:
        p = int(f["hilos"])
        ts = tiempos(f)
        media, sd = statistics.mean(ts), statistics.stdev(ts)
        s = t1 / media
        # desviación del speedup por propagación de errores relativos (aproximada)
        s_sd = s * math.sqrt((s1 / t1) ** 2 + (sd / media) ** 2)
        salida.append(dict(schedule=f["schedule"], hilos=p, n=f["n"], semilla=f["semilla"], t1_media=t1, t1_desv=s1,
                           tp_media=media, tp_desv=sd, speedup=s, speedup_desv_aprox=s_sd, eficiencia=s / p,
                           sobresuscrito=int(p > fisicos), muestras=5, fuente_t1=origen_t1,
                           cpu=f["cpu"], nucleos_fisicos=fisicos, nucleos_logicos=f["nucleos_logicos"],
                           afinidad=f["afinidad"], commit=f["commit"], fuente="results/bench/openmp.csv (T16)"))
    salida.sort(key=lambda r: (r["schedule"], r["hilos"]))
    return salida, filas[0]


def dibujar(agr, cab, destino, formatos, plantilla=False):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    destino.mkdir(parents=True, exist_ok=True)
    titulo_hw = "(sin datos)" if plantilla else (
        f"N={int(cab['n']):,} · semilla {cab['semilla']} · {cab['cpu']} · "
        f"{cab['nucleos_fisicos']} núcleos físicos / {cab['nucleos_logicos']} lógicos · {cab['afinidad']}")
    por_sched = defaultdict(list)
    for r in agr:
        por_sched[r["schedule"]].append(r)

    def lienzo(nombre, ylabel, titulo, ideal=None, log_y=False):
        fig, ax = plt.subplots(figsize=(7.2, 4.6), dpi=160)
        ax.set_xscale("log", base=2)
        ax.set_xticks(PUNTOS)
        ax.set_xticklabels([str(p) for p in PUNTOS])
        ax.set_xlabel("Hilos OpenMP (p)")
        ax.set_ylabel(ylabel)
        if log_y:
            ax.set_yscale("log")
        ax.grid(alpha=0.3, which="both")
        if plantilla:
            ax.text(0.5, 0.5, "PENDIENTE\nsin mediciones reales", transform=ax.transAxes, ha="center", va="center",
                    fontsize=22, color="0.55", rotation=15)
            ax.set_ylim(0, 1)
        elif ideal:
            ax.plot(PUNTOS, [ideal(p) for p in PUNTOS], "k--", lw=1, label="ideal")
        ax.set_title(f"{titulo}\n" + textwrap.fill(titulo_hw, 100), fontsize=7.5)
        return fig, ax

    def cierre(fig, ax, nombre, fuente):
        if not plantilla:
            ax.legend(fontsize=8)
            hay_sobre = any(r["sobresuscrito"] for r in agr)
            pie = f"Fuente: {fuente}. Media ± desviación estándar de 5 repeticiones tras calentamiento."
            if hay_sobre:
                pie += "  Marcador hueco = hilos > núcleos físicos (sobresuscrito)."
        else:
            pie = "Plantilla sin datos: se completa con results/bench/openmp.csv (T16)."
        fig.text(0.01, 0.005, textwrap.fill(pie, 125), fontsize=6.5, color="0.35")
        fig.tight_layout(rect=(0, 0.06, 1, 1))
        for ext in formatos:
            fig.savefig(destino / f"{nombre}.{ext}")
        plt.close(fig)

    series = [
        ("openmp_tiempo", "Tiempo medio Tp (s)", "Tiempo de ejecución, OpenMP", "tp_media", "tp_desv", None, False),
        ("openmp_speedup", "Speedup S = T1 / Tp", "Speedup, OpenMP", "speedup", "speedup_desv_aprox", lambda p: p, False),
        ("openmp_eficiencia", "Eficiencia E = S / p", "Eficiencia, OpenMP", "eficiencia", None, lambda p: 1.0, False),
    ]
    for nombre, ylabel, titulo, campo, err, ideal, log_y in series:
        fig, ax = lienzo(nombre, ylabel, titulo, ideal, log_y)
        if not plantilla:
            for sched, rs in por_sched.items():
                x = [r["hilos"] for r in rs]
                y = [r[campo] for r in rs]
                yerr = [r[err] for r in rs] if err else None
                linea = ax.errorbar(x, y, yerr=yerr, marker="o", capsize=3, lw=1.2, label=f"schedule={sched}")
                for r in rs:  # marcador hueco para puntos sobresuscritos
                    if r["sobresuscrito"]:
                        ax.plot(r["hilos"], r[campo], "o", mfc="white", mec=linea[0].get_color(), ms=8, zorder=5)
            if nombre == "openmp_tiempo":
                ax.axhline(agr[0]["t1_media"], color="0.4", ls=":", lw=1, label="T1 (secuencial)")
        cierre(fig, ax, nombre, "results/bench/openmp.csv (T16)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--entrada", default=str(RAIZ / "results" / "bench" / "openmp.csv"))
    ap.add_argument("--t1-csv", default=None)
    ap.add_argument("--agregado", default=str(RAIZ / "results" / "bench" / "openmp_agregado.csv"))
    ap.add_argument("--figuras", default=str(RAIZ / "results" / "figures"))
    ap.add_argument("--svg", action="store_true")
    ap.add_argument("--plantilla", action="store_true", help="ejes vacíos rotulados PENDIENTE (sin curvas ni cifras)")
    a = ap.parse_args()
    formatos = ["png"] + (["svg"] if a.svg else [])
    if a.plantilla:
        dibujar([], None, Path(a.figuras), formatos, plantilla=True)
        print(f"plantilla escrita en {a.figuras}")
        return
    filas = leer_csv(a.entrada)
    agr, cab = agregar(filas, t1_desde_csv(a.t1_csv) if a.t1_csv else None)
    Path(a.agregado).parent.mkdir(parents=True, exist_ok=True)
    with open(a.agregado, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(agr[0].keys()))
        w.writeheader()
        w.writerows(agr)
    dibujar(agr, cab, Path(a.figuras), formatos)
    print(f"escrito {a.agregado} y figuras en {a.figuras}")
    for r in agr:
        marca = "  [sobresuscrito]" if r["sobresuscrito"] else ""
        print(f"  {r['schedule']:10s} p={r['hilos']:2d}  Tp={r['tp_media']:.4f}s  S={r['speedup']:.2f}  E={r['eficiencia']:.2f}{marca}")


if __name__ == "__main__":
    main()
