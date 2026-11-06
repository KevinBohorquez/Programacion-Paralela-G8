#!/usr/bin/env python3
# T27 | Responsable: Lita | Barrido híbrido de 2, 4, 8 y 16 recursos (procesos MPI x hilos OpenMP).
"""Mide pp_hibrido con presupuestos de 2/4/8/16 núcleos CPU totales y TODAS sus factorizaciones.

Para cada presupuesto B se prueban todos los pares procesos x hilos con p*h = B, incluidos los
extremos p=1 (solo hilos) y h=1 (solo procesos). Cada punto: una corrida de calentamiento (no
cuenta) y N repeticiones (5 por defecto), con la misma carga y semilla que el secuencial; V1 (k, n e
histograma idénticos a pp_serial) se comprueba antes de calcular speedup. T1 se toma de
results/bench/secuencial_t1.csv cuando coincide (ver _comun_mpi.referencia_serial).

Afinidad: mpirun se lanza con `--bind-to none` (si Open MPI ancla cada proceso a un núcleo, sus
hilos comparten ese núcleo). Por eso OMP_PROC_BIND=false por defecto: con `--bind-to none` cada
proceso ve todos los núcleos y `close` colocaría el hilo 0 de TODOS los procesos en el mismo núcleo.
Los valores de OMP_PROC_BIND, OMP_PLACES y --bind-to quedan en la columna `afinidad`.

Salidas (con --salida results/bench/hibrido.csv, el valor por defecto):
  hibrido.csv          UNA fila por corrida (calentamiento = repetición 0, luego 1..5).
  hibrido_resumen.csv  UNA fila por punto: presupuesto, factorización, tiempos, media, desviación,
                       speedup vs T1, eficiencia (speedup / núcleos totales), afinidad y metadatos.
  --figura             además results/figures/hibrido_speedup.{png,svg} e hibrido_eficiencia.{png,svg}
                       (también se puede graficar un resumen existente con --solo-figura).

Ejemplo (en la imagen pp-g8, build Release con -DPP_BUILD_MPI=ON):
    python3 scripts/bench/medir_hibrido.py --build-dir build/docker --presupuestos 2,4,8,16 --figura
"""
import argparse
import csv
import datetime
import platform
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _comun_mpi as cm  # noqa: E402

RAIZ = cm.RAIZ


