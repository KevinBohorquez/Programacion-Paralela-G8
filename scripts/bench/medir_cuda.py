#!/usr/bin/env python3
# T40 | Responsable: Lita (revisión: R6) | Barrido X5 de la extensión CUDA (EXT1).
"""Mide pp_cuda con 2/4/8/16 bloques × 128/256/512 hilos por bloque (X5) y con grillas de referencia
que sí llenan la GPU, con la misma carga y la misma semilla en todos los puntos.

Por punto: una corrida de calentamiento y cinco repeticiones (tiempo_s del CSV del simulador, que
mide cómputo + reducción + copia al anfitrión, sin crear el contexto CUDA). Además, en una corrida
aparte (fuera de los tiempos) se registran la ocupación teórica (API de ocupación de CUDA) y la
OBSERVADA (lanzamiento instrumentado con %smid y %globaltimer: SM distintos usados y bloques que
convivieron en cada SM). Nsight Compute no sirve en este equipo (ERR_NVGPUCTRPERM).

Referencias en el MISMO equipo y sesión (regla 2 de AGENTS.md): pp_serial (T1 propio) y pp_openmp
con todos los núcleos físicos. Cada punto se valida contra el serial: k e hist512 idénticos (V2).

Uso (en WSL Ubuntu-24.04, con build/cuda compilado por scripts/cuda/compilar_wsl.sh):
    python3 scripts/bench/medir_cuda.py                       # barrido completo, N = 1e7
    python3 scripts/bench/medir_cuda.py --n 20000 --repeticiones 1 --salida-dir /tmp/x5   # prueba rápida
    python3 scripts/bench/medir_cuda.py --graficar            # solo la figura, desde el resumen (Docker)

Salidas en --salida-dir (por defecto results/bench/lita_i5-12400F/):
    cuda.csv           una fila por corrida (calentamiento incluido)
    cuda_resumen.csv   una fila por punto: media, desviación, CV, mediana, speedups, ocupación
    cuda_log.txt       entorno, GPU, comandos y avisos
"""
import argparse
import csv
import datetime
import os
import platform
import re
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]


def comando_log(cmd):
    """Comando para el registro, con las rutas relativas a la raíz del repositorio (T58)."""
    raiz = str(RAIZ) + "/"
    return " ".join(str(c).replace(raiz, "") for c in cmd)
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _comun_bench as cb  # noqa: E402

BLOQUES_X5 = (2, 4, 8, 16)
HILOS_X5 = (128, 256, 512)
CAMPOS_OCUPACION = ("sm", "sm_usados", "registros_por_hilo", "bloques_por_sm_max", "bloques_por_sm", "olas",
                    "ocupacion_sm", "ocupacion_gpu", "sm_observados", "max_bloques_por_sm",
                    "media_bloques_por_sm", "ocupacion_observada", "ocupacion_gpu_observada")


def correr(cmd, entorno):
    """Corre el simulador con --salida a un CSV temporal y devuelve (fila, stdout)."""
    with tempfile.TemporaryDirectory() as d:
        salida = Path(d) / "r.csv"
        r = subprocess.run([*cmd, "--salida", str(salida)], capture_output=True, text=True, env=entorno)
        if r.returncode != 0:
            sys.exit(f"falló {' '.join(cmd)} (código {r.returncode})\n{r.stderr}")
        with open(salida, newline="", encoding="utf-8") as f:
            return next(csv.DictReader(f)), r.stdout


def ocupacion(texto):
    """Campos clave=valor de las líneas [cuda] de pp_cuda."""
    datos = {}
    for linea in texto.splitlines():
        if linea.startswith("[cuda]"):
            datos.update(dict(re.findall(r"(\w+)=(\S+)", linea)))
    return {k: datos.get(k, "") for k in CAMPOS_OCUPACION}


def medir(nombre, cmd, reps, entorno, log):
    cal, _ = correr([*cmd, "--silencioso", "--calentamiento"], entorno)
    filas = [correr([*cmd, "--silencioso", "--repeticion", str(i)], entorno)[0] for i in range(1, reps + 1)]
    tiempos = [float(f["tiempo_s"]) for f in filas]
    media = statistics.mean(tiempos)
    sd = statistics.stdev(tiempos) if len(tiempos) > 1 else 0.0
    log.write(f"{nombre}: {comando_log(cmd)}\n  tiempos={['%.4f' % t for t in tiempos]} media={media:.4f} cv={sd / media:.3%}\n")
    print(f"{nombre:28s} media={media:8.4f}s cv={sd / media:6.2%} k={filas[0]['k']}", flush=True)
    return cal, filas, tiempos


