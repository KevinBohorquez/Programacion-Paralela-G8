"""Servidor de la sala de control de la demo en vivo (docs/contrato-sala-control.md).

Corre dentro del contenedor pp-g8, solo con la biblioteca estándar de Python 3.12:
    python3 scripts/demo/sala_control.py --puerto 8765 --build-dir build/docker [--sin-progreso]
        [--interfaz moderna|clasica]

Lanza los backends reales, muestrea /proc/stat cada 0,2 s, emite eventos SSE en /api/stream,
graba en results/demo/sala/<nombre>.jsonl y reproduce esas grabaciones con sus tiempos.
"""
from __future__ import annotations

import argparse
import json
import logging
import mimetypes
import queue
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sala import grabacion, riesgo  # noqa: E402
from sala.cpu import MuestreadorCPU  # noqa: E402
from sala.eventos import Difusor, ahora, formatear_sse  # noqa: E402
from sala.lanzador import (BACKENDS, CorridaDetenida, CorridaFallida, Especificacion,  # noqa: E402
                           Lanzador)

RAIZ = Path(__file__).resolve().parents[2]
ESTATICOS = Path(__file__).resolve().parent / "sala" / "static"
# --interfaz: "moderna" is the React build committed in static/; "clasica" is the original vanilla UI.
INTERFACES = {"moderna": ESTATICOS, "clasica": ESTATICOS.parent / "clasica"}
mimetypes.add_type("font/woff2", ".woff2")
mimetypes.add_type("text/javascript", ".js")
NS_CONVERGENCIA = [1_000, 10_000, 100_000, 1_000_000, 10_000_000]
PLACEHOLDER = """<!doctype html><html lang="es"><head><meta charset="utf-8"><title>Sala de control</title>
<style>body{font-family:system-ui,sans-serif;background:#0F1726;color:#E7ECF4;margin:2rem}
pre{background:#172236;padding:1rem;max-height:70vh;overflow:auto;font-size:12px}</style></head>
<body><h1>Sala de control G8</h1><p>La interfaz (static/index.html) todavía no está instalada. Eventos SSE:</p>
<pre id="log"></pre><script>const l=document.getElementById('log'),es=new EventSource('/api/stream');
es.onmessage=e=>{const d=JSON.parse(e.data);if(d.t==='cpu')return;l.textContent=e.data+'\\n'+l.textContent.slice(0,20000)}
</script></body></html>"""

log = logging.getLogger("sala")


class Ocupado(Exception):
    pass


def entero(d: dict, clave: str, defecto: int, lo: int, hi: int) -> int:
    v = d.get(clave, defecto)
    v = int(float(v)) if v not in (None, "") else defecto
    if not lo <= v <= hi:
        raise ValueError(f"{clave} debe estar entre {lo} y {hi}")
    return v


def real(d: dict, clave: str, lo: float, hi: float) -> float | None:
    v = d.get(clave)
    if v in (None, ""):
        return None
    x = float(v)
    if not lo <= x <= hi:
        raise ValueError(f"{clave} fuera de rango")
    return x


def reparto_hibrido(nucleos: int) -> tuple[int, int]:
    """procesos × hilos = nucleos, con 4 procesos si se puede (24 → 4 × 6)."""
    for p in (4, 3, 2):
        if nucleos % p == 0 and nucleos // p >= 1:
            return p, nucleos // p
    return 1, nucleos


