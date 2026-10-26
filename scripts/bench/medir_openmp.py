#!/usr/bin/env python3
# T16 | Responsable: Lita (borrador preparado junto con T15; revisión: Miguel) | Barrido OpenMP de 2, 4, 8 y 16 hilos.
"""Mide el backend OpenMP frente a la referencia secuencial con la MISMA carga y semilla.

Por cada punto (schedule x hilos): una corrida de calentamiento (no cuenta) y N repeticiones
(5 por defecto). Antes mide la referencia secuencial con el mismo protocolo (backend=serial).
Cada corrida se compara con el secuencial (k, n, histograma idénticos = V1).

Salidas (con --salida results/bench/openmp.csv, el valor por defecto):
  openmp.csv                 UNA fila por corrida OpenMP (calentamiento = repetición 0, luego 1..5) con la
                             cabecera de docs/protocolo-graficos-openmp.md, que lee T18 (graficar_openmp.py).
  openmp_secuencial_ref.csv  igual, para la referencia secuencial medida con el mismo binario, N, semilla y
                             commit (sirve de T1 a T18 mientras no llegue el CSV de T14).
  openmp_resumen.csv         UNA fila por punto: cinco tiempos, media, desviación estándar muestral,
                             afinidad, hardware, compilador, commit y las marcas `sobresuscrito`
                             (hilos > núcleos físicos) y `excede_logicos`.
El commit se toma de PP_COMMIT si está definida (también la leen los ejecutables); si no, de git.

IMPORTANTE: los tiempos solo valen en la máquina de referencia con el binario en Release. El script
se niega a medir un build Debug (use --permitir-debug solo para probar el script).

Ejemplo (máquina de referencia, tras `cmake -S . -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build`):
    python3 scripts/bench/medir_openmp.py --n 20000000 --hilos 2,4,8,16 --schedules static,dynamic,64
"""
import argparse
import csv
import datetime
import os
import platform
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]


# ---------- hardware y entorno ----------
def info_cpu():
    modelo, fisicos, logicos, pares, fis = "desconocido", 0, 0, set(), "0"
    try:
        for linea in open("/proc/cpuinfo"):
            if ":" not in linea:
                continue
            k, v = (s.strip() for s in linea.split(":", 1))
            if k == "model name" and modelo == "desconocido":
                modelo = v
            elif k == "processor":
                logicos += 1
            elif k == "physical id":
                fis = v
            elif k == "core id":
                pares.add((fis, v))
        fisicos = len(pares)
    except OSError:
        pass
    logicos = logicos or os.cpu_count() or 0
    return modelo, (fisicos or logicos), logicos


def ram_gb():
    try:
        for linea in open("/proc/meminfo"):
            if linea.startswith("MemTotal"):
                return round(int(linea.split()[1]) / 1024 / 1024, 1)
    except OSError:
        pass
    return ""


def leer_cache(build_dir, clave):
    try:
        for linea in open(Path(build_dir) / "CMakeCache.txt"):
            if linea.startswith(clave + ":"):
                return linea.split("=", 1)[1].strip()
    except OSError:
        pass
    return ""


def version_compilador(build_dir):
    exe = leer_cache(build_dir, "CMAKE_CXX_COMPILER")
    if not exe:
        return "desconocido"
    try:
        return subprocess.run([exe, "--version"], capture_output=True, text=True).stdout.splitlines()[0]
    except (OSError, IndexError):
        return exe


def commit_git():
    if os.environ.get("PP_COMMIT"):
        return os.environ["PP_COMMIT"]
    try:
        r = subprocess.run(["git", "-C", str(RAIZ), "rev-parse", "--short=12", "HEAD"], capture_output=True, text=True)
        c = r.stdout.strip() if r.returncode == 0 else ""
        if c:
            sucio = subprocess.run(["git", "-C", str(RAIZ), "status", "--porcelain"], capture_output=True, text=True).stdout.strip()
            return c + ("+cambios_sin_commit" if sucio else "")
    except OSError:
        pass
    return "desconocido"


# ---------- ejecución ----------
def correr(exe, args_comunes, extra, entorno):
    with tempfile.TemporaryDirectory() as d:
        salida = Path(d) / "r.csv"
        cmd = [str(exe), *args_comunes, *extra, "--silencioso", "--salida", str(salida)]
        r = subprocess.run(cmd, capture_output=True, text=True, env=entorno)
        if r.returncode != 0:
            sys.exit(f"falló {' '.join(cmd)}\n{r.stderr}")
        with open(salida, newline="") as f:
            return next(csv.DictReader(f))