def graficar(resumen, destino):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    with open(resumen, newline="", encoding="utf-8") as f:
        filas = [r for r in csv.DictReader(f) if r["backend"] == "cuda"]
    x5 = [r for r in filas if r["grupo"] == "x5"]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4.2))
    colores = {"128": "#2a6f97", "256": "#e07a1f", "512": "#3a8d4f"}
    for h in ("128", "256", "512"):
        pts = sorted((int(r["bloques"]), float(r["speedup_t1"])) for r in x5 if r["hilos_por_bloque"] == h)
        a1.plot([p[0] for p in pts], [p[1] for p in pts], "o-", color=colores[h], label=f"{h} hilos/bloque")
    ref = [r for r in filas if r["grupo"] == "referencia"]
    if ref:
        mejor = max(ref, key=lambda r: float(r["speedup_t1"]))
        a1.axhline(float(mejor["speedup_t1"]), ls="--", color="gray",
                   label=f"GPU llena ({mejor['bloques']}×{mejor['hilos_por_bloque']})")
    a1.set_xscale("log", base=2)
    a1.set_xticks(list(BLOQUES_X5), [str(b) for b in BLOQUES_X5])
    a1.set_xlabel("bloques")
    a1.set_ylabel("speedup frente a T1 (pp_serial)")
    a1.set_title("X5: speedup por bloques e hilos por bloque")
    a1.legend(fontsize=8)
    a1.grid(alpha=0.3)
    for h in ("128", "256", "512"):
        pts = sorted((int(r["sm_observados"]), float(r["escenarios_por_s"]) / 1e6) for r in filas
                     if r["hilos_por_bloque"] == h)
        a2.plot([p[0] for p in pts], [p[1] for p in pts], "o", color=colores[h], label=f"{h} hilos/bloque")
    a2.set_xlabel("SM observados (de 24)")
    a2.set_ylabel("millones de escenarios por segundo")
    a2.set_title("El rendimiento sigue a los SM usados, no a los hilos")
    a2.legend(fontsize=8)
    a2.grid(alpha=0.3)
    fig.tight_layout()
    for ext in ("png", "svg"):
        fig.savefig(Path(destino) / f"cuda_x5.{ext}", dpi=150)
    print(f"figura: {Path(destino) / 'cuda_x5.png'}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--build-dir", default=str(RAIZ / "build" / "cuda"))
    ap.add_argument("--config", default=str(RAIZ / "config" / "sintetico.yaml"))
    ap.add_argument("--n", type=float, default=1e7, help="escenarios por corrida (igual en todos los puntos)")
    ap.add_argument("--semilla", type=int, default=20261015)
    ap.add_argument("--config-id", type=int, default=0)
    ap.add_argument("--repeticiones", type=int, default=5)
    ap.add_argument("--hilos-cpu", type=int, default=0, help="hilos de la referencia OpenMP (0 = núcleos físicos)")
    ap.add_argument("--salida-dir", default=str(RAIZ / "results" / "bench" / "lita_i5-12400F"))
    ap.add_argument("--graficar", action="store_true", help="solo genera la figura desde cuda_resumen.csv")
    a = ap.parse_args()

    destino = Path(a.salida_dir)
    figuras = RAIZ / "results" / "figures"
    if a.graficar:
        graficar(destino / "cuda_resumen.csv", figuras)
        return

    bd = Path(a.build_dir) / "src" / "backends"
    exes = {"serial": bd / "serial/pp_serial", "openmp": bd / "openmp/pp_openmp", "cuda": bd / "cuda/pp_cuda"}
    for e in exes.values():
        if not e.exists():
            sys.exit(f"no existe {e}; compile con scripts/cuda/compilar_wsl.sh")
    tipo = cb.leer_cache_cmake(a.build_dir, "CMAKE_BUILD_TYPE")
    if tipo != "Release":
        sys.exit(f"el build es '{tipo}': los tiempos no sirven; compile en Release.")

    cpu, fisicos, logicos = cb.info_cpu()
    hilos_cpu = a.hilos_cpu or fisicos
    n = int(a.n)
    commit = cb.commit_git()
    entorno = dict(os.environ, PP_COMMIT=commit, OMP_PROC_BIND="close", OMP_PLACES="cores")
    entorno.pop("OMP_NUM_THREADS", None)
    comunes = ["--config", a.config, "--n", str(n), "--semilla", str(a.semilla), "--config-id", str(a.config_id)]
    destino.mkdir(parents=True, exist_ok=True)
    log = open(destino / "cuda_log.txt", "w", encoding="utf-8")
    fecha = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    gpu = subprocess.run([str(exes["cuda"]), *comunes[:2], "--n", "1"], capture_output=True, text=True,
                         env=entorno).stdout
    gpu = next((l for l in gpu.splitlines() if l.startswith("bloques=")), "").split(" ", 3)[-1]
    meta = dict(cpu=cpu, nucleos_fisicos=fisicos, nucleos_logicos=logicos, ram_gb=cb.ram_gb(), gpu=gpu,
                commit=commit, fecha=fecha, so=platform.platform(), n=n, semilla=a.semilla, config=Path(a.config).name)
    log.write(f"# T40 · X5 · {fecha}\n# {meta}\n")

    # Puntos: referencias de CPU, el barrido X5 y grillas que llenan la GPU (1 bloque por SM y máximo residente).
    puntos = [("serial", "referencia", exes["serial"], [], 0, 0),
              ("openmp", "referencia", exes["openmp"], ["--hilos", str(hilos_cpu), "--schedule", "static"], 0, 0)]
    puntos += [("cuda", "x5", exes["cuda"], ["--bloques", str(b), "--hilos-por-bloque", str(h)], b, h)
               for h in HILOS_X5 for b in BLOQUES_X5]
    puntos += [("cuda", "referencia", exes["cuda"], ["--bloques", str(b), "--hilos-por-bloque", str(h)], b, h)
               for h in HILOS_X5 for b in (24, 0)]

    corridas, resumen, ref = [], [], {}
    for backend, grupo, exe, extra, b, h in puntos:
        cmd = [str(exe), *comunes, *extra]
        nombre = backend if backend != "cuda" else f"cuda {b or 'auto'}x{h}"
        cal, filas, tiempos = medir(nombre, cmd, a.repeticiones, entorno, log)
        if backend == "serial":
            ref = dict(k=filas[0]["k"], hist=filas[0]["hist512"], t1=statistics.mean(tiempos))
        if backend == "openmp":
            ref["tcpu"] = statistics.mean(tiempos)
        equivalente = all((f["k"], f["hist512"]) == (ref["k"], ref["hist"]) for f in [cal, *filas])
        occ = {k: "" for k in CAMPOS_OCUPACION}
        if backend == "cuda":
            _, salida = correr(cmd, entorno)  # corrida de diagnóstico, fuera de los tiempos
            occ = ocupacion(salida)
        for i, f in enumerate([cal, *filas]):
            corridas.append(dict(backend=backend, grupo=grupo, bloques=f["bloques"], hilos_por_bloque=f["hilos_por_bloque"],
                                 hilos=f["hilos"], repeticion=i, calentamiento=int(i == 0), tiempo_s=f["tiempo_s"],
                                 k=f["k"], equivalente_serial=int(equivalente), **meta))
        media = statistics.mean(tiempos)
        sd = statistics.stdev(tiempos) if len(tiempos) > 1 else 0.0
        fila = dict(backend=backend, grupo=grupo, bloques=filas[0]["bloques"], hilos_por_bloque=filas[0]["hilos_por_bloque"],
                    hilos=filas[0]["hilos"], hilos_gpu=(int(filas[0]["bloques"]) * int(filas[0]["hilos_por_bloque"])
                                                        if backend == "cuda" else ""),
                    t_calentamiento=cal["tiempo_s"])
        fila.update({f"t{i}": t for i, t in enumerate(tiempos, 1)})
        fila.update(media=media, desviacion=sd, cv=sd / media, mediana=statistics.median(tiempos),
                    escenarios_por_s=n / media, speedup_t1=ref["t1"] / media,
                    speedup_cpu=(ref["tcpu"] / media) if "tcpu" in ref else "",
                    k=filas[0]["k"], equivalente_serial=int(equivalente), **occ, **meta)
        resumen.append(fila)
        if not equivalente:
            log.write(f"  AVISO: {nombre} no coincide con el serial (k o hist512)\n")
        if sd / media > 0.05:
            log.write(f"  AVISO: {nombre} con CV {sd / media:.1%} > 5 %: posible interferencia\n")

    for ruta, contenido in ((destino / "cuda.csv", corridas), (destino / "cuda_resumen.csv", resumen)):
        with open(ruta, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(contenido[0].keys()), lineterminator="\n")
            w.writeheader()
            w.writerows(contenido)
        print(f"escrito {ruta}")
    log.close()
    if not all(r["equivalente_serial"] for r in resumen):
        sys.exit("V2 FALLÓ en algún punto: no use estos tiempos.")


if __name__ == "__main__":
    main()
