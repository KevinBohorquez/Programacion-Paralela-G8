"""T56 | Angela: campaña X8; entrada pública: medir_cpu_gpu.py --experimento x8.

Tres variantes en clúster y las mismas tres en una PC. Requiere el contrato
de T54/T55; nunca sustituye pp_mpi_omp_cuda por la implementación EXT2.
"""
import argparse
import csv
import datetime
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shlex
import socket
import statistics
import subprocess
import tempfile

import _comun_bench as cb

VARIANTES = ("mpi", "mpi_openmp", "mpi_openmp_gpu")


def parser():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--experimento", required=True, choices=["x8"])
    ap.add_argument("--build-dir", type=Path, default=Path("build/cuda"), help="build de T54/T55 con CUDA")
    ap.add_argument("--build-cpu-dir", type=Path, default=Path("build/docker"), help="build T54 sin CUDA")
    ap.add_argument("--config", type=Path, default=cb.RAIZ / "config/sintetico.yaml")
    ap.add_argument("--cargas", default="1e7,2e7,5e7,1e8")
    ap.add_argument("--procesos", type=int, default=4, help="incluye maestro; igual en las seis configuraciones")
    ap.add_argument("--hilos", type=int, default=2, help="por trabajador CPU; MPI solo usa uno")
    ap.add_argument("--lote", type=int, default=62500)
    ap.add_argument("--semilla", type=int, default=20261015)
    ap.add_argument("--config-id", type=int, default=0)
    ap.add_argument("--repeticiones", type=int, default=5)
    ap.add_argument("--hostfile", type=Path, required=True, help="2–3 PC de T25; rutas de binarios iguales en todas")
    ap.add_argument("--mpirun-extra", default="", help="opciones de red/SSH de T25, como una cadena")
    ap.add_argument("--t1-csv", type=Path, default=cb.RAIZ / "results/bench/secuencial_t1.csv")
    ap.add_argument("--salida", type=Path, default=cb.RAIZ / "results/bench/x8.csv")
    ap.add_argument("--figuras", type=Path, default=cb.RAIZ / "results/figures")
    ap.add_argument("--timeout", type=float, default=None)
    ap.add_argument("--host-en-reposo", action="store_true", help="confirmación del operador en todas las PC")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--graficar", action="store_true", help="solo regenera las figuras desde el CSV de rangos")
    return ap


def plan(a):
    cargas = [int(float(n)) for n in a.cargas.split(",")]
    if (not cargas or any(n < 1 for n in cargas) or len(set(cargas)) != len(cargas) or
            a.procesos < 3 or a.hilos < 1 or a.lote < 1 or a.repeticiones < 1):
        raise ValueError("cargas distintas y positivas, procesos >= 3, hilos/lote/repeticiones >= 1")
    return [(n, ambito, variante) for n in cargas for ambito in ("cluster", "local") for variante in VARIANTES]


def binario(a, variante):
    if variante == "mpi":
        return a.build_cpu_dir / "src/backends/mpi/pp_mpi_dinamico"
    build = a.build_dir if variante == "mpi_openmp_gpu" else a.build_cpu_dir
    return build / "src/backends/cuda/pp_mpi_omp_cuda"


def comando(a, n, ambito, variante):
    cmd = ["mpirun", "--bind-to", "none", "--map-by", "slot", "-np", str(a.procesos),
           "-x", "OMP_PROC_BIND", "-x", "OMP_PLACES", "-x", "PP_COMMIT", "-x", "GIT_COMMIT"]
    if ambito == "cluster":
        cmd += ["--hostfile", str(a.hostfile)]
    else:
        cmd += ["--host", f"localhost:{a.procesos}"]
    cmd += shlex.split(a.mpirun_extra)
    cmd += ["python3", str(Path(__file__).with_name("_lanzador_x8.py").resolve()), str(binario(a, variante).resolve()),
            "--config", str(a.config.resolve()), "--n", str(n), "--semilla", str(a.semilla),
            "--config-id", str(a.config_id), "--lote", str(a.lote)]
    if variante != "mpi":
        cmd += ["--hilos", str(a.hilos)]
    return cmd


