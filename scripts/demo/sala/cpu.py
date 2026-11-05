"""Muestreo de /proc/stat: utilización por CPU lógica como diferencia entre dos muestras."""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable

PROC_STAT = Path("/proc/stat")


def leer_proc_stat(texto: str) -> list[tuple[int, int]]:
    """Devuelve (total, inactivo) por cada línea `cpuN` en el orden de /proc/stat (sin la línea `cpu` agregada).

    Inactivo = idle + iowait. Se excluyen guest y guest_nice, que ya están contados en user y nice.
    """
    muestras = []
    for linea in texto.splitlines():
        campos = linea.split()
        if not campos or not campos[0].startswith("cpu") or campos[0] == "cpu":
            continue
        valores = [int(x) for x in campos[1:]]
        valores += [0] * (10 - len(valores))
        total = sum(valores[:8])
        inactivo = valores[3] + valores[4]
        muestras.append((total, inactivo))
    return muestras


def utilizacion(previa: list[tuple[int, int]], actual: list[tuple[int, int]]) -> list[float]:
    """Fracción ocupada (0–1) de cada CPU entre dos muestras; 0 si no avanzó el contador."""
    nucleos = []
    for (t0, i0), (t1, i1) in zip(previa, actual):
        dt, di = t1 - t0, i1 - i0
        nucleos.append(round(min(1.0, max(0.0, 1.0 - di / dt)), 3) if dt > 0 else 0.0)
    return nucleos


class MuestreadorCPU(threading.Thread):
    """Lee /proc/stat cada `periodo` segundos y entrega la lista `nucleos` a `entregar`."""

    def __init__(self, entregar: Callable[[list[float]], None], periodo: float = 0.2,
                 ruta: Path = PROC_STAT) -> None:
        super().__init__(daemon=True, name="muestreador-cpu")
        self._entregar, self._periodo, self._ruta = entregar, periodo, ruta
        self._alto = threading.Event()

    def detener(self) -> None:
        self._alto.set()

    def run(self) -> None:
        try:
            previa = leer_proc_stat(self._ruta.read_text())
        except OSError:
            return  # sin /proc (por ejemplo, fuera de Linux): no hay eventos cpu
        while not self._alto.wait(self._periodo):
            actual = leer_proc_stat(self._ruta.read_text())
            self._entregar(utilizacion(previa, actual))
            previa = actual