def factorizaciones(presupuesto):
    """Todos los pares (procesos, hilos) con procesos * hilos = presupuesto, por procesos crecientes."""
    return [(p, presupuesto // p) for p in range(1, presupuesto + 1) if presupuesto % p == 0]


def plan(presupuestos):
    return [(b, p, h) for b in presupuestos for p, h in factorizaciones(b)]


def comando(mpiexec, exe, procesos, hilos, comunes, bind_to="none", oversubscribe=False, schedule="static"):
    return cm.comando_mpi(mpiexec, procesos, exe, [*comunes, "--hilos", hilos, "--schedule", schedule],
                          bind_to=bind_to, oversubscribe=oversubscribe)


def fila_resumen(presupuesto, procesos, hilos, cal, reps, t_serial, fuente_t1, equivalente, afinidad,
                 fisicos, logicos, base):
    tiempos = [float(r["tiempo_s"]) for r in reps]
    media, desviacion = cm.resumir(tiempos)
    fila = dict(nucleos_totales=presupuesto, procesos=procesos, hilos=hilos, factorizacion=f"{procesos}x{hilos}",
                hilos_efectivos=int(reps[0]["hilos"]), **base, t_calentamiento=cal["tiempo_s"])
    for i, t in enumerate(tiempos, 1):
        fila[f"t{i}"] = t
    fila.update(media=media, desviacion=desviacion, t_serial=t_serial, fuente_t1=fuente_t1,
                speedup=cm.speedup(t_serial, media), eficiencia=cm.eficiencia(t_serial, media, presupuesto),
                k=reps[0]["k"], equivalente_serial=int(equivalente), afinidad=afinidad,
                nodos=reps[0].get("nodos", ""), distribucion=reps[0].get("distribucion", ""),
                nucleos_fisicos=fisicos, nucleos_logicos=logicos,
                sobresuscrito=cm.sobresuscrito(presupuesto, fisicos),
                excede_logicos=cm.sobresuscrito(presupuesto, logicos))
    return fila


def figuras(resumen_csv, carpeta):
    """Speedup y eficiencia por factorización, agrupados por presupuesto. Devuelve las rutas escritas."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    with open(resumen_csv, newline="", encoding="utf-8") as f:
        filas = [r for r in csv.DictReader(f) if r.get("speedup") not in ("", None)]
    presupuestos = sorted({int(r["nucleos_totales"]) for r in filas})
    carpeta = Path(carpeta)
    carpeta.mkdir(parents=True, exist_ok=True)
    escritos = []
    for metrica, etiqueta, ideal in (("speedup", "Speedup frente a T1", lambda b: b),
                                     ("eficiencia", "Eficiencia (speedup / núcleos totales)", lambda b: 1.0)):
        fig, ax = plt.subplots(figsize=(8, 4.5))
        etiquetas_x, posiciones = [], []
        x = 0.0
        for b in presupuestos:
            grupo = sorted((r for r in filas if int(r["nucleos_totales"]) == b), key=lambda r: int(r["procesos"]))
            inicio = x
            for r in grupo:
                desv = (float(r["desviacion"]) / float(r["media"]) * float(r[metrica])) if float(r["media"]) else 0
                ax.bar(x, float(r[metrica]), width=0.8, yerr=desv, capsize=2, color="#4C72B0",
                       edgecolor="white")
                etiquetas_x.append(r["factorizacion"])
                posiciones.append(x)
                x += 1
            ax.hlines(ideal(b), inicio - 0.4, x - 0.6, colors="#C44E52", linestyles="--", linewidth=1)
            ax.text((inicio + x - 1) / 2, ideal(b), f"B={b}", ha="center",
                    va="bottom", fontsize=8, color="#C44E52")
            x += 0.8
        ax.set_xticks(posiciones)
        ax.set_xticklabels(etiquetas_x, rotation=45, ha="right", fontsize=8)
        ax.set_xlabel("procesos x hilos (agrupado por núcleos totales B; línea discontinua = ideal)")
        ax.set_ylabel(etiqueta)
        ax.set_title(f"Híbrido MPI + OpenMP: {metrica} por factorización")
        ax.grid(axis="y", alpha=0.3)
        fig.tight_layout()
        for ext in ("png", "svg"):
            ruta = carpeta / f"hibrido_{metrica}.{ext}"
            fig.savefig(ruta, dpi=150)
            escritos.append(ruta)
        plt.close(fig)
    return escritos


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--build-dir", default=str(RAIZ / "build" / "docker"))
    ap.add_argument("--config", default=str(RAIZ / "config" / "sintetico.yaml"))
    ap.add_argument("--n", type=int, default=20_000_000)
    ap.add_argument("--semilla", type=int, default=20261015)
    ap.add_argument("--config-id", type=int, default=0)
    ap.add_argument("--presupuestos", default="2,4,8,16", help="núcleos CPU totales (procesos x hilos)")
    ap.add_argument("--schedule", default="static")
    ap.add_argument("--reps", "--repeticiones", dest="reps", type=int, default=5)
    ap.add_argument("--bind-to", default="none", help="política --bind-to de mpirun")
    ap.add_argument("--bind", default="false", help="OMP_PROC_BIND (false: ver la nota de afinidad)")
    ap.add_argument("--places", default="cores", help="OMP_PLACES")
    ap.add_argument("--t1-csv", default=str(cm.T1_POR_DEFECTO))
    ap.add_argument("--medir-t1", action="store_true")
    ap.add_argument("--timeout", type=float, default=3600)
    ap.add_argument("--salida", default=str(RAIZ / "results" / "bench" / "hibrido.csv"))
    ap.add_argument("--figura", action="store_true", help="generar las figuras al terminar")
    ap.add_argument("--solo-figura", action="store_true", help="solo graficar el resumen existente")
    ap.add_argument("--carpeta-figuras", default=str(RAIZ / "results" / "figures"))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--permitir-debug", action="store_true")
    a = ap.parse_args()

    salida = Path(a.salida)
    resumen_csv = salida.with_name(salida.stem + "_resumen.csv")
    if a.solo_figura:
        for r in figuras(resumen_csv, a.carpeta_figuras):
            print(f"escrito {r}")
        return

    presupuestos = cm.lista_enteros(a.presupuestos)
    bd = Path(a.build_dir)
    serial, exe = bd / "src/backends/serial/pp_serial", bd / "src/backends/hybrid/pp_hibrido"
    mpiexec = cm.mpiexec_de(bd)
    cpu, fisicos, logicos = cm.info_cpu()
    comunes = ["--config", a.config, "--n", str(a.n), "--semilla", str(a.semilla), "--config-id", str(a.config_id)]
    afinidad = f"OMP_PROC_BIND={a.bind};OMP_PLACES={a.places};mpirun --bind-to {a.bind_to}"

    def cmd(p, h):
        return comando(mpiexec, exe, p, h, comunes, bind_to=a.bind_to, oversubscribe=p > logicos, schedule=a.schedule)

    if a.dry_run:
        print(f"# {afinidad}")
        print(" ".join(map(str, [serial, *comunes])) + "   # referencia V1 (y T1 si no coincide)")
        for b, p, h in plan(presupuestos):
            print(" ".join(cmd(p, h)) + f"   # B={b}, calentamiento + {a.reps} repeticiones")
        return

    for e in (serial, exe):
        if not e.exists():
            sys.exit(f"no existe {e}; compile con -DPP_BUILD_MPI=ON (cmake --build {bd})")
    tipo = cm.leer_cache(bd, "CMAKE_BUILD_TYPE") or "desconocido"
    if tipo in ("Debug", "desconocido") and not a.permitir_debug:
        sys.exit(f"el build es '{tipo}': los tiempos no sirven. Recompile con -DCMAKE_BUILD_TYPE=Release.")

    meta = dict(cpu=cpu, ram_gb=cm.ram_gb(), compilador=cm.version_compilador(bd), tipo_build=tipo,
                commit=cm.commit_git(), fecha=datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
                so=platform.platform(), mpiexec=mpiexec)
    entorno = cm.entorno_mpi(PP_COMMIT=meta["commit"], OMP_PROC_BIND=a.bind, OMP_PLACES=a.places)
    ref, t_serial, fuente_t1, filas_serial = cm.referencia_serial(
        serial, comunes, entorno, a.t1_csv, a.n, a.semilla, a.config_id, a.reps, forzar=a.medir_t1)
    print(f"referencia secuencial k={ref['k']}  T1={t_serial:.4f}s ({fuente_t1})", flush=True)

    base = dict(n=a.n, semilla=a.semilla, config_id=a.config_id, dias=ref["dias"], schedule=a.schedule)
    corridas, resumen = [], []
    for b, p, h in plan(presupuestos):
        (cal, vcal), reps_v = cm.medir_punto(cmd(p, h), entorno, a.reps, a.timeout)
        todas = [(cal, vcal)] + reps_v
        equivalente = all(cm.equivalente(r, ref) and v["estado"] == "OK" for r, v in todas)
        for i, (r, v) in enumerate(todas):
            corridas.append(dict(
                nucleos_totales=b, procesos=p, hilos=h, factorizacion=f"{p}x{h}", hilos_efectivos=r["hilos"],
                repeticion=i, calentamiento=int(i == 0), tiempo_s=r["tiempo_s"], **base, k=r["k"],
                equivalente_serial=int(cm.equivalente(r, ref)), estado=v["estado"], nivel_hilos_mpi=v["nivel_hilos"],
                nodos=r.get("nodos", ""), distribucion=r.get("distribucion", ""),
                reparto_rangos=cm.reparto_texto(v["rangos"]), afinidad=afinidad,
                sobresuscrito=cm.sobresuscrito(b, fisicos), excede_logicos=cm.sobresuscrito(b, logicos),
                cpu=cpu, nucleos_fisicos=fisicos, nucleos_logicos=logicos, hardware=r.get("hardware", ""),
                commit=meta["commit"]))
        fila = fila_resumen(b, p, h, cal, [r for r, _ in reps_v], t_serial, fuente_t1, equivalente, afinidad,
                            fisicos, logicos, base)
        fila.update(hardware=reps_v[0][0].get("hardware", ""), **meta)
        resumen.append(fila)
        marca = " [SOBRESUSCRITO]" if fila["sobresuscrito"] else ""
        print(f"B={b:2d} {p:2d}x{h:<2d} media={fila['media']:.4f}s sd={fila['desviacion']:.4f}s "
              f"S={fila['speedup']:.2f} E={fila['eficiencia']:.2f} V1={'ok' if equivalente else 'FALLA'}{marca}",
              flush=True)

    cm.escribir_csv(salida, corridas)
    cm.escribir_csv(resumen_csv, resumen)
    if filas_serial:
        cm.escribir_csv(salida.with_name(salida.stem + "_secuencial_ref.csv"),
                        [dict(repeticion=i, calentamiento=int(i == 0), tiempo_s=r["tiempo_s"], k=r["k"], **base,
                              commit=meta["commit"]) for i, (r, _) in enumerate(filas_serial)])
    if a.figura:
        for r in figuras(resumen_csv, a.carpeta_figuras):
            print(f"escrito {r}")
    if not all(f["equivalente_serial"] for f in resumen):
        sys.exit("V1 FALLÓ: hay corridas híbridas distintas del secuencial; no use este CSV para speedup.")
    if any(f["sobresuscrito"] for f in resumen):
        print(f"AVISO: núcleos totales > {fisicos} físicos: esos puntos están sobresuscritos y se analizan aparte.")


if __name__ == "__main__":
    main()