def correr(cmd, env, log, timeout):
    with tempfile.TemporaryDirectory() as d:
        salida = Path(d) / "salida.csv"
        argv = [*cmd, "--salida", str(salida)]
        log.write(f"$ {shlex.join(argv)}\n")
        log.flush()
        r = subprocess.run(argv, capture_output=True, text=True, env=env, timeout=timeout)
        log.write(f"{r.stdout}\n{r.stderr}\n[codigo_salida] {r.returncode}\n")
        log.flush()
        if r.returncode or not salida.exists():
            raise ValueError(f"falló el simulador ({r.returncode}); consulte el log")
        return cb.leer_fila_simulador(salida), r.stdout, r.stderr


def firma(fila, n):
    hist = [int(x) for x in fila["hist512"].split(";")]
    if (int(fila["n"]) != n or len(hist) != 512 or min(hist) < 0 or sum(hist) != n or
            not 0 <= int(fila["k"]) <= n or not math.isfinite(float(fila["tiempo_s"])) or
            float(fila["tiempo_s"]) <= 0):
        raise ValueError("CSV del simulador incoherente (n, k, hist512 o tiempo)")
    return int(fila["k"]), tuple(hist)


def verificar_rangos(stdout, stderr, n, procesos, ambito, variante, lote):
    rangos = cb.parsear_verif(stdout)
    hosts = {int(r): h for r, h in re.findall(r"\[x8-host\] rango=(\d+) host=(\S+)", stderr)}
    gpu = {int(r) for r in re.findall(r"\[gpu\] rango=(\d+)", stdout + "\n" + stderr)}
    gpu.update(r["rango"] for r in rangos if r.get("tipo") == "gpu")
    esperados = set(range(procesos))
    estados = re.findall(r"\bestado=(\w+)", stdout)
    if not estados or any(e != "OK" for e in estados):
        raise ValueError("falta estado=OK global o falló V3")
    if {r["rango"] for r in rangos} != esperados or set(hosts) != esperados:
        raise ValueError("faltan rangos o hostnames observados; no se infiere el reparto del hostfile")
    if any("bloques" not in r or "n_local" not in r for r in rangos):
        raise ValueError("T54/T55 deben publicar bloques y n_local de cada rango")
    rangos = [{**r, "bloques": int(r["bloques"]), "n_local": int(r["n_local"])} for r in rangos]
    if sum(r["n_local"] for r in rangos) != n or rangos[0]["n_local"] != 0:
        raise ValueError("suma de escenarios por rango incorrecta o maestro con trabajo propio")
    trabajadores = rangos[1:]
    if sum(r["bloques"] for r in trabajadores) != math.ceil(n / lote):
        raise ValueError("los bloques de trabajadores no cubren N; no se suma el contador del maestro")
    if any(r["n_local"] < 0 or r["bloques"] < 0 or r["n_local"] > r["bloques"] * lote or
           (r["bloques"] == 0) != (r["n_local"] == 0) for r in trabajadores):
        raise ValueError("bloques y escenarios incoherentes por trabajador")
    nodos = len(set(hosts.values()))
    if (ambito == "cluster" and nodos < 2) or (ambito == "local" and nodos != 1):
        raise ValueError(f"{ambito}: número de PC observado incorrecto: {nodos}")
    if variante == "mpi_openmp_gpu" and not any(r["rango"] in gpu and r["n_local"] > 0 for r in trabajadores):
        raise ValueError("variante GPU sin trabajo GPU observado: no se acepta el fallback CPU como X8 GPU")
    if variante != "mpi_openmp_gpu" and gpu:
        raise ValueError("se detectó GPU en una variante CPU")
    return [{"rango": r["rango"], "bloques": r["bloques"], "n_local": r["n_local"],
             "host": hosts[r["rango"]], "tipo": "maestro" if r["rango"] == 0 else
             ("gpu" if r["rango"] in gpu else "cpu")} for r in rangos]


