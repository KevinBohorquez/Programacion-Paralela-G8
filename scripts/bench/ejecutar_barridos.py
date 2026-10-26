#!/usr/bin/env python3
# T26,T30,T31 | Responsable: Miguel | Ejecución parametrizada de X1, X2 y X3.
"""Ejecutor parametrizable de los barridos X1 (escalabilidad fuerte), X2 (débil) y X3 (carga).

  x1  N fijo; recursos 1/2/4/8/16 (hilos en openmp, procesos en MPI, procesos x hilos en híbrido).
  x2  N = n_base x recursos (la carga por recurso es constante).
  x3  recursos fijos; N recorre --cargas.

El híbrido expande cada presupuesto en factorizaciones p x h con p*h = presupuesto (16 -> 2x8, 4x4,
8x2); --factorizaciones las restringe. Cada punto: 1 calentamiento (no cuenta) + --reps repeticiones.
Antes de cada N nuevo corre pp_serial una vez como referencia (--referencia serial): todas las
corridas con el mismo N y semilla deben dar el mismo k, n e histograma que el secuencial; si no,
la fila queda con equivalente=0 y el script termina con código 2 (después de escribir el CSV).

Se ejecuta DENTRO del contenedor pp-g8 con un build Release (incluido -DPP_BUILD_MPI=ON).
Los tiempos son los `tiempo_s` internos del simulador (sin el arranque de mpirun).
El CSV propio (results/bench/<experimento>.csv) guarda sus metadatos: commit (GIT_COMMIT o git),
CPU, núcleos, nproc, RAM, GPU (nvidia-smi), red, afinidad, procesos, hilos, nodos y fecha.
Del CSV del simulador solo se leen columnas por nombre: tolera columnas añadidas.

Ejemplos (en el contenedor, tras compilar en build/docker):
  python3 scripts/bench/ejecutar_barridos.py --experimento x1 --backend openmp --recursos 1,2 --n 2e5 --reps 1 --dry-run
  python3 scripts/bench/ejecutar_barridos.py --experimento x1 --backend serial,openmp,mpi_estatico,mpi_dinamico,hibrido \\
      --build-dir build/docker --n 2e7
  python3 scripts/bench/ejecutar_barridos.py --experimento x2 --backend mpi_dinamico --n 2.5e6 --referencia primera
  python3 scripts/bench/ejecutar_barridos.py --experimento x3 --backend hibrido --recursos 16 --cargas 1e6,5e6,2e7
"""
import argparse
import csv
import datetime
import os
import platform
import shlex
import socket
import statistics
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _comun_bench as cb  # noqa: E402

RAIZ = cb.RAIZ
BACKENDS = ("serial", "openmp", "mpi_estatico", "mpi_dinamico", "hibrido")
EXES = {
    "serial": "src/backends/serial/pp_serial",
    "openmp": "src/backends/openmp/pp_openmp",
    "mpi_estatico": "src/backends/mpi/pp_mpi_estatico",
    "mpi_dinamico": "src/backends/mpi/pp_mpi_dinamico",
    "hibrido": "src/backends/hybrid/pp_hibrido",
}
CON_MPI = ("mpi_estatico", "mpi_dinamico", "hibrido")
CON_HILOS = ("openmp", "hibrido")
US_T1 = 2.99  # µs por escenario de la línea base T14 (results/bench/secuencial_t1.csv)


@dataclass(frozen=True)
class Punto:
    experimento: str
    backend: str
    n: int
    procesos: int
    hilos: int

    @property
    def recursos(self):
        return self.procesos * self.hilos


@dataclass
class Opciones:
    build_dir: str
    config: str
    semilla: int
    config_id: int
    schedule: str
    lote: int
    hosts: list = field(default_factory=list)  # [(host, slots)] de --hosts o leídos del --hostfile
    hostfile: str = ""
    red_tcp: str = ""
    bind_mpi: str = ""
    omp_bind: str = "close"
    omp_places: str = "cores"
    mpirun_extra: list = field(default_factory=list)
    nucleos: int = 1  # núcleos físicos totales (para la marca de sobresuscripción)
    slots: int = 1    # slots de mpirun (para --oversubscribe)