def parse_schedule(s):
    # "static" | "dynamic" | "guided" | "dynamic:64" | atajo "64" = dynamic:64
    return f"dynamic:{s}" if s.isdigit() else s


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--build-dir", default=str(RAIZ / "build"))
    ap.add_argument("--config", default=str(RAIZ / "config" / "sintetico.yaml"),
                    help="configuración con los parámetros del modelo (sintéticos hasta recibir T10)")
    ap.add_argument("--n", type=int, default=20_000_000, help="escenarios por corrida (igual para todo el barrido)")
    ap.add_argument("--semilla", type=int, default=20261015)
    ap.add_argument("--config-id", type=int, default=0)
    ap.add_argument("--hilos", default="2,4,8,16")
    ap.add_argument("--schedules", default="static,dynamic,64", help="lista separada por comas; '64' = dynamic:64")
    ap.add_argument("--repeticiones", type=int, default=5)
    ap.add_argument("--bind", default="close", help="OMP_PROC_BIND (def. 8.5 de la definición: close)")
    ap.add_argument("--places", default="cores", help="OMP_PLACES (def. 8.5: cores)")
    ap.add_argument("--salida", default=str(RAIZ / "results" / "bench" / "openmp.csv"))
    ap.add_argument("--permitir-debug", action="store_true")
    a = ap.parse_args()

    bd = Path(a.build_dir)
    serial, openmp = bd / "src/backends/serial/pp_serial", bd / "src/backends/openmp/pp_openmp"
    for exe in (serial, openmp):
        if not exe.exists():
            sys.exit(f"no existe {exe}; compile primero (cmake --build {bd})")
    tipo = leer_cache(bd, "CMAKE_BUILD_TYPE") or "desconocido"
    if tipo in ("Debug", "") and not a.permitir_debug:
        sys.exit(f"el build es '{tipo}': los tiempos no sirven. Recompile con -DCMAKE_BUILD_TYPE=Release.")

    cpu, fisicos, logicos = info_cpu()
    entorno = dict(os.environ, OMP_PROC_BIND=a.bind, OMP_PLACES=a.places)
    entorno.pop("OMP_NUM_THREADS", None)
    entorno.pop("OMP_SCHEDULE", None)
    afinidad = f"OMP_PROC_BIND={a.bind};OMP_PLACES={a.places}"
    comunes = ["--config", a.config, "--n", str(a.n), "--semilla", str(a.semilla), "--config-id", str(a.config_id)]
    hilos = [int(x) for x in a.hilos.split(",")]
    schedules = [parse_schedule(s.strip()) for s in a.schedules.split(",")]
    meta = dict(cpu=cpu, ram_gb=ram_gb(), compilador=version_compilador(bd), tipo_build=tipo,
                commit=commit_git(), fecha=datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
                so=platform.platform())

    entorno["PP_COMMIT"] = meta["commit"]  # los ejecutables escriben el mismo commit que el script
    puntos = [("serial", 1, "-")] + [("openmp", h, s) for s in schedules for h in hilos]
    filas, corridas, ref = [], [], None
    for backend, h, sched in puntos:
        exe = serial if backend == "serial" else openmp
        extra = [] if backend == "serial" else ["--hilos", str(h), "--schedule", sched]
        cal = correr(exe, comunes, extra + ["--calentamiento"], entorno)  # calentamiento: no cuenta
        reps = [correr(exe, comunes, extra + ["--repeticion", str(i)], entorno) for i in range(1, a.repeticiones + 1)]
        tiempos = [float(r["tiempo_s"]) for r in reps]
        for i, r in enumerate([cal] + reps):
            corridas.append(dict(
                modelo="secuencial" if backend == "serial" else "openmp", hilos=h, repeticion=i,
                tiempo_s=r["tiempo_s"], n=a.n, semilla=a.semilla, cpu=cpu, nucleos_fisicos=fisicos,
                afinidad=afinidad, schedule=r["schedule"] or "none", commit=meta["commit"],
                calentamiento=int(i == 0), hilos_efectivos=r["hilos"], nucleos_logicos=logicos,
                sobresuscrito=int(backend == "openmp" and h > fisicos),
                excede_logicos=int(backend == "openmp" and h > logicos), k=r["k"], config_id=a.config_id))
        k, n, hist = reps[0]["k"], reps[0]["n"], reps[0]["hist512"]
        if ref is None:
            ref = (k, n, hist)
        # V1: todas las repeticiones deben coincidir entre sí y con el secuencial
        equivalente = all((r["k"], r["n"], r["hist512"]) == ref for r in reps + [cal])
        usados = int(reps[0]["hilos"])
        fila = dict(backend=backend, hilos=h, hilos_efectivos=usados, schedule=reps[0]["schedule"] or "-",
                    n=a.n, semilla=a.semilla, config_id=a.config_id, afinidad=afinidad,
                    nucleos_fisicos=fisicos, nucleos_logicos=logicos,
                    sobresuscrito=int(backend == "openmp" and h > fisicos),
                    excede_logicos=int(backend == "openmp" and h > logicos),
                    t_calentamiento=cal["tiempo_s"])
        for i, t in enumerate(tiempos, 1):
            fila[f"t{i}"] = t
        fila.update(media=statistics.mean(tiempos),
                    desviacion=statistics.stdev(tiempos) if len(tiempos) > 1 else 0.0,
                    k=k, equivalente_serial=int(equivalente), **meta)
        filas.append(fila)
        marca = " [SOBRESUSCRITO]" if fila["sobresuscrito"] else ""
        print(f"{backend:6s} hilos={h:2d} {fila['schedule']:10s} media={fila['media']:.4f}s "
              f"sd={fila['desviacion']:.4f}s V1={'ok' if equivalente else 'FALLA'}{marca}", flush=True)

    salida = Path(a.salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    archivos = {
        salida: [c for c in corridas if c["modelo"] == "openmp"],
        salida.with_name(salida.stem + "_secuencial_ref.csv"): [c for c in corridas if c["modelo"] == "secuencial"],
        salida.with_name(salida.stem + "_resumen.csv"): filas,
    }
    for ruta, contenido in archivos.items():
        with open(ruta, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(contenido[0].keys()))
            w.writeheader()
            w.writerows(contenido)
        print(f"escrito {ruta}")
    if not all(f["equivalente_serial"] for f in filas):
        sys.exit("V1 FALLÓ: hay corridas OpenMP distintas del secuencial; no use este CSV.")
    if any(f["sobresuscrito"] for f in filas):
        print(f"AVISO: hilos > {fisicos} núcleos físicos: esos puntos están sobresuscritos y se analizan aparte.")


if __name__ == "__main__":
    main()
