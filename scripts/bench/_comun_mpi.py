#!/usr/bin/env python3
# T21,T27 | Responsable: Ashley (T21) y Lita (T27) | Piezas comunes de medir_mpi.py y medir_hibrido.py.
"""Utilidades compartidas por los barridos MPI (T21) e híbrido (T27).

Las funciones puras (lectura de las líneas `[verif]`, speedup, eficiencia, T1, V1, comando mpirun)
se prueban en tests/unit/test_medir_mpi.py. Los datos de hardware y el commit se reutilizan de
medir_openmp.py para que los tres barridos registren los mismos metadatos.
"""
import csv
import os
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from medir_openmp import commit_git, info_cpu, leer_cache, ram_gb, version_compilador  # noqa: E402,F401

RAIZ = Path(__file__).resolve().parents[2]
T1_POR_DEFECTO = RAIZ / "results" / "bench" / "secuencial_t1.csv"
NOTA_E2 = "E2: el rango 0 es maestro y no simula; computan procesos-1 rangos"

_PAR = re.compile(r"(\w+)=(\S+)")


# ---------- partes puras ----------
def lista_enteros(texto):
    """'2,4,8' -> [2, 4, 8]; rechaza valores < 1."""
    valores = [int(x) for x in texto.split(",") if x.strip()]
    if not valores or any(v < 1 for v in valores):
        raise ValueError(f"lista inválida: {texto!r} (enteros >= 1 separados por comas)")
    return valores


def _entero(d, clave):
    return int(d[clave]) if clave in d else None


def parse_verif(texto):
    """Lee las líneas `[verif]` que el rango 0 imprime (src/backends/mpi/comun.cpp)."""
    v = {"backend": None, "procesos": None, "nivel_hilos": None, "rangos": [], "suma_n": None,
         "suma_n_rangos": None, "k": None, "estado": None, "v1": None, "tiempo_s": None}
    for linea in texto.splitlines():
        if not linea.startswith("[verif]"):
            continue
        d = dict(_PAR.findall(linea))
        if "rango" in d:
            v["rangos"].append({"rango": int(d["rango"]), "n_local": _entero(d, "n_local"),
                                "bloques": _entero(d, "bloques"), "inicio": _entero(d, "inicio"),
                                "fin": _entero(d, "fin"), "hilos": _entero(d, "hilos")})
        elif "estado" in d:
            v.update(suma_n=int(d["suma_n"]), suma_n_rangos=int(d["suma_n_rangos"]), k=int(d["k"]),
                     estado=d["estado"])
        elif "v1_referencia" in d:
            v["v1"] = d["v1_referencia"]
        elif "tiempo_s" in d:
            v["tiempo_s"] = float(d["tiempo_s"])
        elif "backend" in d and v["backend"] is None:
            v.update(backend=d["backend"], procesos=int(d["procesos"]), nivel_hilos=d.get("nivel_hilos_mpi"))
    return v


def reparto_texto(rangos):
    """Escenarios simulados por rango: 'rango:n_local;...'."""
    return ";".join(f"{r['rango']}:{r['n_local']}" for r in rangos)


def bloques_texto(rangos):
    """Bloques por rango (solo E2); vacío si el esquema no informa bloques."""
    if not rangos or any(r["bloques"] is None for r in rangos):
        return ""
    return ";".join(f"{r['rango']}:{r['bloques']}" for r in rangos)


def procesos_de_computo(esquema, procesos):
    """En E2 el rango 0 solo reparte bloques; con un único proceso simula todo."""
    return procesos - 1 if esquema == "mpi_dinamico" and procesos > 1 else procesos


def resumir(tiempos):
    return statistics.mean(tiempos), (statistics.stdev(tiempos) if len(tiempos) > 1 else 0.0)


def speedup(t_serial, t):
    return t_serial / t if t_serial and t else ""


def eficiencia(t_serial, t, recursos):
    s = speedup(t_serial, t)
    return s / recursos if s != "" and recursos else ""


def sobresuscrito(recursos, fisicos):
    return int(recursos > fisicos)


def equivalente(fila, ref):
    """V1: k, n e histograma idénticos a la referencia secuencial."""
    return all(fila[c] == ref[c] for c in ("k", "n", "hist512"))