class Sala:
    """Estado compartido: una sola corrida o replay a la vez."""

    def __init__(self, dir_bin: Path, progreso: bool = True, dir_grabaciones: Path | None = None,
                 dir_config: Path | None = None) -> None:
        self.difusor = Difusor()
        self.grabadora = grabacion.Grabadora(dir_grabaciones or RAIZ / "results" / "demo" / "sala")
        self.difusor.agregar_oyente(self.grabadora)
        self.dir_config = dir_config or RAIZ / "config"
        self.lanzador = Lanzador(dir_bin, self.dir_config, self.difusor.emitir, progreso=progreso, raiz=RAIZ)
        self.modo = "vivo"
        self.ocupado = False
        self._cerrojo = threading.Lock()
        self._alto_replay = threading.Event()
        self._contador = 0

    # --- estado ---
    def estado(self) -> dict:
        return {"t": "estado", "modo": self.modo, "grabando": self.grabadora.activa, "ocupado": self.ocupado}

    def emitir_estado(self) -> None:
        self.difusor.emitir(self.estado())

    def ocupar(self, modo: str = "vivo") -> None:
        with self._cerrojo:
            if self.ocupado:
                raise Ocupado("ya hay una corrida en curso")
            self.ocupado, self.modo = True, modo
            self.lanzador.reiniciar()
            self._alto_replay.clear()
        self.emitir_estado()

    def liberar(self) -> None:
        with self._cerrojo:
            self.ocupado, self.modo = False, "vivo"
        self.emitir_estado()

    def nuevo_id(self, prefijo: str) -> str:
        with self._cerrojo:
            self._contador += 1
            return f"{prefijo}{self._contador}"

    def en_segundo_plano(self, trabajo, modo: str = "vivo") -> None:
        self.ocupar(modo)

        def envoltura():
            try:
                trabajo()
            except Exception as e:  # noqa: BLE001 - se informa por SSE
                log.exception("fallo en segundo plano")
                self.difusor.emitir({"t": "error", "id": None, "mensaje": str(e)})
            finally:
                self.liberar()

        threading.Thread(target=envoltura, daemon=True).start()

    def cpu(self, nucleos: list[float]) -> None:
        if self.modo != "replay":
            self.difusor.emitir({"t": "cpu", "nucleos": nucleos})

    def config_valida(self, nombre: str) -> str:
        nombre = str(nombre or "sintetico").removesuffix(".yaml")
        if "/" in nombre or "\\" in nombre or not (self.dir_config / f"{nombre}.yaml").is_file():
            raise ValueError(f"config desconocida: {nombre}")
        return nombre

    def _correr(self, esp: Especificacion, speedup_de=None) -> dict | None:
        try:
            return self.lanzador.ejecutar(esp, speedup_de)
        except CorridaDetenida:
            self.difusor.emitir({"t": "error", "id": esp.id, "mensaje": "corrida detenida"})
        except CorridaFallida as e:
            self.difusor.emitir({"t": "error", "id": esp.id, "mensaje": str(e)})
        return None

    # --- API ---
    def carrera(self, d: dict) -> dict:
        backends = d.get("backends") or list(BACKENDS)
        if not isinstance(backends, list) or any(b not in BACKENDS for b in backends):
            raise ValueError(f"backends válidos: {', '.join(BACKENDS)}")
        n = entero(d, "n", 20_000_000, 1, 1_000_000_000)
        nucleos = entero(d, "nucleos", 24, 1, 256)
        config = self.config_valida(d.get("config", "sintetico"))
        carrera = self.nuevo_id("c")

        def trabajo():
            t_serial: list[float] = []

            def speedup_de(segundos: float) -> float | None:
                return round(t_serial[0] / segundos, 3) if t_serial and segundos > 0 else None

            for b in backends:
                if self.lanzador.detenido:
                    break
                p, h, afin = 1, 1, "-"
                if b == "openmp":
                    h = nucleos
                elif b in ("mpi_estatico", "mpi_dinamico"):
                    p = max(2, nucleos)
                elif b == "hibrido":
                    (p, h), afin = reparto_hibrido(nucleos), "false"
                esp = Especificacion(f"{carrera}-{b}", b, n, config, p, h, afin)
                fin = self._correr(esp, (lambda s: 1.0) if b == "serial" else speedup_de)
                if fin and b == "serial":
                    t_serial.append(fin["segundos"])

        self.en_segundo_plano(trabajo)
        return {"carrera": carrera}

    def hibrido(self, d: dict) -> dict:
        afinidad = str(d.get("afinidad", "false"))
        if afinidad not in ("close", "false"):
            raise ValueError("afinidad debe ser close o false")
        p = entero(d, "procesos", 4, 1, 64)
        h = entero(d, "hilos", 6, 1, 64)
        n = entero(d, "n", 20_000_000, 1, 1_000_000_000)
        config = self.config_valida(d.get("config", "sintetico"))
        id_corrida = f"{self.nuevo_id('h')}-{afinidad}"
        esp = Especificacion(id_corrida, "hibrido", n, config, p, h, afinidad)
        self.en_segundo_plano(lambda: self._correr(esp))
        return {"id": id_corrida}

    def _openmp_sincrono(self, prefijo: str, config: str, n: int, hilos: int, extra: list[str]) -> tuple[dict, dict]:
        esp = Especificacion(self.nuevo_id(prefijo), "openmp", n, config, 1, hilos, "-", extra)
        fin = self.lanzador.ejecutar(esp, emitir_eventos=False)
        return fin, self.lanzador.ultima_fila

    def riesgo(self, q: dict) -> dict:
        config = self.config_valida(q.get("config", "sintetico"))
        c = real(q, "c", 0, 1000)
        n = entero(q, "n", 100_000, 1, 100_000_000)
        hilos = entero(q, "hilos", 24, 1, 256)
        extra = ["--capacidad", repr(c)] if c is not None else []
        self.ocupar()
        try:
            fin, fila = self._openmp_sincrono("r", config, n, hilos, extra)
        finally:
            self.liberar()
        curva = riesgo.curva_riesgo(riesgo.leer_hist(fila["hist512"]))
        return {**curva, "segundos": fin["segundos"], "c": float(fila["capacidad"]), "umbral": float(fila["umbral"])}

    def convergencia(self, q: dict) -> list[dict]:
        config = self.config_valida(q.get("config", "sintetico"))
        extra = ["--config-id", "0"]  # config_id = 0: las corridas con N creciente son prefijos entre sí
        for clave, bandera in (("c", "--capacidad"), ("u", "--umbral")):
            x = real(q, clave, 0, 1000)
            if x is not None:
                extra += [bandera, repr(x)]
        ns = q.get("ns") or NS_CONVERGENCIA
        if isinstance(ns, str):
            ns = [x for x in ns.replace(";", ",").split(",") if x.strip()]
        ns = sorted({entero({"n": x}, "n", 1000, 1, 100_000_000) for x in ns})
        hilos = entero(q, "hilos", 24, 1, 256)
        self.ocupar()
        try:
            puntos = []
            for n in ns:
                fin, _ = self._openmp_sincrono("v", config, n, hilos, extra)
                puntos.append({"n": n, "k": fin["k"], "p": fin["p"], "lo": fin["wilson"][0],
                               "hi": fin["wilson"][1], "segundos": fin["segundos"]})
        finally:
            self.liberar()
        return puntos

    def detener(self) -> dict:
        self._alto_replay.set()
        self.lanzador.detener()
        return {"detenido": self.ocupado}

    def grabar(self, d: dict) -> dict:
        if d.get("activo", True):
            ruta = self.grabadora.iniciar(d.get("nombre") or time.strftime("ensayo-%Y%m%d-%H%M%S"))
            resultado = {"grabando": True, "archivo": str(ruta.relative_to(RAIZ)) if ruta.is_relative_to(RAIZ)
                         else str(ruta)}
        else:
            self.grabadora.detener()
            resultado = {"grabando": False}
        self.emitir_estado()
        return resultado

    def replay(self, d: dict) -> dict:
        velocidad = float(d.get("velocidad") or 1.0)
        eventos = grabacion.cargar(self.grabadora.directorio, d.get("nombre", "ensayo"))
        programa = grabacion.programa_replay(eventos, velocidad)
        self.en_segundo_plano(lambda: grabacion.reproducir(programa, self.difusor.emitir, self._alto_replay,
                                                           time.monotonic), modo="replay")
        return {"eventos": len(programa), "duracion_s": programa[-1][0] if programa else 0.0}

    def grabaciones(self) -> list[dict]:
        return grabacion.listar(self.grabadora.directorio)


