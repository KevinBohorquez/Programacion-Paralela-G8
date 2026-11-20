#!/usr/bin/env python3
# T41 | Responsable: Lita (revisión: R1) | EXT2: CPU frente a CPU + GPU con el esquema dinámico E2.
"""Compara el esquema dinámico E2 con trabajadores de CPU solamente frente a E2 con la GPU como un
trabajador más (pp_mpi_dinamico_gpu), con la misma carga, semilla y tamaño de bloque de la cola.

Variantes (P = núcleos físicos; el rango 0 es el maestro y no simula):
    cpu          mpirun -np P    pp_mpi_dinamico       P-1 trabajadores de CPU
    cpu_gpu      mpirun -np P    pp_mpi_dinamico_gpu   P-2 de CPU + 1 GPU  (mismos procesos que «cpu»)
    cpu_gpu_mas1 mpirun -np P+1  pp_mpi_dinamico_gpu   P-1 de CPU + 1 GPU  (la GPU se suma a «cpu»; su
                                                        rango duerme mientras espera al kernel)
    gpu          mpirun -np 2    pp_mpi_dinamico_gpu   solo el trabajador GPU
y como referencias del mismo equipo y sesión: pp_serial (T1) y pp_cuda (la misma grilla, sin MPI).

Por variante: calentamiento + cinco repeticiones. V1/V3: cada corrida debe dar estado=OK en [verif]
(suma = N, cobertura exacta de la cola) y el mismo k e hist512 que el serial. Del [verif] se obtiene
el trabajo de cada rango: fracción de escenarios de la GPU, bloques por trabajador y mensajes de E2
(por trabajador: bloques + 1 REQ, bloques WORK y 1 STOP).

Uso (WSL Ubuntu-24.04, build/cuda compilado con MPI por scripts/cuda/compilar_wsl.sh):
    python3 scripts/bench/medir_cpu_gpu.py --bloques 24 --hilos-por-bloque 128
    python3 scripts/bench/medir_cpu_gpu.py --n 20000 --repeticiones 1 --salida-dir /tmp/ext2   # prueba
    python3 scripts/bench/medir_cpu_gpu.py --graficar        # solo la figura (Docker con matplotlib)
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


def correr(cmd, entorno):
    """Corre con --salida a un CSV temporal; devuelve (fila, stdout, stderr)."""
    with tempfile.TemporaryDirectory() as d:
        salida = Path(d) / "r.csv"
        r = subprocess.run([*cmd, "--salida", str(salida)], capture_output=True, text=True, env=entorno)
        if r.returncode != 0:
            sys.exit(f"falló {' '.join(cmd)} (código {r.returncode})\n{r.stdout[-2000:]}\n{r.stderr[-2000:]}")
        with open(salida, newline="", encoding="utf-8") as f:
            return next(csv.DictReader(f)), r.stdout, r.stderr


def rangos(stdout):
    """{rango: (bloques, n_local)} de las líneas [verif] rango=... de E2, y el estado global."""
    por_rango = {}
    for m in re.finditer(r"\[verif\] rango=(\d+) bloques=(\d+) n_local=(\d+)", stdout):
        por_rango[int(m.group(1))] = (int(m.group(2)), int(m.group(3)))
    estado = re.search(r"estado=(\w+)", stdout)
    return por_rango, (estado.group(1) if estado else "")


def graficar(resumen, destino):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    with open(resumen, newline="", encoding="utf-8") as f:
        filas = list(csv.DictReader(f))
    orden = ["serial", "cpu", "gpu", "cuda_sin_mpi", "cpu_gpu", "cpu_gpu_mas1"]
    filas = sorted((r for r in filas if r["variante"] in orden), key=lambda r: orden.index(r["variante"]))
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(11, 4.2))
    nombres = [r["etiqueta"] for r in filas]
    a1.barh(nombres, [float(r["escenarios_por_s"]) / 1e6 for r in filas], color="#2a6f97")
    for i, r in enumerate(filas):
        a1.text(float(r["escenarios_por_s"]) / 1e6, i, f" ×{float(r['speedup_t1']):.1f}", va="center", fontsize=8)
    a1.set_xlabel("millones de escenarios por segundo (× = speedup frente a T1)")
    a1.set_title("EXT2: CPU frente a CPU + GPU (E2 dinámico)")
    a1.invert_yaxis()
    mixtas = [r for r in filas if r["variante"] in ("cpu_gpu", "cpu_gpu_mas1")]
    if mixtas:
        x = range(len(mixtas))
        gpu = [float(r["fraccion_gpu"]) for r in mixtas]
        a2.bar(x, gpu, color="#e07a1f", label="GPU (1 trabajador)")
        a2.bar(x, [1 - g for g in gpu], bottom=gpu, color="#2a6f97", label="CPU (resto de trabajadores)")
        a2.set_xticks(list(x), [r["etiqueta"] for r in mixtas], fontsize=8)
        a2.set_ylabel("fracción de los N escenarios")
        a2.set_title("Reparto que hizo la cola dinámica")
        a2.set_ylim(0, 1.25)
        a2.legend(fontsize=8, loc="upper center", ncol=2)
    fig.tight_layout()
    for ext in ("png", "svg"):
        fig.savefig(Path(destino) / f"cuda_ext2.{ext}", dpi=150)
    print(f"figura: {Path(destino) / 'cuda_ext2.png'}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--build-dir", default=str(RAIZ / "build" / "cuda"))
    ap.add_argument("--config", default=str(RAIZ / "config" / "sintetico.yaml"))
    ap.add_argument("--n", type=float, default=1e7)
    ap.add_argument("--semilla", type=int, default=20261015)
    ap.add_argument("--lote", type=int, default=62500, help="tamaño de bloque de la cola E2 (igual en todas)")
    ap.add_argument("--bloques", type=int, default=24, help="grilla del trabajador GPU")
    ap.add_argument("--hilos-por-bloque", type=int, default=128)
    ap.add_argument("--procesos", type=int, default=0, help="P (0 = núcleos físicos)")
    ap.add_argument("--repeticiones", type=int, default=5)
    ap.add_argument("--salida-dir", default=str(RAIZ / "results" / "bench" / "lita_i5-12400F"))
    ap.add_argument("--graficar", action="store_true")
    a = ap.parse_args()

    destino = Path(a.salida_dir)
    if a.graficar:
        graficar(destino / "cuda_ext2_resumen.csv", RAIZ / "results" / "figures")
        return

    bd = Path(a.build_dir) / "src" / "backends"
    exes = {"serial": bd / "serial/pp_serial", "cuda": bd / "cuda/pp_cuda",
            "e2": bd / "mpi/pp_mpi_dinamico", "e2gpu": bd / "cuda/pp_mpi_dinamico_gpu"}
    for e in exes.values():
        if not e.exists():
            sys.exit(f"no existe {e}; compile con scripts/cuda/compilar_wsl.sh (con MPI)")
    if cb.leer_cache_cmake(a.build_dir, "CMAKE_BUILD_TYPE") != "Release":
        sys.exit("el build no es Release: los tiempos no sirven.")

    cpu, fisicos, logicos = cb.info_cpu()
    p = a.procesos or fisicos
    n = int(a.n)
    commit = cb.commit_git()
    entorno = dict(os.environ, PP_COMMIT=commit)
    comunes = ["--config", a.config, "--n", str(n), "--semilla", str(a.semilla), "--lote", str(a.lote)]
    grilla = ["--bloques", str(a.bloques), "--hilos-por-bloque", str(a.hilos_por_bloque)]
    mpirun = ["mpirun", "--bind-to", "none"]
    destino.mkdir(parents=True, exist_ok=True)
    fecha = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    salida_gpu = subprocess.run([str(exes["cuda"]), "--config", a.config, "--n", "1"], capture_output=True,
                                text=True, env=entorno).stdout
    gpu = next((l for l in salida_gpu.splitlines() if l.startswith("bloques=")), "").split(" ", 3)[-1]
    meta = dict(cpu=cpu, nucleos_fisicos=fisicos, nucleos_logicos=logicos, ram_gb=cb.ram_gb(), gpu=gpu,
                mpi=subprocess.run(["mpirun", "--version"], capture_output=True, text=True).stdout.splitlines()[0],
                commit=commit, fecha=fecha, so=platform.platform(), n=n, semilla=a.semilla, lote=a.lote,
                grilla_gpu=f"{a.bloques}x{a.hilos_por_bloque}", config=Path(a.config).name)
    log = open(destino / "cuda_ext2_log.txt", "w", encoding="utf-8")
    log.write(f"# T41 · EXT2 · {fecha}\n# {meta}\n")

    # (variante, etiqueta, comando, procesos, trabajadores CPU, trabajadores GPU, sobresuscrito)
    variantes = [
        ("serial", "serial (T1)", [str(exes["serial"]), *comunes], 1, 1, 0, 0),
        ("cuda_sin_mpi", f"pp_cuda {a.bloques}x{a.hilos_por_bloque}", [str(exes["cuda"]), *comunes, *grilla], 1, 0, 1, 0),
        ("cpu", f"E2 CPU: {p - 1} CPU", [*mpirun, "-np", str(p), str(exes["e2"]), *comunes], p, p - 1, 0, 0),
        ("gpu", "E2 solo GPU", [*mpirun, "-np", "2", str(exes["e2gpu"]), *comunes, *grilla], 2, 0, 1, 0),
        ("cpu_gpu", f"E2 CPU+GPU: {p - 2} CPU + GPU", [*mpirun, "-np", str(p), str(exes["e2gpu"]), *comunes, *grilla],
         p, p - 2, 1, 0),
        ("cpu_gpu_mas1", f"E2 CPU+GPU: {p - 1} CPU + GPU",
         [*mpirun, "--oversubscribe", "-np", str(p + 1), str(exes["e2gpu"]), *comunes, *grilla], p + 1, p - 1, 1, 1),
    ]
    corridas, resumen, ref = [], [], {}
    for var, etiqueta, cmd, procs, wcpu, wgpu, sobre in variantes:
        res = [correr([*cmd, *(["--calentamiento"] if i == 0 else ["--repeticion", str(i)])], entorno)
               for i in range(a.repeticiones + 1)]
        tiempos = [float(f["tiempo_s"]) for f, _, _ in res[1:]]
        if var == "serial":
            ref = dict(k=res[0][0]["k"], hist=res[0][0]["hist512"], t1=statistics.mean(tiempos))
        if var == "cpu":
            ref["tcpu"] = statistics.mean(tiempos)
        equivalente = all((f["k"], f["hist512"]) == (ref["k"], ref["hist"]) for f, _, _ in res)
        estados = {rangos(out)[1] for _, out, _ in res if procs > 1}
        v3 = estados <= {"OK"}
        # Trabajo por rango (de la primera repetición medida): fracción GPU, bloques y mensajes de E2.
        por_rango, _ = rangos(res[1][1]) if procs > 1 else ({}, "")
        trabajadores = {r: v for r, v in por_rango.items() if r != 0}
        rango_gpu = procs - 1 if (wgpu and procs > 1) else None
        n_gpu = trabajadores.get(rango_gpu, (0, 0))[1] if rango_gpu is not None else (n if var == "cuda_sin_mpi" else 0)
        bloques_gpu = trabajadores.get(rango_gpu, (0, 0))[0] if rango_gpu is not None else 0
        cpu_n = [v[1] for r, v in trabajadores.items() if r != rango_gpu]
        mensajes = sum(2 * b + 2 for b, _ in trabajadores.values())
        t_ctx = re.search(r"t_contexto_s=(\S+)", res[1][2])
        for i, (f, out, _) in enumerate(res):
            corridas.append(dict(variante=var, etiqueta=etiqueta, repeticion=i, calentamiento=int(i == 0),
                                 tiempo_s=f["tiempo_s"], k=f["k"], procesos=procs, trabajadores_cpu=wcpu,
                                 trabajadores_gpu=wgpu, sobresuscrito=sobre,
                                 estado_v3=rangos(out)[1] if procs > 1 else "", equivalente_serial=int(equivalente),
                                 **meta))
        media = statistics.mean(tiempos)
        sd = statistics.stdev(tiempos) if len(tiempos) > 1 else 0.0
        fila = dict(variante=var, etiqueta=etiqueta, procesos=procs, trabajadores_cpu=wcpu, trabajadores_gpu=wgpu,
                    sobresuscrito=sobre, t_calentamiento=res[0][0]["tiempo_s"])
        fila.update({f"t{i}": t for i, t in enumerate(tiempos, 1)})
        fila.update(media=media, desviacion=sd, cv=sd / media, mediana=statistics.median(tiempos),
                    escenarios_por_s=n / media, speedup_t1=ref["t1"] / media,
                    speedup_cpu=(ref["tcpu"] / media) if "tcpu" in ref else "",
                    fraccion_gpu=n_gpu / n, bloques_gpu=bloques_gpu,
                    n_cpu_por_trabajador_media=statistics.mean(cpu_n) if cpu_n else "",
                    desbalance_cpu=(max(cpu_n) / statistics.mean(cpu_n)) if cpu_n else "",
                    mensajes_e2=mensajes if procs > 1 else "", t_contexto_gpu_s=t_ctx.group(1) if t_ctx else "",
                    k=ref["k"], equivalente_serial=int(equivalente), v3_ok=int(v3), **meta)
        resumen.append(fila)
        log.write(f"{var}: {comando_log(cmd)}\n  tiempos={['%.4f' % t for t in tiempos]} media={media:.4f} "
                  f"cv={sd / media:.2%} fraccion_gpu={n_gpu / n:.3f} V1={'ok' if equivalente else 'FALLA'} "
                  f"V3={'ok' if v3 else 'FALLA'}\n")
        if procs > 1:
            log.write(f"  rangos (bloques, n_local): {por_rango}\n")
        if t_ctx:
            log.write(f"  contexto CUDA creado antes de MPI_Init en {t_ctx.group(1)} s (fuera del tiempo)\n")
        print(f"{etiqueta:30s} media={media:8.4f}s cv={sd / media:6.2%} ×T1={ref['t1'] / media:5.2f} "
              f"GPU={n_gpu / n:6.1%} V1={'ok' if equivalente else 'FALLA'} V3={'ok' if v3 else 'FALLA'}", flush=True)

    for ruta, contenido in ((destino / "cuda_ext2.csv", corridas), (destino / "cuda_ext2_resumen.csv", resumen)):
        with open(ruta, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(contenido[0].keys()), lineterminator="\n")
            w.writeheader()
            w.writerows(contenido)
        print(f"escrito {ruta}")
    log.close()
    if not all(r["equivalente_serial"] and r["v3_ok"] for r in resumen):
        sys.exit("V1 o V3 FALLÓ en alguna variante: no use estos tiempos.")


if __name__ == "__main__":
    main()