def verificar_hardware(stderr, rangos, exe, config):
    from _lanzador_x8 import sha256
    hardware = {}
    for linea in stderr.splitlines():
        if linea.startswith("[x8-hardware] "):
            datos = json.loads(linea.removeprefix("[x8-hardware] "))
            hardware[datos["rango"]] = datos
    if set(hardware) != {r["rango"] for r in rangos}:
        raise ValueError("faltan metadatos observados de algún rango")
    exe_sha, config_sha = sha256(exe), sha256(config)
    for r in rangos:
        h = hardware[r["rango"]]
        if (h["host"] != r["host"] or h["binario_sha256"] != exe_sha or h["config_sha256"] != config_sha or
                not h["cpu"] or int(h["nucleos_fisicos"]) < 1 or not h["ram_gb"]):
            raise ValueError("binario/configuración distintos entre PC o hardware incompleto")
    return hardware


def escribir(ruta, filas):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0]))
        w.writeheader()
        w.writerows(filas)


def graficar(ruta, destino):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    with ruta.open(encoding="utf-8", newline="") as f:
        filas = [r for r in csv.DictReader(f) if r["calentamiento"] == "0" and r["tipo"] != "maestro"]
    if not filas:
        raise ValueError("no hay mediciones de trabajadores para graficar")
    grupos, etiquetas, repeticiones = {}, {}, {}
    for r in filas:
        punto = (int(r["n"]), r["ambito"], r["variante"])
        trabajador = (r["host"], int(r["rango"]), r["tipo"])
        repeticiones.setdefault(punto, set()).add(r["repeticion"])
        grupos.setdefault(punto, {}).setdefault(trabajador, []).append(float(r["fraccion_bloques"]))
        etiquetas[trabajador] = f"{trabajador[0]} / rango {trabajador[1]} ({trabajador[2]})"
    puntos = list(grupos)
    fig, ejes = plt.subplots(2, 1, figsize=(max(10, len(puntos) * .5), 9), sharex=True)
    for ax, por_pc in zip(ejes, (False, True)):
        series = {}
        for i, punto in enumerate(puntos):
            for trabajador, valores in grupos[punto].items():
                clave = trabajador[0] if por_pc else etiquetas[trabajador]
                series.setdefault(clave, [0.] * len(puntos))[i] += sum(valores) / len(repeticiones[punto])
        fondo = [0.] * len(puntos)
        for etiqueta, valores in series.items():
            ax.bar(range(len(puntos)), valores, bottom=fondo, label=etiqueta)
            fondo = [x + y for x, y in zip(fondo, valores)]
        ax.set_ylim(0, 1.05)
        ax.set_ylabel("fracción de bloques WORK")
        ax.set_title("Por PC" if por_pc else "Por rango (media de repeticiones medidas)")
        ax.legend(fontsize=6, loc="upper left", bbox_to_anchor=(1, 1))
    ejes[-1].set_xticks(range(len(puntos)), [f"N={n:g}\n{a}\n{v}" for n, a, v in puntos], rotation=75, fontsize=6)
    fig.suptitle(f"X8 · fuente: {ruta.name}")
    fig.tight_layout()
    destino.mkdir(parents=True, exist_ok=True)
    for ext in ("svg", "png"):
        fig.savefig(destino / f"x8_fraccion_bloques.{ext}", dpi=180, bbox_inches="tight")
    plt.close(fig)