def comando_mpi(mpiexec, procesos, exe, args, bind_to="core", oversubscribe=False):
    cmd = [str(mpiexec), "-np", str(procesos), "--bind-to", bind_to]
    if oversubscribe:
        cmd.append("--oversubscribe")
    return cmd + [str(exe), *map(str, args)]


def leer_t1(ruta, n, semilla, config_id):
    """Media y k del secuencial (T14) medido con la misma carga; None si no hay fila que coincida."""
    try:
        with open(ruta, newline="", encoding="utf-8") as f:
            for fila in csv.DictReader(f):
                if (int(fila["n"]), int(fila["semilla"]), int(fila["config_id"])) == (n, semilla, config_id):
                    return {"media": float(fila["media"]), "k": fila["k"], "dias": fila.get("dias", "")}
    except (OSError, KeyError, ValueError):
        pass
    return None


# ---------- ejecución ----------
def mpiexec_de(build_dir):
    return leer_cache(build_dir, "MPIEXEC_EXECUTABLE") or shutil.which("mpirun") or "mpirun"


def entorno_mpi(**omp):
    """Entorno para mpirun; como root (contenedor) Open MPI exige permitirlo explícitamente."""
    env = dict(os.environ)
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        env.setdefault("OMPI_ALLOW_RUN_AS_ROOT", "1")
        env.setdefault("OMPI_ALLOW_RUN_AS_ROOT_CONFIRM", "1")
    env.pop("OMP_NUM_THREADS", None)
    env.pop("OMP_SCHEDULE", None)
    env.update({k: str(v) for k, v in omp.items()})
    return env


def correr(cmd, entorno, timeout=None):
    """Ejecuta un binario del simulador (directo o bajo mpirun) y devuelve (fila CSV, [verif])."""
    with tempfile.TemporaryDirectory() as d:
        salida = Path(d) / "r.csv"
        completo = [*map(str, cmd), "--silencioso", "--salida", str(salida)]
        try:
            r = subprocess.run(completo, capture_output=True, text=True, env=entorno, timeout=timeout)
        except subprocess.TimeoutExpired:
            sys.exit(f"tiempo agotado ({timeout} s): {' '.join(completo)}")
        if r.returncode != 0 or not salida.exists():
            sys.exit(f"falló ({r.returncode}) {' '.join(completo)}\n{r.stdout[-2000:]}\n{r.stderr[-2000:]}")
        with open(salida, newline="") as f:
            return next(csv.DictReader(f)), parse_verif(r.stdout)


def medir_punto(cmd, entorno, repeticiones, timeout=None):
    """Calentamiento (repetición 0, no cuenta) y `repeticiones` medidas del mismo comando."""
    cal = correr([*cmd, "--calentamiento"], entorno, timeout)
    reps = [correr([*cmd, "--repeticion", str(i)], entorno, timeout) for i in range(1, repeticiones + 1)]
    return cal, reps


def referencia_serial(serial, comunes, entorno, t1_csv, n, semilla, config_id, repeticiones, forzar=False):
    """Referencia V1 y tiempo T1.

    Corre pp_serial una vez para obtener k, n e histograma (V1 exige el histograma, que T14 no guarda).
    T1 se toma de `t1_csv` si coincide en N, semilla, config_id, días y k; si no (o con `forzar`),
    se mide el secuencial con el mismo protocolo (calentamiento + repeticiones).
    Devuelve (fila_ref, t_serial, fuente_t1, filas_serial_medidas).
    """
    ref, _ = correr([serial, *comunes], entorno)
    t1 = None if forzar else leer_t1(t1_csv, n, semilla, config_id)
    if t1 and t1["k"] == ref["k"] and (not t1["dias"] or t1["dias"] == ref["dias"]):
        return ref, t1["media"], str(t1_csv), []
    if t1:
        print(f"AVISO: {t1_csv} no coincide con el secuencial actual (k o días); se mide T1 de nuevo.")
    cal, reps = medir_punto([serial, *comunes], entorno, repeticiones)
    media, _ = resumir([float(r["tiempo_s"]) for r, _ in reps])
    return ref, media, "medido_en_este_barrido", [cal] + reps


def escribir_csv(ruta, filas):
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    campos = []
    for f in filas:
        campos += [c for c in f if c not in campos]
    with open(ruta, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=campos)
        w.writeheader()
        w.writerows(filas)
    print(f"escrito {ruta}")