class Manejador(BaseHTTPRequestHandler):
    sala: Sala
    estaticos: Path = ESTATICOS
    protocol_version = "HTTP/1.1"

    def _enviar(self, codigo: int, cuerpo: bytes, tipo: str) -> None:
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(cuerpo)

    def _json(self, codigo: int, obj) -> None:
        self._enviar(codigo, json.dumps(obj, ensure_ascii=False).encode(), "application/json; charset=utf-8")

    def _api(self, funcion, *args) -> None:
        try:
            self._json(200, funcion(*args))
        except Ocupado as e:
            self._json(409, {"error": str(e)})
        except FileNotFoundError as e:
            self._json(404, {"error": str(e)})
        except (ValueError, TypeError, json.JSONDecodeError) as e:
            self._json(400, {"error": str(e)})
        except (CorridaFallida, CorridaDetenida) as e:
            self._json(500, {"error": str(e)})

    def _estatico(self, ruta: str) -> None:
        relativa = ruta.lstrip("/").removeprefix("static/") or "index.html"
        archivo = (self.estaticos / relativa).resolve()
        if not archivo.is_relative_to(self.estaticos.resolve()) or not archivo.is_file():
            if relativa == "index.html":
                self._enviar(200, PLACEHOLDER.encode(), "text/html; charset=utf-8")
            else:
                self._json(404, {"error": "no encontrado"})
            return
        tipo = mimetypes.guess_type(archivo.name)[0] or "application/octet-stream"
        if tipo.startswith("text/") or tipo in ("application/javascript", "application/json"):
            tipo += "; charset=utf-8"
        self._enviar(200, archivo.read_bytes(), tipo)

    def _stream(self) -> None:
        sala = self.sala
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Accel-Buffering", "no")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        cola = sala.difusor.suscribir()
        try:
            self.wfile.write(formatear_sse({**sala.estado(), "ts": ahora()}))
            self.wfile.flush()
            while True:
                try:
                    evento = cola.get(timeout=15)
                    self.wfile.write(formatear_sse(evento))
                except queue.Empty:  # latido para mantener viva la conexión
                    self.wfile.write(b": latido\n\n")
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            sala.difusor.desuscribir(cola)
            self.close_connection = True

    def do_GET(self):  # noqa: N802
        partes = urlsplit(self.path)
        q = {k: v[-1] for k, v in parse_qs(partes.query).items()}
        ruta = partes.path
        if ruta == "/api/stream":
            self._stream()
        elif ruta == "/api/configs":
            self._api(riesgo.listar_configs, self.sala.dir_config)
        elif ruta == "/api/riesgo":
            self._api(self.sala.riesgo, q)
        elif ruta == "/api/convergencia":
            self._api(self.sala.convergencia, q)
        elif ruta == "/api/grabaciones":
            self._api(self.sala.grabaciones)
        elif ruta == "/api/estado":
            self._api(self.sala.estado)
        elif ruta.startswith("/api/"):
            self._json(404, {"error": "no encontrado"})
        else:
            self._estatico(ruta)

    do_HEAD = do_GET

    def do_POST(self):  # noqa: N802
        largo = int(self.headers.get("Content-Length") or 0)
        try:
            datos = json.loads(self.rfile.read(largo) or b"{}")
            if not isinstance(datos, dict):
                raise ValueError("el cuerpo debe ser un objeto JSON")
        except (ValueError, json.JSONDecodeError) as e:
            self._json(400, {"error": str(e)})
            return
        rutas = {"/api/carrera": self.sala.carrera, "/api/hibrido": self.sala.hibrido,
                 "/api/detener": lambda d: self.sala.detener(), "/api/grabar": self.sala.grabar,
                 "/api/replay": self.sala.replay}
        funcion = rutas.get(urlsplit(self.path).path)
        if funcion is None:
            self._json(404, {"error": "no encontrado"})
        else:
            self._api(funcion, datos)

    def log_message(self, fmt, *args):
        if "/api/stream" not in (args[0] if args else ""):
            log.info("http %s | %s", self.client_address[0], fmt % args)


