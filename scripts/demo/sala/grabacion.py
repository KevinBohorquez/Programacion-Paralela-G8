"""Grabación de eventos SSE en .jsonl y reproducción con los tiempos originales (§5)."""
from __future__ import annotations

import json
import re
import threading
from pathlib import Path
from typing import Callable

NOMBRE_VALIDO = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")


def validar_nombre(nombre: str) -> str:
    nombre = str(nombre or "").removesuffix(".jsonl")
    if not NOMBRE_VALIDO.match(nombre) or nombre.startswith("."):
        raise ValueError(f"nombre de grabación inválido: {nombre!r}")
    return nombre


class Grabadora:
    """Oyente del difusor: mientras está activa, agrega cada evento como una línea JSON."""

    def __init__(self, directorio: Path) -> None:
        self.directorio = directorio
        self._archivo = None
        self._cerrojo = threading.Lock()
        self.nombre: str | None = None

    @property
    def activa(self) -> bool:
        return self._archivo is not None

    def iniciar(self, nombre: str) -> Path:
        nombre = validar_nombre(nombre)
        self.directorio.mkdir(parents=True, exist_ok=True)
        ruta = self.directorio / f"{nombre}.jsonl"
        with self._cerrojo:
            if self._archivo:
                self._archivo.close()
            self._archivo = ruta.open("w", encoding="utf-8")
            self.nombre = nombre
        return ruta

    def detener(self) -> None:
        with self._cerrojo:
            if self._archivo:
                self._archivo.close()
            self._archivo, self.nombre = None, None

    def __call__(self, evento: dict) -> None:
        with self._cerrojo:
            if self._archivo and evento.get("t") != "estado":
                self._archivo.write(json.dumps(evento, ensure_ascii=False) + "\n")
                self._archivo.flush()


def listar(directorio: Path) -> list[dict]:
    if not directorio.is_dir():
        return []
    return [{"nombre": r.stem, "bytes": r.stat().st_size,
             "eventos": sum(1 for _ in r.open(encoding="utf-8"))}
            for r in sorted(directorio.glob("*.jsonl"))]


def cargar(directorio: Path, nombre: str) -> list[dict]:
    ruta = directorio / f"{validar_nombre(nombre)}.jsonl"
    if not ruta.is_file():
        raise FileNotFoundError(f"no existe la grabación {ruta.name}")
    with ruta.open(encoding="utf-8") as f:
        return [json.loads(linea) for linea in f if linea.strip()]


def programa_replay(eventos: list[dict], velocidad: float = 1.0) -> list[tuple[float, dict]]:
    """(retardo desde el inicio del replay, evento) respetando los `ts` grabados, divididos por `velocidad`."""
    if velocidad <= 0:
        raise ValueError("velocidad debe ser > 0")
    if not eventos:
        return []
    t0 = eventos[0].get("ts", 0.0)
    programa, previo = [], 0.0
    for e in eventos:
        retardo = max(previo, (e.get("ts", t0) - t0) / velocidad)  # nunca hacia atrás
        programa.append((round(retardo, 6), e))
        previo = retardo
    return programa


def reproducir(programa: list[tuple[float, dict]], emitir: Callable[[dict], None], alto: threading.Event,
               reloj: Callable[[], float]) -> bool:
    """Emite el programa; `ts` se reescribe con el reloj actual y el original queda en `ts_original`.

    Devuelve False si se interrumpió con `alto`.
    """
    inicio = reloj()
    for retardo, evento in programa:
        espera = inicio + retardo - reloj()
        if espera > 0 and alto.wait(espera):
            return False
        if alto.is_set():
            return False
        copia = {k: v for k, v in evento.items() if k != "ts"}
        emitir({**copia, "ts_original": evento.get("ts"), "replay": True})
    return True
