"""Construye los comandos de los backends, los lanza y traduce su salida a eventos `avance`, `bloque` y `fin`."""
from __future__ import annotations

import csv
import os
import queue
import re
import signal
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import riesgo

BACKENDS = ("serial", "openmp", "mpi_estatico", "mpi_dinamico", "hibrido")
EJECUTABLES = {"serial": "serial/pp_serial", "openmp": "openmp/pp_openmp", "mpi_estatico": "mpi/pp_mpi_estatico",
               "mpi_dinamico": "mpi/pp_mpi_dinamico", "hibrido": "hybrid/pp_hibrido"}
MPIRUN = ["mpirun", "--allow-run-as-root", "--oversubscribe"]
COSTO_SERIAL_S = 3e-6  # segundos por escenario en serial: estimación inicial para --sin-progreso

PROG_AVANCE = re.compile(r"^\[prog\](?: rango=(\d+))? hecho=(\d+) total=(\d+)\s*$")
PROG_BLOQUE = re.compile(r"^\[prog\] rango=(\d+) bloque=(\d+),(\d+)\s*$")
VERIF_RANGO = re.compile(r"\[verif\] rango=(\d+)\b.* n_local=(\d+)")


class CorridaDetenida(Exception):
    pass


class CorridaFallida(RuntimeError):
    pass


def parsear_prog(linea: str) -> dict | None:
    """Traduce una línea `[prog]` (§1) a {'tipo': 'avance'|'bloque', ...}; None si no es una línea de avance."""
    linea = linea.strip()
    m = PROG_BLOQUE.match(linea)
    if m:
        return {"tipo": "bloque", "rango": int(m[1]), "i0": int(m[2]), "i1": int(m[3])}
    m = PROG_AVANCE.match(linea)
    if m:
        return {"tipo": "avance", "rango": int(m[1]) if m[1] is not None else None,
                "hecho": int(m[2]), "total": int(m[3])}
    return None


def trabajo_rangos(lineas: list[str]) -> list[int] | None:
    """n_local de cada rango según las líneas `[verif] rango=`; None si no hay (serial, OpenMP)."""
    por_rango = {}
    for linea in lineas:
        m = VERIF_RANGO.search(linea)
        if m:
            por_rango[int(m[1])] = int(m[2])
    return [por_rango[r] for r in sorted(por_rango)] if por_rango else None


def construir_fin(id_corrida: str, fila: dict, lineas_verif: list[str], speedup: float | None = None) -> dict:
    """Evento `fin` (§2) desde la última fila del CSV y las líneas `[verif]`."""
    k, n = int(fila["k"]), int(fila["n"])
    hist = riesgo.leer_hist(fila["hist512"])
    lo, hi = float(fila["wilson_inf"]), float(fila["wilson_sup"])
    return {"t": "fin", "id": id_corrida, "backend": fila["backend"], "segundos": float(fila["tiempo_s"]),
            "k": k, "n": n, "p": float(fila["p_hat"]), "wilson": [lo, hi], "huella": riesgo.huella(hist),
            "trabajo_rangos": trabajo_rangos(lineas_verif), "speedup": speedup}


def leer_ultima_fila(ruta: Path) -> dict:
    with ruta.open(encoding="utf-8") as f:
        filas = list(csv.DictReader(f))
    if not filas:
        raise CorridaFallida(f"{ruta.name} no tiene filas")
    return filas[-1]


@dataclass
class Especificacion:
    id: str
    backend: str
    n: int
    config: str = "sintetico"
    procesos: int = 1
    hilos: int = 1
    afinidad: str = "-"  # close | false | -
    extra: list[str] = field(default_factory=list)

    @property
    def unidades(self) -> int:
        return self.procesos * self.hilos


def construir_comando(esp: Especificacion, dir_bin: Path, dir_config: Path, salida: Path,
                      progreso: bool) -> tuple[list[str], dict[str, str]]:
    """argv y variables de entorno según la afinidad del contrato (§4)."""
    if esp.backend not in EJECUTABLES:
        raise ValueError(f"backend desconocido: {esp.backend}")
    exe = str(dir_bin / EJECUTABLES[esp.backend])
    comunes = ["--config", str(dir_config / f"{esp.config}.yaml"), "--n", str(esp.n), *esp.extra,
               "--salida", str(salida)]
    if progreso:
        comunes.append("--progreso")
    env: dict[str, str] = {}
    if esp.backend == "serial":
        argv = [exe, *comunes]
    elif esp.backend == "openmp":
        env = {"OMP_PROC_BIND": "close", "OMP_PLACES": "cores"}
        argv = [exe, *comunes, "--hilos", str(esp.hilos)]
    elif esp.backend in ("mpi_estatico", "mpi_dinamico"):
        env = {"OMP_NUM_THREADS": "1"}
        argv = [*MPIRUN, "-np", str(esp.procesos), "--bind-to", "core", exe, *comunes]
    else:  # híbrido: --bind-to none; OMP_PROC_BIND=false es la corrección y close el error a propósito
        if esp.afinidad not in ("close", "false"):
            raise ValueError("afinidad del híbrido debe ser close o false")
        env = {"OMP_PROC_BIND": esp.afinidad, "OMP_PLACES": "cores"}
        argv = [*MPIRUN, "-np", str(esp.procesos), "--bind-to", "none",
                *[x for k in env for x in ("-x", k)], exe, *comunes, "--hilos", str(esp.hilos)]
    return argv, env


def texto_comando(argv: list[str], env: dict[str, str]) -> str:
    return " ".join([*(f"{k}={v}" for k, v in env.items()), *argv])