def crear_servidor(sala: Sala, host: str, puerto: int, estaticos: Path = ESTATICOS) -> ThreadingHTTPServer:
    """`estaticos` is the UI folder served at `/` and under `/static/` (see INTERFACES)."""
    manejador = type("ManejadorSala", (Manejador,), {"sala": sala, "estaticos": estaticos})
    servidor = ThreadingHTTPServer((host, puerto), manejador)
    servidor.daemon_threads = True
    return servidor


def analizar_argumentos(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--puerto", type=int, default=8765)
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--build-dir", default="build/docker", help="directorio de compilación de CMake")
    ap.add_argument("--sin-progreso", action="store_true",
                    help="no pasa --progreso a los binarios; el avance se estima con el tiempo esperado")
    ap.add_argument("--interfaz", choices=sorted(INTERFACES), default="moderna",
                    help="moderna: compilación React de sala/static/; clasica: interfaz original de sala/clasica/")
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    a = analizar_argumentos(argv)
    logging.basicConfig(level=logging.INFO, stream=sys.stdout, format="%(asctime)s [%(levelname)s] %(message)s")
    dir_build = Path(a.build_dir)
    dir_build = dir_build if dir_build.is_absolute() else RAIZ / dir_build
    sala = Sala(dir_build / "src" / "backends", progreso=not a.sin_progreso)
    MuestreadorCPU(sala.cpu).start()
    servidor = crear_servidor(sala, a.host, a.puerto, INTERFACES[a.interfaz])
    log.info("Sala de control en http://127.0.0.1:%d (interfaz %s, binarios %s, progreso %s)", a.puerto,
             a.interfaz, dir_build, "estimado" if a.sin_progreso else "real")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        sala.detener()


if __name__ == "__main__":
    main()