# ---------- plan ----------
def factorizaciones(presupuesto):
    """Pares (procesos, hilos) con producto = presupuesto; sin los casos puros si hay mixtos."""
    pares = [(p, presupuesto // p) for p in range(1, presupuesto + 1) if presupuesto % p == 0]
    mixtos = [(p, h) for p, h in pares if p > 1 and h > 1]
    return mixtos or pares


def parsear_factorizaciones(texto):
    if not texto or not texto.strip():
        return None
    pares = []
    for parte in texto.split(","):
        p, x, h = parte.strip().lower().partition("x")
        if not x or not p.isdigit() or not h.isdigit():
            raise ValueError(f"factorización inválida '{parte}': use PxH, p. ej. 2x8")
        pares.append((int(p), int(h)))
    return pares


def _pares_backend(backend, r, facts):
    if backend == "serial":
        return [(1, 1)] if r == 1 else []
    if backend == "openmp":
        return [(1, r)]
    if backend in ("mpi_estatico", "mpi_dinamico"):
        return [(r, 1)]
    if facts is not None:
        return [(p, h) for p, h in facts if p * h == r]
    return factorizaciones(r)


def generar_plan(experimento, backends, recursos, n, cargas=None, factorizaciones=None):
    """Lista ordenada de Puntos. El secuencial va primero (sirve de referencia) y solo con 1 recurso."""
    for b in backends:
        if b not in BACKENDS:
            raise ValueError(f"backend desconocido '{b}'; válidos: {', '.join(BACKENDS)}")
    if experimento not in ("x1", "x2", "x3"):
        raise ValueError("experimento debe ser x1, x2 o x3")
    if experimento == "x3" and not cargas:
        raise ValueError("x3 necesita --cargas")
    orden = sorted(dict.fromkeys(backends), key=lambda b: b != "serial")
    plan = []
    for b in orden:
        rs = [1] if b == "serial" else recursos
        for r in rs:
            ns = cargas if experimento == "x3" else [n * r if experimento == "x2" else n]
            for carga in ns:
                for p, h in _pares_backend(b, r, factorizaciones):
                    plan.append(Punto(experimento, b, int(carga), p, h))
    return plan


def sobresuscrito(punto, nucleos):
    return punto.recursos > nucleos


def estimar_segundos(plan, repeticiones, us_por_escenario, nucleos, calentamiento=True):
    """Duración ideal (speedup lineal hasta `nucleos`) de todo el plan, sin referencias."""
    corridas = repeticiones + (1 if calentamiento else 0)
    return sum(corridas * p.n * us_por_escenario / 1e6 / max(1, min(p.recursos, nucleos)) for p in plan)


# ---------- comandos ----------
def comando(punto, o):
    """argv de una corrida (sin --salida, que añade el ejecutor)."""
    exe = f"{o.build_dir}/{EXES[punto.backend]}"
    args = ["--config", o.config, "--n", str(punto.n), "--semilla", str(o.semilla),
            "--config-id", str(o.config_id), "--silencioso"]
    if punto.backend in CON_HILOS:
        args += ["--hilos", str(punto.hilos), "--schedule", o.schedule]
    if punto.backend == "mpi_dinamico" and o.lote:
        args += ["--lote", str(o.lote)]
    if punto.backend not in CON_MPI:
        return [exe, *args]
    cmd = ["mpirun", "-np", str(punto.procesos)]
    if punto.procesos > o.slots:
        cmd.append("--oversubscribe")
    if punto.backend == "hibrido":
        # Sin esto Open MPI ancla cada rango a un núcleo y sus hilos se apiñan (1.90 vs 7.13 de speedup).
        cmd += ["--bind-to", o.bind_mpi or "none", "-x", "OMP_PROC_BIND", "-x", "OMP_PLACES"]
    elif o.bind_mpi:
        cmd += ["--bind-to", o.bind_mpi]
    if o.hostfile:
        cmd += ["--hostfile", o.hostfile, "--map-by", "slot"]
    elif o.hosts:
        cmd += ["--host", ",".join(f"{h}:{s}" for h, s in o.hosts), "--map-by", "slot"]
    if o.red_tcp:
        cmd += ["--mca", "btl", "tcp,self", "--mca", "btl_tcp_if_include", o.red_tcp,
                "--mca", "oob_tcp_if_include", o.red_tcp]
    return cmd + list(o.mpirun_extra) + [exe, *args]


def afinidad(punto, o):
    if o is None or punto.backend == "serial":
        return "-"
    partes = []
    if punto.backend in CON_HILOS:
        partes.append(f"OMP_PROC_BIND={o.omp_bind};OMP_PLACES={o.omp_places}")
    if punto.backend in CON_MPI:
        partes.append(f"mpirun_bind={o.bind_mpi or ('none' if punto.backend == 'hibrido' else 'por_defecto')}")
    return ";".join(partes)


def entorno_omp(o):
    e = dict(os.environ, OMP_PROC_BIND=o.omp_bind, OMP_PLACES=o.omp_places)
    e.pop("OMP_NUM_THREADS", None)
    e.pop("OMP_SCHEDULE", None)
    return e


def crear_ejecutor(o, timeout=None, log=print):
    """Ejecutor real: punto -> (fila del CSV del simulador, lista [verif] por rango)."""
    entorno = entorno_omp(o)

    def correr(punto):
        with tempfile.TemporaryDirectory() as d:
            salida = Path(d) / "r.csv"
            cmd = comando(punto, o) + ["--salida", str(salida)]
            r = subprocess.run(cmd, capture_output=True, text=True, env=entorno, timeout=timeout)
            if r.returncode != 0 or not salida.exists():
                cola = "\n".join((r.stdout + r.stderr).splitlines()[-15:])
                raise RuntimeError(f"falló ({r.returncode}): {shlex.join(cmd)}\n{cola}")
            return cb.leer_fila_simulador(salida), cb.parsear_verif(r.stdout)

    return correr


# ---------- ejecución ----------
def _firma(fila):
    return (fila.get("k"), fila.get("n"), fila.get("hist512"))


def ejecutar_plan(plan, correr, repeticiones, nucleos, meta, referencia="serial", calentamiento=True,
                  opciones=None, log=print):
    """Mide cada punto y devuelve las filas del CSV. `correr(punto) -> (fila_sim, verif)`."""
    refs, filas = {}, []
    hosts = opciones.hosts if opciones else []
    for punto in plan:
        if referencia == "serial" and punto.n not in refs and punto.backend != "serial":
            fila_ref, _ = correr(Punto("referencia", "serial", punto.n, 1, 1))
            refs[punto.n] = _firma(fila_ref)
        cal = correr(punto)[0] if calentamiento else None
        reps = [correr(punto) for _ in range(repeticiones)]
        sims = [s for s, _ in reps]
        if referencia != "ninguna" and punto.n not in refs:
            refs[punto.n] = _firma(sims[0])
        if referencia == "ninguna":
            equivalente = ""
        else:
            equivalente = int(all(_firma(s) == refs[punto.n] for s in sims + ([cal] if cal else [])))
        tiempos = [float(s["tiempo_s"]) for s in sims]
        verif = reps[-1][1]
        trabajos = [v.get("n_local", 0) for v in verif]
        bloques = [v["bloques"] for v in verif if "bloques" in v]
        asignacion = cb.asignar_rangos(hosts, punto.procesos) if hosts else []
        fila = dict(
            experimento=punto.experimento, backend=punto.backend, n=punto.n, procesos=punto.procesos,
            hilos=punto.hilos, recursos=punto.recursos, nodos=len(set(asignacion)) if asignacion else 1,
            hosts=";".join(dict.fromkeys(asignacion)) if asignacion else socket.gethostname(),
            schedule=sims[0].get("schedule") or "-",
            lote=(opciones.lote or "por_defecto") if opciones and punto.backend == "mpi_dinamico" else "-",
            afinidad=afinidad(punto, opciones), sobresuscrito=int(sobresuscrito(punto, nucleos)),
            nucleos_ref=nucleos, repeticiones=repeticiones,
            t_calentamiento=cal["tiempo_s"] if cal else "",
            tiempos=";".join(str(t) for t in tiempos), media=statistics.mean(tiempos),
            desviacion=statistics.stdev(tiempos) if len(tiempos) > 1 else 0.0, minimo=min(tiempos),
            k=sims[0].get("k"), k_ref=refs[punto.n][0] if punto.n in refs else "", equivalente=equivalente,
            trabajo_rangos=";".join(map(str, trabajos)), bloques_rangos=";".join(map(str, bloques)),
            desbalance=cb.desbalance(trabajos),
        )
        fila.update(meta)
        fila["commit_binario"] = sims[0].get("commit", "")
        fila["fecha"] = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
        filas.append(fila)
        marca = " [SOBRESUSCRITO]" if fila["sobresuscrito"] else ""
        eq = {1: "ok", 0: "FALLA", "": "sin_ref"}[equivalente]
        log(f"{punto.backend:12s} n={punto.n:<11d} {punto.procesos:>2d}x{punto.hilos:<2d} "
            f"media={fila['media']:.4f}s sd={fila['desviacion']:.4f}s k={fila['k']} V1={eq}{marca}")
    return filas


def escribir_csv(filas, ruta, anexar=False):
    """Escribe las filas; con anexar une las columnas con las del archivo existente."""
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    previas, campos = [], []
    if anexar and ruta.exists():
        with open(ruta, newline="") as f:
            lector = csv.DictReader(f)
            campos = list(lector.fieldnames or [])
            previas = list(lector)
    for fila in filas:
        for k in fila:
            if k not in campos:
                campos.append(k)
    with open(ruta, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=campos, restval="")
        w.writeheader()
        w.writerows(previas + filas)


def capturar_meta(o, args):
    cpu, fisicos, logicos = cb.info_cpu()
    return dict(
        semilla=o.semilla, config_id=o.config_id, config=o.config, config_sha=cb.sha_archivo(o.config),
        commit=cb.commit_git(), cpu=cpu, nucleos_fisicos=fisicos, nucleos_logicos=logicos, nproc=cb.nproc(),
        ram_gb=cb.ram_gb(), gpu=cb.info_gpu(), red=cb.info_red(), hostname=socket.gethostname(),
        tipo_build=cb.leer_cache_cmake(o.build_dir, "CMAKE_BUILD_TYPE") or "desconocido",
        compilador=cb.leer_cache_cmake(o.build_dir, "CMAKE_CXX_COMPILER") or "desconocido",
        so=platform.platform(), comando=shlex.join(sys.argv),
    )


# ---------- CLI ----------
def _enteros(texto):
    return [int(float(x)) for x in texto.split(",") if x.strip()] if texto else []


DEF_N = {"x1": 20_000_000, "x2": 2_500_000, "x3": 0}
DEF_RECURSOS = {"x1": "1,2,4,8,16", "x2": "1,2,4,8,16", "x3": "8"}


def construir_parser():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--experimento", required=True, choices=["x1", "x2", "x3"])
    ap.add_argument("--backend", required=True, help=f"lista separada por comas de: {','.join(BACKENDS)}")
    ap.add_argument("--recursos", help="presupuestos (hilos/procesos/p*h). Def.: 1,2,4,8,16 (x3: 8)")
    ap.add_argument("--n", type=float, help="x1: N fijo (def. 2e7); x2: N por recurso (def. 2.5e6)")
    ap.add_argument("--cargas", help="x3: lista de N, p. ej. 1e6,5e6,2e7")
    ap.add_argument("--factorizaciones", default="", help="híbrido: PxH separados por comas (def. todos los mixtos)")
    ap.add_argument("--reps", type=int, default=5)
    ap.add_argument("--sin-calentamiento", action="store_true")
    ap.add_argument("--referencia", default="serial", choices=["serial", "primera", "ninguna"],
                    help="serial: pp_serial por cada N; primera: el primer punto de cada N; ninguna")
    ap.add_argument("--build-dir", default=str(RAIZ / "build" / "docker"))
    ap.add_argument("--config", default=str(RAIZ / "config" / "sintetico.yaml"))
    ap.add_argument("--semilla", type=int, default=20261015)
    ap.add_argument("--config-id", type=int, default=0)
    ap.add_argument("--schedule", default="static", help="OpenMP/híbrido")
    ap.add_argument("--lote", type=int, default=0, help="mpi_dinamico: tamaño de bloque (0 = el del binario)")
    ap.add_argument("--hosts", default="", help="mpirun --host, p. ej. nodo1:8,nodo2:8")
    ap.add_argument("--hostfile", default="")
    ap.add_argument("--red-tcp", default="", help="interfaz o CIDR para btl/oob tcp entre contenedores (eth0)")
    ap.add_argument("--bind-mpi", default="", help="mpirun --bind-to (híbrido: none por defecto)")
    ap.add_argument("--omp-bind", default="close")
    ap.add_argument("--omp-places", default="cores")
    ap.add_argument("--mpirun-extra", default="", help="opciones extra de mpirun (una cadena)")
    ap.add_argument("--nucleos", type=int, default=0,
                    help="núcleos físicos totales para la marca de sobresuscripción (def. locales x nodos)")
    ap.add_argument("--salida", default="", help="def. results/bench/<experimento>.csv")
    ap.add_argument("--log", default="", help="def. la salida con extensión .log")
    ap.add_argument("--anexar", action="store_true", help="agrega filas a un CSV existente")
    ap.add_argument("--timeout", type=float, default=None, help="segundos por corrida")
    ap.add_argument("--us-por-escenario", type=float, default=US_T1, help="para la estimación del --dry-run")
    ap.add_argument("--dry-run", action="store_true", help="imprime el plan, los comandos y la duración estimada")
    ap.add_argument("--permitir-debug", action="store_true")
    return ap


def opciones_desde_args(a):
    hosts = cb.parsear_hosts(a.hosts) if a.hosts else (cb.leer_hostfile(a.hostfile) if a.hostfile else [])
    _, fisicos, logicos = cb.info_cpu()
    nodos = max(1, len(hosts))
    return Opciones(
        build_dir=str(Path(a.build_dir).resolve().as_posix()), config=str(Path(a.config).resolve().as_posix()),
        semilla=a.semilla, config_id=a.config_id, schedule=a.schedule, lote=a.lote,
        hosts=hosts, hostfile=a.hostfile, red_tcp=a.red_tcp,
        bind_mpi=a.bind_mpi, omp_bind=a.omp_bind, omp_places=a.omp_places,
        mpirun_extra=shlex.split(a.mpirun_extra), nucleos=a.nucleos or fisicos * nodos,
        slots=sum(s for _, s in hosts) if hosts else logicos,
    )


def preparar(a):
    """Plan y opciones a partir de los argumentos (también lo usa comparar_mpi_heterogeneo.py)."""
    backends = [b.strip() for b in a.backend.split(",") if b.strip()]
    recursos = _enteros(a.recursos or DEF_RECURSOS[a.experimento])
    n = int(a.n) if a.n else DEF_N[a.experimento]
    plan = generar_plan(a.experimento, backends, recursos, n, cargas=_enteros(a.cargas),
                        factorizaciones=parsear_factorizaciones(a.factorizaciones))
    return plan, opciones_desde_args(a)


def comprobar_build(o, permitir_debug):
    faltan = sorted({EXES[b] for b in EXES if not Path(o.build_dir, EXES[b]).exists()})
    tipo = cb.leer_cache_cmake(o.build_dir, "CMAKE_BUILD_TYPE") or "desconocido"
    if tipo in ("Debug", "desconocido", "") and not permitir_debug:
        sys.exit(f"el build '{o.build_dir}' es '{tipo}': recompile con -DCMAKE_BUILD_TYPE=Release.")
    return faltan


def imprimir_plan(plan, o, a):
    reps = a.reps
    print(f"# plan {a.experimento}: {len(plan)} puntos x ({0 if a.sin_calentamiento else 1} calentamiento + {reps} reps)")
    for i, p in enumerate(plan, 1):
        est = estimar_segundos([p], reps, a.us_por_escenario, o.nucleos, not a.sin_calentamiento)
        marca = " [SOBRESUSCRITO]" if sobresuscrito(p, o.nucleos) else ""
        print(f"{i:3d} {p.backend:12s} n={p.n:<11d} {p.procesos}x{p.hilos} ~{est:8.1f}s{marca}\n"
              f"    {shlex.join(comando(p, o))}")
    total = estimar_segundos(plan, reps, a.us_por_escenario, o.nucleos, not a.sin_calentamiento)
    ns = {p.n for p in plan if p.backend != "serial"} - (
        {p.n for p in plan if p.backend == "serial"} if a.referencia == "serial" else set())
    ref = sum(ns) * a.us_por_escenario / 1e6 if a.referencia == "serial" else 0.0
    print(f"# estimación ideal: {total / 60:.1f} min de puntos + {ref / 60:.1f} min de referencias serial "
          f"({a.us_por_escenario} µs/escenario, speedup lineal hasta {o.nucleos} núcleos)")


def main(argv=None):
    a = construir_parser().parse_args(argv)
    try:
        plan, o = preparar(a)
    except ValueError as e:
        sys.exit(str(e))
    if a.dry_run:
        imprimir_plan(plan, o, a)
        return 0
    faltan = comprobar_build(o, a.permitir_debug)
    usados = {EXES[p.backend] for p in plan} | ({EXES["serial"]} if a.referencia == "serial" else set())
    if usados & set(faltan):
        sys.exit(f"faltan binarios en {o.build_dir}: {sorted(usados & set(faltan))} "
                 "(compile con -DPP_BUILD_MPI=ON)")
    salida = Path(a.salida or RAIZ / "results" / "bench" / f"{a.experimento}.csv")
    ruta_log = Path(a.log or salida.with_suffix(".log"))
    ruta_log.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta_log, "a", encoding="utf-8") as flog:
        def log(msg):
            linea = f"{datetime.datetime.now().isoformat(timespec='seconds')} {msg}"
            print(linea, flush=True)
            flog.write(linea + "\n")
            flog.flush()

        meta = capturar_meta(o, a)
        log(f"inicio {meta['comando']} | commit={meta['commit']} cpu={meta['cpu']} nucleos={o.nucleos} "
            f"gpu={meta['gpu'] or '-'} red={meta['red']}")
        try:
            filas = ejecutar_plan(plan, crear_ejecutor(o, a.timeout), a.reps, o.nucleos, meta,
                                  referencia=a.referencia, calentamiento=not a.sin_calentamiento,
                                  opciones=o, log=log)
        except (RuntimeError, subprocess.TimeoutExpired) as e:
            log(f"ERROR {e}")
            return 1
        escribir_csv(filas, salida, anexar=a.anexar)
        log(f"escrito {salida} ({len(filas)} filas)")
        if any(f["equivalente"] == 0 for f in filas):
            log("V1 FALLÓ: hay corridas con k/histograma distintos de la referencia; no use este CSV.")
            return 2
        if any(f["sobresuscrito"] for f in filas):
            log(f"AVISO: puntos con recursos > {o.nucleos} núcleos físicos: se analizan aparte.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