class Lanzador:
    """Ejecuta una corrida a la vez y emite sus eventos; `detener()` mata el grupo de procesos."""

    def __init__(self, dir_bin: Path, dir_config: Path, emitir: Callable[[dict], None], progreso: bool = True,
                 periodo_estimado: float = 0.2, raiz: Path | None = None) -> None:
        self.dir_bin, self.dir_config, self.emitir = dir_bin, dir_config, emitir
        self.progreso, self.periodo_estimado, self.raiz = progreso, periodo_estimado, raiz
        self.costo_serial = COSTO_SERIAL_S
        self._proc: subprocess.Popen | None = None
        self.ultima_fila: dict = {}
        self._alto = threading.Event()

    def detener(self) -> None:
        self._alto.set()
        proc = self._proc
        if proc and proc.poll() is None:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except (ProcessLookupError, PermissionError, AttributeError):
                proc.terminate()

    def reiniciar(self) -> None:
        self._alto.clear()

    @property
    def detenido(self) -> bool:
        return self._alto.is_set()

    def ejecutar(self, esp: Especificacion, speedup_de: Callable[[float], float | None] | None = None,
                 emitir_eventos: bool = True) -> dict:
        """Lanza la corrida y devuelve el evento `fin` (ya emitido si `emitir_eventos`)."""
        emitir = self.emitir if emitir_eventos else (lambda e: None)
        if self._alto.is_set():
            raise CorridaDetenida("corrida detenida")
        with tempfile.TemporaryDirectory(prefix="sala-") as tmp:
            salida = Path(tmp) / "corrida.csv"
            argv, env = construir_comando(esp, self.dir_bin, self.dir_config, salida, self.progreso)
            texto = texto_comando(argv, env)
            emitir({"t": "inicio", "id": esp.id, "backend": esp.backend, "procesos": esp.procesos,
                    "hilos": esp.hilos, "n": esp.n, "afinidad": esp.afinidad, "comando": texto})
            t0 = time.monotonic()
            lineas, verif = self._correr(argv, env, esp, emitir, t0)
            pared = time.monotonic() - t0
            if self._alto.is_set():
                raise CorridaDetenida("corrida detenida")
            fila = leer_ultima_fila(salida)
        self.ultima_fila = fila
        fin = construir_fin(esp.id, fila, verif)
        fin["segundos_pared"] = round(pared, 3)
        if speedup_de:
            fin["speedup"] = speedup_de(fin["segundos"])
        if esp.backend == "serial" and fin["segundos"] > 0:
            self.costo_serial = fin["segundos"] / esp.n
        emitir(fin)
        return fin

    def _correr(self, argv, env, esp, emitir, t0) -> tuple[list[str], list[str]]:
        cola: queue.Queue = queue.Queue()
        self._proc = proc = subprocess.Popen(
            argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1,
            env={**os.environ, **env}, cwd=self.raiz, start_new_session=True)

        def leer(flujo):
            for linea in flujo:
                cola.put(linea.rstrip("\n"))
            cola.put(None)

        hilos = [threading.Thread(target=leer, args=(f,), daemon=True) for f in (proc.stdout, proc.stderr)]
        for h in hilos:
            h.start()
        abiertos, lineas, verif = 2, [], []
        esperado = self.costo_serial * esp.n / max(1, esp.unidades if esp.backend != "mpi_dinamico"
                                                   else max(1, esp.procesos - 1))
        ultimo = t0
        while abiertos:
            try:
                linea = cola.get(timeout=self.periodo_estimado)
            except queue.Empty:
                linea = ""
            if not self.progreso and time.monotonic() - ultimo >= self.periodo_estimado:
                ultimo = time.monotonic()
                self._avance_estimado(esp, emitir, ultimo - t0, esperado)
            if linea == "":
                continue
            if linea is None:
                abiertos -= 1
                continue
            lineas.append(linea)
            if linea.startswith("[verif]"):
                verif.append(linea)
            elif linea.startswith("[prog]"):
                ev = parsear_prog(linea)
                if ev and ev["tipo"] == "avance":
                    dt = max(time.monotonic() - t0, 1e-6)
                    emitir({"t": "avance", "id": esp.id, "hecho": ev["hecho"], "total": ev["total"],
                            "rango": ev["rango"], "escenarios_s": round(ev["hecho"] / dt, 1)})
                elif ev:
                    emitir({"t": "bloque", "id": esp.id, "rango": ev["rango"], "i0": ev["i0"], "i1": ev["i1"]})
        codigo = proc.wait()
        self._proc = None
        if self._alto.is_set():
            return lineas, verif
        if codigo != 0:
            cola_err = "\n".join(lineas[-15:])
            raise CorridaFallida(f"{esp.backend} terminó con código {codigo}\n{cola_err}")
        if not self.progreso:
            emitir({"t": "avance", "id": esp.id, "hecho": esp.n, "total": esp.n, "rango": None,
                    "escenarios_s": round(esp.n / max(time.monotonic() - t0, 1e-6), 1), "estimado": True})
        return lineas, verif

    @staticmethod
    def _avance_estimado(esp, emitir, transcurrido: float, esperado: float) -> None:
        hecho = int(min(0.99, transcurrido / max(esperado, 1e-6)) * esp.n)
        emitir({"t": "avance", "id": esp.id, "hecho": hecho, "total": esp.n, "rango": None,
                "escenarios_s": round(hecho / max(transcurrido, 1e-6), 1), "estimado": True})
