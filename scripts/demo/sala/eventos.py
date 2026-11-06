"""Difusor SSE: cada cliente tiene su propia cola; los eventos se sellan con `ts` (§2)."""
from __future__ import annotations

import json
import queue
import threading
import time
from typing import Callable

ARRANQUE = time.monotonic()


def ahora() -> float:
    """Segundos desde el arranque del servidor."""
    return round(time.monotonic() - ARRANQUE, 3)


def formatear_sse(evento: dict) -> bytes:
    return f"data: {json.dumps(evento, ensure_ascii=False)}\n\n".encode()


class Difusor:
    """Reparte cada evento a todas las colas suscritas y avisa a los oyentes (por ejemplo, la grabadora)."""

    def __init__(self, capacidad: int = 2000) -> None:
        self._colas: set[queue.Queue] = set()
        self._oyentes: list[Callable[[dict], None]] = []
        self._cerrojo = threading.Lock()
        self._capacidad = capacidad

    def suscribir(self) -> queue.Queue:
        cola: queue.Queue = queue.Queue(maxsize=self._capacidad)
        with self._cerrojo:
            self._colas.add(cola)
        return cola

    def desuscribir(self, cola: queue.Queue) -> None:
        with self._cerrojo:
            self._colas.discard(cola)

    def agregar_oyente(self, oyente: Callable[[dict], None]) -> None:
        self._oyentes.append(oyente)

    @property
    def clientes(self) -> int:
        with self._cerrojo:
            return len(self._colas)

    def emitir(self, evento: dict) -> dict:
        evento = {**evento}
        evento.setdefault("ts", ahora())
        with self._cerrojo:
            colas = list(self._colas)
        for cola in colas:
            try:
                cola.put_nowait(evento)
            except queue.Full:  # cliente lento: se descarta el evento más viejo
                try:
                    cola.get_nowait()
                    cola.put_nowait(evento)
                except (queue.Empty, queue.Full):
                    pass
        for oyente in self._oyentes:
            oyente(evento)
        return evento