def main(argv=None):
    a = parser().parse_args(argv)
    estado_path = None
    try:
        puntos = plan(a)
        rangos_csv = a.salida.with_name(a.salida.stem + "_rangos.csv")
        if a.graficar:
            graficar(rangos_csv, a.figuras)
            return 0
        hosts = cb.leer_hostfile(a.hostfile)
        if not 2 <= len({h for h, _ in hosts}) <= 3:
            raise ValueError("el hostfile debe identificar dos o tres PC de T25")
        if a.dry_run:
            for n, ambito, variante in puntos:
                print(shlex.join(comando(a, n, ambito, variante)))
            print(f"{len(puntos)} puntos: un calentamiento + {a.repeticiones} repeticiones; "
                  "además una referencia serial por N. No se ejecutaron simuladores.")
            return 0
        if a.repeticiones != 5 or not a.host_en_reposo:
            raise ValueError("la campaña oficial requiere cinco repeticiones y --host-en-reposo en todas las PC")
        if min(n for n, _, _ in puntos) != 10_000_000 or max(n for n, _, _ in puntos) != 100_000_000:
            raise ValueError("la campaña oficial debe cubrir desde N=1e7 hasta N=1e8")
        for build in (a.build_dir, a.build_cpu_dir):
            if cb.leer_cache_cmake(build, "CMAKE_BUILD_TYPE") != "Release":
                raise ValueError(f"{build}: se requiere Release")
        for variante in VARIANTES:
            if not binario(a, variante).is_file():
                raise ValueError(f"falta {binario(a, variante)}; completar T54/T55 antes de medir X8")
        # T59 es referencia temporal solo en su N original. No se extrapolan tiempos a otro N.
        with a.t1_csv.open(encoding="utf-8", newline="") as f:
            t1, = list(csv.DictReader(f))
        commit = cb.commit_git()
        if (t1["commit"] != commit or t1["tipo_build"] != "Release" or int(t1["repeticiones"]) != 5 or
                int(t1["semilla"]) != a.semilla or int(t1["config_id"]) != a.config_id or
                t1["cpu"] != cb.info_cpu()[0]):
            raise ValueError("T1 no corresponde al commit, equipo, semilla o configuración actual; repetir T59")
        if any(not math.isfinite(float(t1[f"t{i}"])) or float(t1[f"t{i}"]) <= 0 for i in range(1, 6)):
            raise ValueError("T59 debe conservar cinco tiempos positivos y finitos")
        if not math.isclose(float(t1["media"]), statistics.mean(float(t1[f"t{i}"]) for i in range(1, 6)), rel_tol=1e-9):
            raise ValueError("la media T59 no coincide con sus cinco tiempos")
        if any(p.exists() for p in (a.salida, rangos_csv, a.salida.with_suffix(".log"), a.salida.with_suffix(".json"))):
            raise ValueError("ya hay salidas X8: elija otra --salida para conservar la campaña anterior")
        env = dict(os.environ, OMP_PROC_BIND="false", OMP_PLACES="cores", PP_COMMIT=commit, GIT_COMMIT=commit)
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            env.update(OMPI_ALLOW_RUN_AS_ROOT="1", OMPI_ALLOW_RUN_AS_ROOT_CONFIRM="1")
        a.salida.parent.mkdir(parents=True, exist_ok=True)
        filas, detalle, referencias = [], [], {}
        estado_path = a.salida.with_suffix(".json")
        estado = dict(estado="en_curso", puntos_previstos=len(puntos), puntos_completados=0, commit=commit)
        estado_path.write_text(json.dumps(estado, indent=2) + "\n", encoding="utf-8")
        with a.salida.with_suffix(".log").open("w", encoding="utf-8") as log:
            log.write(f"# T56 X8 commit={commit} host_en_reposo=declarado_por_operador\n")
            log.write(json.dumps({"cpu": cb.info_cpu(), "gpu": cb.info_gpu(), "ram_gb": cb.ram_gb(),
                                  "hostfile": a.hostfile.read_text(), "t1": t1}, ensure_ascii=False) + "\n")
            for n, ambito, variante in puntos:
                if n not in referencias:
                    cmd = [str((a.build_cpu_dir / 'src/backends/serial/pp_serial').resolve()),
                           "--config", str(a.config.resolve()), "--n", str(n), "--semilla", str(a.semilla),
                           "--config-id", str(a.config_id)]
                    ref, _, _ = correr(cmd, env, log, a.timeout)
                    referencias[n] = firma(ref, n)
                    if ref["commit"] != commit or (n == int(t1["n"]) and int(t1["k"]) != referencias[n][0]):
                        raise ValueError("referencia serial con commit o conteo distintos de T59")
                muestras, t_calentamiento, sobre_punto = [], None, 0
                for i in range(a.repeticiones + 1):
                    fila, out, err = correr(comando(a, n, ambito, variante), env, log, a.timeout)
                    if firma(fila, n) != referencias[n] or fila["commit"] != commit:
                        raise ValueError("falló equivalencia serial o commit del binario; consulte el log")
                    rangos = verificar_rangos(out, err, n, a.procesos, ambito, variante, a.lote)
                    hardware = verificar_hardware(err, rangos, binario(a, variante), a.config)
                    demanda, nodos_hw = {}, {}
                    for r in rangos:
                        host = r["host"]
                        nodos_hw[host] = hardware[r["rango"]]
                        # Maestro y GPU conservan un hilo de control; CPU usa --hilos.
                        demanda[host] = demanda.get(host, 0) + (a.hilos if
                            variante != "mpi" and r["tipo"] == "cpu" else 1)
                    sobre = int(any(demanda[h] > int(nodos_hw[h]["nucleos_fisicos"]) for h in demanda))
                    sobre_punto |= sobre
                    meta = dict(n=n, ambito=ambito, variante=variante, repeticion=i, calentamiento=int(i == 0),
                                commit=commit, fecha=datetime.datetime.now().astimezone().isoformat(timespec="seconds"))
                    total_bloques = sum(r["bloques"] for r in rangos if r["rango"] != 0)
                    for r in rangos:
                        detalle.append({**meta, **r, "cpu": hardware[r["rango"]]["cpu"],
                                        "nucleos_fisicos": hardware[r["rango"]]["nucleos_fisicos"],
                                        "ram_gb": hardware[r["rango"]]["ram_gb"], "gpu": hardware[r["rango"]]["gpu"],
                                        "binario_sha256": hardware[r["rango"]]["binario_sha256"],
                                        "sobresuscrito": sobre,
                                        "fraccion_bloques": r["bloques"] / total_bloques if r["rango"] else 0,
                                        "fraccion_escenarios": r["n_local"] / n})
                    if i:
                        muestras.append(float(fila["tiempo_s"]))
                    else:
                        t_calentamiento = float(fila["tiempo_s"])
                media = statistics.mean(muestras)
                registro = dict(n=n, ambito=ambito, variante=variante, procesos=a.procesos,
                    hilos=1 if variante == "mpi" else a.hilos, lote=a.lote, semilla=a.semilla, config_id=a.config_id,
                    config_sha256=hashlib.sha256(a.config.read_bytes()).hexdigest(),
                    commit=commit, cpu=cb.info_cpu()[0], gpu_local=cb.info_gpu(), host_local=socket.gethostname(),
                    hosts=";".join(sorted({r['host'] for r in rangos})), repeticiones=5, equivalente=1,
                    sobresuscrito=sobre_punto, hardware_nodos=json.dumps(nodos_hw, ensure_ascii=True, sort_keys=True),
                    host_en_reposo="declarado_por_operador", media=media, desviacion=statistics.stdev(muestras),
                    cv=statistics.stdev(muestras) / media,
                    speedup_t1=float(t1["media"]) / media if int(t1["n"]) == n else "",
                    nota_t1="Solo se calcula speedup si N coincide con T59", k=referencias[n][0],
                    t_calentamiento=t_calentamiento)
                registro.update({f"t{i}": t for i, t in enumerate(muestras, 1)})
                filas.append(registro)
                escribir(a.salida, filas)
                escribir(rangos_csv, detalle)
                estado["puntos_completados"] = len(filas)
                estado_path.write_text(json.dumps(estado, indent=2) + "\n", encoding="utf-8")
                print(f"{ambito} {variante} N={n} media={media:.4f}s CV={registro['cv']:.2%}", flush=True)
        graficar(rangos_csv, a.figuras)
        estado["estado"] = "completada"
        estado_path.write_text(json.dumps(estado, indent=2) + "\n", encoding="utf-8")
        return 0
    except (OSError, ValueError, KeyError, ImportError, subprocess.SubprocessError) as e:
        if estado_path is not None:
            estado.update(estado="error", error=str(e))
            estado_path.write_text(json.dumps(estado, indent=2) + "\n", encoding="utf-8")
        print(f"ERROR X8: {e}")
        return 1
