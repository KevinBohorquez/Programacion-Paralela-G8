#!/usr/bin/env python3
# T26,T32 | Responsable: Miguel | Utilidades compartidas por ejecutar_barridos.py y comparar_mpi_heterogeneo.py.
"""Captura de metadatos (CPU, GPU, red, commit), lectura robusta del CSV del simulador,
interpretación de las líneas [verif] de los backends MPI y cálculos de reparto por rango/nodo.

Todo lo que toca el sistema devuelve un valor por defecto si la herramienta no existe
(nvidia-smi, lscpu, ip, git): el ejecutor no debe fallar por falta de metadatos.
"""
import csv
import hashlib
import os
import platform
import re
import shutil
import socket
import subprocess
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]


def _salida(cmd, timeout=10):
    """stdout de `cmd` o "" si no existe o falla."""
    if shutil.which(cmd[0]) is None:
        return ""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return ""
    return r.stdout if r.returncode == 0 else ""


# ---------- hardware y entorno ----------
def info_cpu():
    """(modelo, núcleos físicos, CPU lógicas visibles). Lee lscpu y /proc/cpuinfo."""
    modelo, pares, logicos, fis = "", set(), 0, "0"
    for linea in _salida(["lscpu"]).splitlines():
        if linea.startswith("Model name:"):
            modelo = linea.split(":", 1)[1].strip()
            break
    try:
        with open("/proc/cpuinfo") as f:
            for linea in f:
                if ":" not in linea:
                    continue
                k, v = (s.strip() for s in linea.split(":", 1))
                if k == "model name" and not modelo:
                    modelo = v
                elif k == "processor":
                    logicos += 1
                elif k == "physical id":
                    fis = v
                elif k == "core id":
                    pares.add((fis, v))
    except OSError:
        pass
    logicos = logicos or os.cpu_count() or 0
    return modelo or platform.processor() or "desconocido", (len(pares) or logicos), logicos


def nproc():
    """CPU utilizables por este proceso (respeta cpuset/afinidad del contenedor)."""
    try:
        return len(os.sched_getaffinity(0))
    except (AttributeError, OSError):
        return os.cpu_count() or 0


def info_gpu():
    """Nombres de GPU NVIDIA separados por ';', o "" si no hay nvidia-smi."""
    txt = _salida(["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader"])
    return ";".join(l.strip().replace(",", " driver") for l in txt.splitlines() if l.strip())


def info_red():
    """Resumen 'iface=ip/prefijo;...' sin lo. Cae a la IP del hostname si no hay `ip`."""
    partes = []
    for linea in _salida(["ip", "-brief", "-4", "addr"]).splitlines():
        campos = linea.split()
        if len(campos) >= 3 and campos[0] != "lo":
            partes.append(f"{campos[0].split('@')[0]}={campos[2]}")
    if not partes:
        try:
            partes.append(f"ip={socket.gethostbyname(socket.gethostname())}")
        except OSError:
            pass
    return ";".join(partes)


def ram_gb():
    try:
        with open("/proc/meminfo") as f:
            for linea in f:
                if linea.startswith("MemTotal"):
                    return round(int(linea.split()[1]) / 1024 / 1024, 1)
    except OSError:
        pass
    return ""


def commit_git(raiz=RAIZ):
    """GIT_COMMIT del entorno (lo pasa el anfitrión) o `git rev-parse`; marca cambios sin commit."""
    if os.environ.get("GIT_COMMIT"):
        return os.environ["GIT_COMMIT"]
    c = _salida(["git", "-C", str(raiz), "rev-parse", "--short=12", "HEAD"]).strip()
    if not c:
        return "desconocido"
    sucio = _salida(["git", "-C", str(raiz), "status", "--porcelain", "--untracked-files=no"]).strip()
    return c + ("+cambios_sin_commit" if sucio else "")


def leer_cache_cmake(build_dir, clave):
    try:
        with open(Path(build_dir) / "CMakeCache.txt") as f:
            for linea in f:
                if linea.startswith(clave + ":"):
                    return linea.split("=", 1)[1].strip()
    except OSError:
        pass
    return ""


def sha_archivo(ruta):
    try:
        return hashlib.sha1(Path(ruta).read_bytes()).hexdigest()[:12]
    except OSError:
        return "sin_archivo"


# ---------- salida del simulador ----------
def leer_fila_simulador(ruta):
    """Última fila del CSV del simulador como dict por nombre de columna.

    Tolera columnas añadidas o reordenadas: solo se usan por nombre (tiempo_s, k, n, hist512...).
    """
    with open(ruta, newline="") as f:
        filas = list(csv.DictReader(f))
    if not filas:
        raise ValueError(f"{ruta}: CSV del simulador vacío")
    return filas[-1]


_PAR = re.compile(r"(\w+)=(\S+)")


def parsear_verif(texto):
    """Líneas '[verif] rango=r ... n_local=x' -> lista ordenada por rango de dicts con enteros.

    Ignora las demás líneas [verif]; devuelve [] para backends sin esas líneas (serial, openmp).
    """
    rangos = {}
    for linea in texto.splitlines():
        if not linea.startswith("[verif] rango="):
            continue
        d = {}
        for k, v in _PAR.findall(linea):
            d[k] = int(v) if v.isdigit() else v
        rangos[d["rango"]] = d
    return [rangos[r] for r in sorted(rangos)]


# ---------- reparto por rango y por nodo ----------
def parsear_hosts(texto):
    """'nodo1:2,nodo2:4' -> [('nodo1', 2), ('nodo2', 4)]; sin ':' vale 1 slot."""
    hosts = []
    for parte in filter(None, (p.strip() for p in (texto or "").split(","))):
        nombre, _, slots = parte.partition(":")
        hosts.append((nombre, int(slots) if slots else 1))
    return hosts


def leer_hostfile(ruta):
    """Hostfile de Open MPI ('nodo1 slots=2') -> [('nodo1', 2), ...]."""
    hosts = []
    with open(ruta) as f:
        for linea in f:
            linea = linea.split("#", 1)[0].strip()
            if not linea:
                continue
            campos = linea.split()
            m = re.search(r"slots=(\d+)", linea)
            hosts.append((campos[0], int(m.group(1)) if m else 1))
    return hosts


def asignar_rangos(hosts, procesos):
    """Host de cada rango con `--map-by slot`: llena los slots en orden y, si sobran rangos
    (--oversubscribe), vuelve a repartir uno por host en turno circular."""
    if not hosts:
        return ["local"] * procesos
    orden = [h for h, s in hosts for _ in range(s)]
    asignacion = orden[:procesos]
    i = 0
    while len(asignacion) < procesos:
        asignacion.append(hosts[i % len(hosts)][0])
        i += 1
    return asignacion


def desbalance(trabajos):
    """max/media del trabajo de los rangos que trabajan (1.0 = perfecto); "" si no hay datos."""
    utiles = [t for t in trabajos if t > 0]
    if not utiles:
        return ""
    return max(utiles) / (sum(utiles) / len(utiles))


def trabajo_por_nodo(asignacion, trabajos):
    """Suma de n_local por host, en orden de primera aparición."""
    total = {}
    for host, t in zip(asignacion, trabajos):
        total[host] = total.get(host, 0) + t
    return total
