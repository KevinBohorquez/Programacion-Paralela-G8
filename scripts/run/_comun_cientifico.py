"""Utilidades compartidas por los experimentos científicos X6 (T34), riesgo (T35) y X7 (T42).

Cada experimento es una lista de *puntos*: una configuración config/<estacion>_<regimen>.yaml más
la capacidad C, el umbral U, el número de escenarios N y, en el bootstrap, los parámetros de una
réplica. Cada punto se corre con el simulador (pp_openmp o pp_hibrido), que agrega una fila al CSV
del contrato (docs/contratos.md §5). La corrida es reanudable: un punto cuya clave ya está en el CSV
no se vuelve a correr.

Semillas: cada punto usa la `semilla` y el `config_id` de su YAML, sin cambiarlos al variar C, U o los
parámetros. Así todos los puntos de una estación y régimen comparten los mismos números aleatorios
(números aleatorios comunes): la curva riesgo–capacidad es monótona y las diferencias entre réplicas
bootstrap reflejan solo la incertidumbre de los parámetros.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import platform
import re
import shlex
import subprocess
import time

ROOT = Path(__file__).resolve().parents[2]
Z95 = 1.959963984540054
PARAMETROS = ("p01", "p11", "alfa", "theta")
CAPACIDADES_X6 = (2, 3, 4, 5, 6, 7, 8, 9, 10, 12, 15, 20, 25, 30)
NOTA_V6 = ("V6 (validación contra datos observados) falla en estadísticos de cola (sd -32 %, "
           "p99 -42 %) en 16/16 grupos: el modelo subestima los extremos y estas probabilidades "
           "pueden subestimar el riesgo hasta que la ola D recalibre.")
ENCABEZADO = (
    "backend,estacion,regimen,config_id,semilla,n,k,p_hat,wilson_inf,wilson_sup,dias,capacidad,umbral,"
    "p01,p11,alfa,theta,hilos,procesos,repeticion,calentamiento,schedule,afinidad,tiempo_s,commit,cpu,"
    "nucleos_fisicos,nucleos_logicos,hist512,hardware,nodos,distribucion,bloques,hilos_por_bloque"
).split(",")
BINARIOS = {"openmp": "src/backends/openmp/pp_openmp", "hibrido": "src/backends/hybrid/pp_hibrido"}


# --- Configuración y CSV -------------------------------------------------------------------------

def leer_yaml_plano(ruta: Path) -> dict[str, str]:
    """Lee el YAML plano `clave: valor` del contrato (§3); `#` inicia un comentario."""
    datos = {}
    for linea in Path(ruta).read_text(encoding="utf-8").splitlines():
        linea = linea.split("#", 1)[0].strip()
        if ":" in linea:
            clave, valor = linea.split(":", 1)
            datos[clave.strip()] = valor.strip()
    return datos


def escribir_yaml_plano(ruta: Path, datos: dict, comentario: str = "") -> Path:
    lineas = [f"# {c}" for c in comentario.splitlines() if c] + [f"{k}: {v}" for k, v in datos.items()]
    Path(ruta).write_text("\n".join(lineas) + "\n", encoding="utf-8")
    return Path(ruta)


def leer_resultados(ruta: Path) -> list[dict]:
    """Filas de un CSV (vacío si no existe)."""
    ruta = Path(ruta)
    if not ruta.exists():
        return []
    with ruta.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def escribir_tabla(ruta: Path, filas: list[dict], campos: list[str]) -> Path:
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=campos, lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        w.writerows({k: fmt(v) for k, v in fila.items()} for fila in filas)
    return ruta


def fmt(valor) -> str:
    if isinstance(valor, float):
        if not math.isfinite(valor):
            return ""
        return str(int(valor)) if valor.is_integer() else repr(valor)
    return "" if valor is None else str(valor)


def num(valor) -> float:
    """Número normalizado para comparar claves (el CSV usa 17 cifras; los YAML, 6 decimales)."""
    return round(float(valor), 6)


def escribir_markdown(ruta: Path, titulo: str, filas: list[dict], campos: list[str],
                      notas: list[str] = ()) -> Path:
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    lineas = [f"# {titulo}", ""]
    lineas += [f"> {n}" for n in notas] + ([""] if notas else [])
    lineas.append("| " + " | ".join(campos) + " |")
    lineas.append("|" + "|".join("---" for _ in campos) + "|")
    for fila in filas:
        lineas.append("| " + " | ".join(fmt_md(fila.get(c)) for c in campos) + " |")
    ruta.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    return ruta


def fmt_md(valor) -> str:
    if isinstance(valor, float):
        if not math.isfinite(valor):
            return "—"
        return str(int(valor)) if valor.is_integer() else f"{valor:.4g}"
    return "—" if valor in (None, "") else str(valor)


# --- Estadística ---------------------------------------------------------------------------------

def wilson(k: int, n: int, z: float = Z95) -> tuple[float, float]:
    """Intervalo de Wilson, igual que src/stats/wilson.cpp."""
    if n == 0:
        return 0.0, 1.0
    p = k / n
    z2 = z * z
    den = 1.0 + z2 / n
    centro = (p + z2 / (2.0 * n)) / den
    mitad = z * math.sqrt(p * (1.0 - p) / n + z2 / (4.0 * n * n)) / den
    inf, sup = max(0.0, centro - mitad), min(1.0, centro + mitad)
    return (0.0 if k == 0 else inf), (1.0 if k == n else sup)


def parse_hist(texto: str) -> list[int]:
    return [int(x) for x in texto.split(";")] if texto else []


def excedencia_hist(hist: list[int], u: float) -> float:
    """Fracción con floor(Amax) >= ceil(u), es decir P(Amax > u) para u entero >= 1.

    La clase b del histograma es [b, b+1) mm (la última, >= 511). Para u entero, Amax > u equivale a
    floor(Amax) >= u salvo el empate Amax == u, de probabilidad nula. Para u no entero es una cota
    inferior (la clase floor(u) queda fuera).
    """
    total = sum(hist)
    if total == 0:
        return float("nan")
    return sum(hist[min(int(math.ceil(u)), len(hist) - 1):]) / total


def percentil(valores: list[float], q: float) -> float:
    """Percentil con interpolación lineal (igual que numpy.percentile por defecto)."""
    v = sorted(valores)
    if not v:
        return float("nan")
    pos = (len(v) - 1) * q / 100.0
    i = int(math.floor(pos))
    j = min(i + 1, len(v) - 1)
    return v[i] + (v[j] - v[i]) * (pos - i)


# --- Puntos y plan -------------------------------------------------------------------------------

@dataclass
class Punto:
    config: Path
    estacion: str
    regimen: str
    config_id: str
    semilla: str
    capacidad: float
    umbral: float
    n: int
    params: dict = field(default_factory=dict)  # p01, p11, alfa, theta del YAML (texto)
    replica: str = ""

    @property
    def etiqueta(self) -> str:
        r = f"_b{self.replica}" if self.replica else ""
        return f"{self.estacion}_{self.regimen}{r}_C{self.capacidad:g}_U{self.umbral:g}_N{self.n}"


def punto_desde_config(ruta: Path, *, capacidad=None, umbral=None, n=None, replica="") -> Punto:
    c = leer_yaml_plano(ruta)
    return Punto(config=Path(ruta), estacion=c.get("estacion", "sintetica"),
                 regimen=c.get("regimen", "normal"), config_id=c.get("config_id", "0"),
                 semilla=c.get("semilla", "12345"),
                 capacidad=float(c.get("capacidad", 0) if capacidad is None else capacidad),
                 umbral=float(c.get("umbral", 0) if umbral is None else umbral),
                 n=int(float(c.get("n", 1_000_000) if n is None else n)),
                 params={p: c.get(p, "0") for p in PARAMETROS}, replica=replica)


def clave_punto(p: Punto) -> tuple:
    return (p.estacion, p.regimen, num(p.capacidad), num(p.umbral), int(p.n),
            *(num(p.params[k]) for k in PARAMETROS))


def clave_fila(f: dict) -> tuple:
    return (f["estacion"], f["regimen"], num(f["capacidad"]), num(f["umbral"]), int(f["n"]),
            *(num(f[k]) for k in PARAMETROS))


def pendientes(plan: list[Punto], salida: Path) -> list[Punto]:
    hechas = {clave_fila(f) for f in leer_resultados(salida)}
    return [p for p in plan if clave_punto(p) not in hechas]


def configs_por_defecto(directorio: Path = ROOT / "config") -> list[Path]:
    """Las 10 configuraciones estación × régimen (excluye ejemplo.yaml y sintetico.yaml)."""
    d = Path(directorio)
    return sorted(d.glob("*_normal.yaml")) + sorted(d.glob("*_el_nino.yaml"))


def lista_numeros(texto: str) -> list[float]:
    return [float(x) for x in re.split(r"[,\s]+", texto.strip()) if x]


# --- Ejecución -----------------------------------------------------------------------------------

def comando(p: Punto, backend: str, build_dir: Path, hilos: int, procesos: int, salida: Path) -> list[str]:
    binario = str(Path(build_dir) / BINARIOS[backend])
    cmd = [binario, "--config", str(p.config), "--capacidad", f"{p.capacidad:g}",
           "--umbral", f"{p.umbral:g}", "--n", str(p.n), "--hilos", str(hilos), "--salida", str(salida)]
    if backend == "hibrido":
        cmd = ["mpirun", "-np", str(procesos), "--bind-to", "none", *cmd]
    return cmd


def commit_actual() -> str:
    if os.environ.get("PP_COMMIT"):
        return os.environ["PP_COMMIT"]
    try:
        r = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True,
                           text=True, timeout=10)
        return r.stdout.strip() or "desconocido"
    except (OSError, subprocess.SubprocessError):
        return "desconocido"


def info_hardware() -> dict:
    cpu, ram = platform.processor() or "desconocido", None
    try:
        for linea in Path("/proc/cpuinfo").read_text(encoding="utf-8").splitlines():
            if linea.startswith("model name"):
                cpu = linea.split(":", 1)[1].strip()
                break
        for linea in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            if linea.startswith("MemTotal"):
                ram = round(int(linea.split()[1]) / 1024 ** 2, 1)
    except OSError:
        pass
    return {"host": platform.node(), "cpu": cpu, "nucleos_logicos": os.cpu_count(), "ram_gb": ram,
            "sistema": platform.platform(), "python": platform.python_version()}


def entorno_simulador() -> dict:
    env = dict(os.environ)
    env.setdefault("OMP_PROC_BIND", "close")
    env.setdefault("OMP_PLACES", "cores")
    env["PP_COMMIT"] = commit_actual()
    if hasattr(os, "geteuid") and os.geteuid() == 0:  # mpirun como root dentro de la imagen
        env.setdefault("OMPI_ALLOW_RUN_AS_ROOT", "1")
        env.setdefault("OMPI_ALLOW_RUN_AS_ROOT_CONFIRM", "1")
    return env


def runner_subprocess(cmd: list[str], log: Path, env: dict) -> int:
    with Path(log).open("a", encoding="utf-8") as f:
        f.write(f"$ {shlex.join(cmd)}\n")
        f.flush()
        r = subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, env=env)
        f.write(f"[codigo_salida] {r.returncode}\n")
    return r.returncode


def prob_falsa(d: dict) -> float:
    """Probabilidad por defecto del simulador falso: decrece con C y U y crece con p01."""
    c, u = max(float(d["capacidad"]), 1e-9), max(float(d["umbral"]), 1e-9)
    return min(1.0, 120.0 * float(d["p01"]) / (c * u))


class RunnerFalso:
    """Simulador de mentira para las pruebas: agrega una fila del contrato con k = round(prob · n).

    `prob(datos)` recibe la configuración efectiva (YAML + banderas) y devuelve la probabilidad. El
    histograma pone las k inundaciones en la clase ceil(U) y el resto en la clase 0, así que la
    excedencia calculada desde hist512 reproduce k.
    """

    def __init__(self, prob=None, falla_en=()):
        self.prob = prob or prob_falsa
        self.falla_en = set(falla_en)
        self.comandos = []

    def __call__(self, cmd: list[str], log: Path, env: dict) -> int:
        self.comandos.append(cmd)
        i = cmd.index("--config")
        datos = leer_yaml_plano(Path(cmd[i + 1]))
        for j in range(i + 2, len(cmd) - 1, 2):
            datos[cmd[j].lstrip("-")] = cmd[j + 1]
        if float(datos["capacidad"]) in self.falla_en:
            return 2
        n = int(datos["n"])
        k = int(round(self.prob(datos) * n))
        hist = [0] * 512
        hist[0] += n - k
        hist[min(int(math.ceil(float(datos["umbral"]))), 511)] += k
        inf, sup = wilson(k, n)
        fila = dict(backend="falso", estacion=datos["estacion"], regimen=datos["regimen"],
                    config_id=datos.get("config_id", "0"), semilla=datos.get("semilla", "0"), n=n, k=k,
                    p_hat=k / n, wilson_inf=inf, wilson_sup=sup, dias=datos.get("dias", "120"),
                    capacidad=datos["capacidad"], umbral=datos["umbral"],
                    **{p: datos[p] for p in PARAMETROS}, hilos=datos.get("hilos", "1"), procesos=1,
                    repeticion=1, calentamiento=0, schedule="", afinidad="", tiempo_s=0.001,
                    commit=env.get("PP_COMMIT", ""), cpu="falsa", nucleos_fisicos=1, nucleos_logicos=1,
                    hist512=";".join(map(str, hist)), hardware="host=falso;ram_gb=1", nodos=1,
                    distribucion="falso:1", bloques="", hilos_por_bloque="")
        salida = Path(datos["salida"])
        nuevo = not salida.exists()
        with salida.open("a", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=ENCABEZADO, lineterminator="\n")
            if nuevo:
                w.writeheader()
            w.writerow(fila)
        return 0


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ejecutar_plan(plan: list[Punto], *, salida: Path, logs: Path, manifiesto: Path, experimento: str,
                  backend: str, build_dir: Path, hilos: int, procesos: int, runner=runner_subprocess,
                  dry_run: bool = False, extra: dict | None = None) -> dict:
    """Corre los puntos pendientes del plan; agrega al CSV y actualiza el manifiesto tras cada punto."""
    salida, logs, manifiesto = Path(salida), Path(logs), Path(manifiesto)
    pend = pendientes(plan, salida)
    resumen = {"total": len(plan), "omitidos": len(plan) - len(pend), "corridos": 0, "errores": 0,
               "comandos": [comando(p, backend, build_dir, hilos, procesos, salida) for p in pend]}
    if dry_run:
        for cmd in resumen["comandos"]:
            print(shlex.join(cmd))
        print(f"[dry-run] {experimento}: {len(pend)} pendientes de {len(plan)} "
              f"({resumen['omitidos']} ya en {salida})")
        return resumen

    salida.parent.mkdir(parents=True, exist_ok=True)
    logs.mkdir(parents=True, exist_ok=True)
    manifiesto.parent.mkdir(parents=True, exist_ok=True)
    datos = json.loads(manifiesto.read_text(encoding="utf-8")) if manifiesto.exists() else {
        "experimento": experimento, "salida": salida.as_posix(), "nota": NOTA_V6, "semillas": {},
        "sesiones": [], "puntos": []}
    for p in plan:
        datos["semillas"][f"{p.estacion}/{p.regimen}"] = {"semilla": p.semilla, "config_id": p.config_id}
    env = entorno_simulador()
    sesion = {"inicio": _ahora(), "commit": env["PP_COMMIT"], "hardware": info_hardware(),
              "backend": backend, "hilos": hilos, "procesos": procesos if backend == "hibrido" else 1,
              "pendientes": len(pend), "omitidos": resumen["omitidos"], **(extra or {})}
    datos["sesiones"].append(sesion)
    log = logs / f"{experimento}_{datetime.now().strftime('%Y%m%dT%H%M%S')}.log"

    def guardar():
        manifiesto.write_text(json.dumps(datos, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    guardar()
    for i, (p, cmd) in enumerate(zip(pend, resumen["comandos"]), 1):
        antes = len(leer_resultados(salida))
        t0 = time.perf_counter()
        codigo = runner(cmd, log, env)
        dur = time.perf_counter() - t0
        ok = codigo == 0 and len(leer_resultados(salida)) == antes + 1
        resumen["corridos" if ok else "errores"] += 1
        datos["puntos"].append({"etiqueta": p.etiqueta, "estacion": p.estacion, "regimen": p.regimen,
                                "replica": p.replica, "capacidad": p.capacidad, "umbral": p.umbral,
                                "n": p.n, "semilla": p.semilla, "config_id": p.config_id,
                                "duracion_s": round(dur, 4), "codigo_salida": codigo,
                                "estado": "ok" if ok else "error", "fin": _ahora()})
        print(f"[{experimento}] {i}/{len(pend)} {p.etiqueta} {'ok' if ok else 'ERROR'} {dur:.2f} s",
              flush=True)
        guardar()
    sesion.update(fin=_ahora(), corridos=resumen["corridos"], errores=resumen["errores"],
                  log=log.as_posix())
    guardar()
    return resumen


def agregar_args_ejecucion(parser, salida: str, manifiesto: str, n_defecto: float) -> None:
    """Argumentos comunes a los scripts que corren el simulador."""
    parser.add_argument("--configs", nargs="+", type=Path,
                        help="YAML estación × régimen (por defecto config/*_normal.yaml y *_el_nino.yaml)")
    parser.add_argument("--n", type=float, default=n_defecto, help="escenarios por punto")
    parser.add_argument("--backend", choices=sorted(BINARIOS), default="openmp")
    parser.add_argument("--hilos", type=int, default=16, help="hilos por proceso")
    parser.add_argument("--procesos", type=int, default=2, help="procesos MPI (solo hibrido)")
    parser.add_argument("--build-dir", type=Path, default=Path("build-c"))
    parser.add_argument("--salida", type=Path, default=Path(salida))
    parser.add_argument("--logs", type=Path, default=Path("results/cientifico/logs"))
    parser.add_argument("--manifiesto", type=Path, default=Path(manifiesto))
    parser.add_argument("--dry-run", action="store_true", help="solo imprime los comandos pendientes")
    parser.add_argument("--runner-falso", action="store_true", help=argparse.SUPPRESS)


def runner_de(args, prob=None):
    return RunnerFalso(prob=prob) if args.runner_falso else runner_subprocess


def verificar_binario(args) -> bool:
    if args.dry_run or args.runner_falso:
        return True
    b = Path(args.build_dir) / BINARIOS[args.backend]
    if not b.exists():
        print(f"error: no existe {b}; compile con cmake (ver results/cientifico/README.md)")
        return False
    return True
