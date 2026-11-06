# /// script
# requires-python = ">=3.10"
# dependencies = ["matplotlib>=3.8"]
# ///
"""Local demo web UI: runs the real simulator (pp-g8 Docker image) and renders figures.

Usage (from the repository root, Docker Desktop running), either:
    uv run scripts/demo/servidor_demo.py          # host mode: each run starts a pp-g8 container
or, inside Docker with the backend logs visible through `docker logs`:
    docker run -d --name pp-g8-demo -p 8000:8000 -v "${PWD}:/work" -w /work pp-g8 python3 -u scripts/demo/servidor_demo.py
    docker logs -f pp-g8-demo                     # follow the backend log
    docker rm -f pp-g8-demo                       # stop it
Then open http://127.0.0.1:8000

Endpoints:
    GET  /               the page
    GET  /api/configs    available config/*.yaml files
    POST /api/simular    sequential baseline vs a parallel backend (OpenMP, MPI static,
                         MPI dynamic or hybrid) -> metrics, per-rank work and figures
    POST /api/punto      one point of the live sweep (sequential baseline or one backend, 1-5 reps)
    POST /api/openmp     official sweep figures from results/bench/*.csv (no new runs)
Nothing is written to the repository: outputs go to a temporary directory.
"""
from __future__ import annotations

import base64
import csv
import hashlib
import io
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

RAIZ = Path(__file__).resolve().parents[2]
IMAGEN = "pp-g8"
BIN = "build/docker/src/backends"
BIN_MPI = "build/docker-mpi/src/backends"
SCHEDULES = {"static", "dynamic,1", "dynamic,64"}
MODOS = {"openmp", "mpi_estatico", "mpi_dinamico", "hibrido"}
PUERTO = 8000
NUCLEOS = os.cpu_count() or 24
EN_DOCKER = Path("/.dockerenv").exists()

logging.basicConfig(level=logging.INFO, stream=sys.stdout, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("demo")

AZUL, NARANJA, TINTA, GRIS = "#2F6FB3", "#B4561A", "#13233F", "#8A94A6"
RANGO = re.compile(r"\[verif\] rango=(\d+)(?: inicio=(\d+) fin=(\d+))?(?: bloques=(\d+))?(?: hilos=(\d+))? n_local=(\d+)")


def configs() -> list[str]:
    return sorted(p.name for p in (RAIZ / "config").glob("*.yaml"))


def png(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()


def ejes(ax) -> None:
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color="#E6E2D8", lw=0.8)
    ax.set_axisbelow(True)


def leer_fila(ruta: Path) -> dict:
    with ruta.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))[-1]


def entero(d: dict, clave: str, defecto: int, lo: int, hi: int) -> int:
    v = int(d.get(clave) or defecto)
    if not lo <= v <= hi:
        raise ValueError(f"{clave} debe estar entre {lo} y {hi}")
    return v


def validar(d: dict) -> dict:
    cfg = str(d.get("config", "sintetico.yaml"))
    if cfg not in configs():
        raise ValueError(f"config desconocida: {cfg}")
    modo = str(d.get("modo", "openmp"))
    if modo not in MODOS:
        raise ValueError(f"modo inválido: {modo}")
    schedule = str(d.get("schedule", "static"))
    if schedule not in SCHEDULES:
        raise ValueError(f"schedule inválido: {schedule}")
    p = {"config": cfg, "modo": modo, "schedule": schedule,
         "n": entero(d, "n", 1_000_000, 1_000, 20_000_000),
         "semilla": entero(d, "semilla", 20261015, 0, 2**63 - 1),
         "hilos": entero(d, "hilos", 16, 1, 64),
         "procesos": entero(d, "procesos", 4, 2, 32)}
    if modo in ("mpi_estatico", "mpi_dinamico"):
        p["hilos"] = 1
    if modo == "openmp":
        p["procesos"] = 1
    extra = []
    for clave in ("capacidad", "umbral"):
        v = d.get(clave)
        if v not in (None, ""):
            x = float(v)
            if not 0 <= x <= 1000:
                raise ValueError(f"{clave} fuera de rango")
            extra += [f"--{clave}", repr(x)]
    p["extra"] = extra
    return p


def comando_paralelo(p: dict, comunes: str, salida: str) -> str:
    mpirun = f"mpirun --allow-run-as-root --oversubscribe -np {p['procesos']}"
    afin = "OMP_PROC_BIND=close OMP_PLACES=cores"
    if p["modo"] == "openmp":
        return (f"{afin} {BIN}/openmp/pp_openmp {comunes} --hilos {p['hilos']} "
                f"--schedule {p['schedule']} --salida {salida}")
    if p["modo"] == "hibrido":
        return (f"OMP_PROC_BIND=false OMP_PLACES=cores {mpirun} --bind-to none {BIN_MPI}/hybrid/pp_hibrido {comunes} --hilos {p['hilos']} "
                f"--schedule {p['schedule']} --salida {salida}")
    return f"{mpirun} {BIN_MPI}/mpi/pp_{p['modo']} {comunes} --salida {salida}"


def ejecutar(script: str, tmp: str) -> str:
    if EN_DOCKER:
        cmd = ["bash", "-c", script]
    else:
        cmd = ["docker", "run", "--rm", "--shm-size=1g", "-v", f"{RAIZ}:/work", "-v", f"{tmp}:/out",
               "-w", "/work", IMAGEN, "bash", "-c", script]
    log.info("ejecutando (%s): %s", "contenedor actual" if EN_DOCKER else "docker run", script)
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=1800, cwd=RAIZ)
    for linea in (r.stdout + r.stderr).splitlines():
        log.info("  simulador | %s", linea)
    if r.returncode != 0:
        log.error("el simulador terminó con código %d", r.returncode)
        raise RuntimeError((r.stderr or r.stdout).strip()[-1500:])
    return r.stdout


def fig_histograma(hs, hp, umbral, etiqueta, n) -> str:
    ultimo = max(i for i, v in enumerate(hs) if v) + 1
    fig, ax = plt.subplots(figsize=(7.6, 4))
    ax.bar(range(ultimo), hs[:ultimo], width=1.0, color=AZUL, alpha=0.7, label="Secuencial")
    ax.step(range(ultimo), hp[:ultimo], where="mid", color=NARANJA, lw=1.5, label=etiqueta)
    ax.axvline(umbral, color=TINTA, ls="--", lw=1.2, label=f"Umbral U = {umbral:g} mm")
    ax.set(xlabel="Agua máxima acumulada en la temporada, Amax (mm)", ylabel="Temporadas",
           title=f"Distribución de Amax · N = {n:,}".replace(",", " "))
    ax.legend(frameon=False)
    ejes(ax)
    return png(fig)


def fig_riesgo(hist, umbral, n) -> str:
    # P(Amax > u) read from the same histogram (1 mm classes): the risk for every threshold u.
    cola, acum = [], n
    for h in hist:
        acum -= h
        cola.append(acum / n)
    ultimo = next((i for i, v in enumerate(cola) if v == 0), len(cola)) + 1
    u = list(range(1, ultimo + 1))
    fig, ax = plt.subplots(figsize=(7.6, 4))
    ax.plot(u, cola[:ultimo], color=AZUL, lw=2)
    p_u = cola[int(umbral) - 1] if 1 <= int(umbral) <= len(cola) else None
    if p_u is not None:
        ax.scatter([umbral], [p_u], color=NARANJA, zorder=3)
        ax.annotate(f"U = {umbral:g} mm → {p_u:.1%}", (umbral, p_u), textcoords="offset points",
                    xytext=(10, 10), color=NARANJA, fontweight="bold")
    ax.axhline(0.10, color=GRIS, ls=":", lw=1.2)
    ax.text(u[-1], 0.105, "riesgo 10 %", color=GRIS, ha="right", va="bottom")
    ax.set(xlabel="Umbral u (mm)", ylabel="P(Amax > u)", ylim=(0, 1.02),
           title="Riesgo de inundación según el umbral (misma corrida)")
    ejes(ax)
    return png(fig)


def fig_tiempo(t1, tp, etiqueta, speedup) -> str:
    fig, ax = plt.subplots(figsize=(5.6, 4))
    barras = ax.bar(["Secuencial", etiqueta], [t1, tp], color=[AZUL, NARANJA], width=0.55)
    ax.bar_label(barras, labels=[f"{t1:.2f} s", f"{tp:.2f} s"], padding=3, fontweight="bold")
    ax.set(ylabel="Tiempo de pared (s)", title=f"Speedup = {speedup:.2f}×")
    ejes(ax)
    return png(fig)


def fig_rangos(rangos, modo) -> str:
    etiquetas = [f"R{r['rango']}" + (" (maestro)" if modo == "mpi_dinamico" and r["n_local"] == 0 else "")
                 for r in rangos]
    valores = [r["n_local"] for r in rangos]
    fig, ax = plt.subplots(figsize=(7.6, max(2.6, 0.45 * len(rangos) + 1.2)))
    barras = ax.barh(etiquetas, valores, color=NARANJA)
    textos = []
    for r in rangos:
        t = f"{r['n_local']:,}".replace(",", " ")
        if r["bloques"] is not None:
            t += f" · {r['bloques']} bloques"
        if r["hilos"] is not None:
            t += f" · {r['hilos']} hilos"
        textos.append(t)
    ax.bar_label(barras, labels=textos, padding=4)
    ax.invert_yaxis()
    ax.set(xlabel="Temporadas simuladas por el proceso", title="Trabajo por proceso MPI")
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_xlim(0, max(valores) * 1.35 if max(valores) else 1)
    return png(fig)


def simular(d: dict) -> dict:
    p = validar(d)
    log.info("simular: %s", {k: v for k, v in p.items() if k != "extra"} | {"extra": p["extra"]})
    comunes = f"--config config/{p['config']} --n {p['n']} --semilla {p['semilla']} {' '.join(p['extra'])}"
    with tempfile.TemporaryDirectory() as tmp:
        dest = tmp if EN_DOCKER else "/out"
        script = (f"{BIN}/serial/pp_serial {comunes} --salida {dest}/serial.csv && "
                  + comando_paralelo(p, comunes, f"{dest}/paralelo.csv"))
        salida = ejecutar(script, tmp)
        s, o = leer_fila(Path(tmp) / "serial.csv"), leer_fila(Path(tmp) / "paralelo.csv")

    rangos = [{"rango": int(m[1]), "inicio": int(m[2]) if m[2] else None, "fin": int(m[3]) if m[3] else None,
               "bloques": int(m[4]) if m[4] else None, "hilos": int(m[5]) if m[5] else None, "n_local": int(m[6])}
              for m in RANGO.finditer(salida)]
    hs = [int(x) for x in s["hist512"].split(";")]
    hp = [int(x) for x in o["hist512"].split(";")]
    umbral, n = float(s["umbral"]), p["n"]
    t1, tp = float(s["tiempo_s"]), float(o["tiempo_s"])
    recursos = p["procesos"] * p["hilos"]
    speedup = t1 / tp
    identico = s["k"] == o["k"] and hs == hp
    etiqueta = {"openmp": f"OpenMP {p['hilos']} hilos", "mpi_estatico": f"MPI estático {p['procesos']} proc.",
                "mpi_dinamico": f"MPI dinámico {p['procesos']} proc.",
                "hibrido": f"Híbrido {p['procesos']}×{p['hilos']}"}[p["modo"]]
    log.info("resultado: modo=%s k serial=%s k paralelo=%s identico=%s t1=%.3f s tp=%.3f s speedup=%.2fx",
             p["modo"], s["k"], o["k"], identico, t1, tp, speedup)

    def resumen(f):
        lo, hi = float(f["wilson_inf"]), float(f["wilson_sup"])
        t = float(f["tiempo_s"])
        return {"k": int(f["k"]), "p_hat": float(f["p_hat"]), "wilson": [lo, hi], "mitad": (hi - lo) / 2,
                "tiempo_s": t, "us_por_escenario": t / n * 1e6, "escenarios_s": n / t,
                "hilos": int(f["hilos"] or 1), "procesos": int(f["procesos"] or 1), "schedule": f["schedule"] or "-"}

    imagenes = {"histograma": fig_histograma(hs, hp, umbral, etiqueta, n), "riesgo": fig_riesgo(hs, umbral, n),
                "tiempo": fig_tiempo(t1, tp, etiqueta, speedup)}
    if rangos:
        imagenes["rangos"] = fig_rangos(rangos, p["modo"])
    return {"parametros": {k: v for k, v in p.items() if k != "extra"}
            | {"capacidad": float(s["capacidad"]), "umbral": umbral, "cpu": s["cpu"], "nucleos": NUCLEOS},
            "etiqueta": etiqueta, "serial": resumen(s), "paralelo": resumen(o), "identico": identico,
            "speedup": speedup, "recursos": recursos, "eficiencia": speedup / recursos,
            "sobresuscrito": recursos > NUCLEOS, "rangos": rangos, "imagenes": imagenes}


def punto(d: dict) -> dict:
    """One point of the live sweep: `reps` runs of one backend (or the sequential baseline)."""
    serial = d.get("modo") == "serial"
    p = validar({**d, "modo": "openmp" if serial else d.get("modo", "openmp")})
    reps = entero(d, "reps", 1, 1, 5)
    comunes = f"--config config/{p['config']} --n {p['n']} --semilla {p['semilla']} {' '.join(p['extra'])}"
    with tempfile.TemporaryDirectory() as tmp:
        destino = f"{tmp if EN_DOCKER else '/out'}/punto.csv"
        uno = f"{BIN}/serial/pp_serial {comunes} --salida {destino}" if serial else comando_paralelo(p, comunes, destino)
        log.info("barrido: %s unidades=%d reps=%d", "serial" if serial else p["modo"],
                 1 if serial else p["procesos"] * p["hilos"], reps)
        ejecutar(f"for i in $(seq {reps}); do {uno} || exit 1; done", tmp)
        with (Path(tmp) / "punto.csv").open(encoding="utf-8") as f:
            filas = list(csv.DictReader(f))
    tiempos = [float(f["tiempo_s"]) for f in filas]
    media = sum(tiempos) / len(tiempos)
    desv = (sum((t - media) ** 2 for t in tiempos) / (len(tiempos) - 1)) ** 0.5 if len(tiempos) > 1 else 0.0
    estables = len({(f["k"], f["hist512"]) for f in filas}) == 1
    return {"modo": "serial" if serial else p["modo"], "hilos": 1 if serial else p["hilos"],
            "procesos": 1 if serial else p["procesos"], "unidades": 1 if serial else p["procesos"] * p["hilos"],
            "k": int(filas[0]["k"]), "huella": hashlib.sha1(filas[0]["hist512"].encode()).hexdigest()[:12],
            "estable": estables, "tiempos": tiempos, "media": media, "desv": desv}


def graficos_openmp() -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        cmd = [sys.executable, str(RAIZ / "scripts/bench/graficar_openmp_ashley.py"),
               "--entrada", str(RAIZ / "results/bench/openmp.csv"),
               "--t1-csv", str(RAIZ / "results/bench/secuencial_t1.csv"),
               "--agregado", str(Path(tmp) / "agregado.csv"), "--figuras", tmp]
        log.info("graficos_openmp: %s", " ".join(cmd[1:]))
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300, cwd=RAIZ)
        for linea in (r.stdout + r.stderr).splitlines():
            log.info("  graficar | %s", linea)
        if r.returncode != 0:
            log.error("graficar terminó con código %d", r.returncode)
            raise RuntimeError((r.stderr or r.stdout).strip()[-1500:])
        imgs = {p.stem: base64.b64encode(p.read_bytes()).decode() for p in sorted(Path(tmp).glob("*.png"))}
    if not imgs:
        raise RuntimeError("el script no generó imágenes")
    return {"imagenes": imgs, "fuente": "results/bench/openmp.csv + secuencial_t1.csv (N = 2·10⁷, 5 repeticiones)"}


PAGINA = r"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><title>Simulador G8</title>
<style>
/* Layout: sticky control panel beside a results column; one column under 900px. Tokens drive both themes. */
:root{--bg:#F6F4EF;--surface:#FFFFFF;--fg:#13233F;--muted:#4A5568;--line:#DCD7CC;--grid:#E6E2D8;--accent:#2F6FB3;--accent-fg:#FFFFFF;--accent-soft:#EAF0F7;--warm:#B4561A;
--head:#13233F;--head-fg:#F6F4EF;--head-muted:#C9D3E3;--head-line:#24375A;--ok:#1D6B3A;--ok-soft:#EEF7F1;--bad:#A12020;--bad-soft:#FBEEEE;--warn:#7A3E0E;--warn-soft:#FFF4E5;--ideal:#8A94A6;--chip:#EAF0F7;--track:#E6E2D8}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){--bg:#0F1726;--surface:#172236;--fg:#E7ECF4;--muted:#A9B4C6;--line:#2B3A55;--grid:#24324A;--accent:#6FA3E0;--accent-fg:#0B1220;--accent-soft:#1E3150;--warm:#E8964A;
--head:#0B1220;--head-fg:#E7ECF4;--head-muted:#A9B4C6;--head-line:#1E2B44;--ok:#5CC48A;--ok-soft:#14301F;--bad:#F08A8A;--bad-soft:#3A1A1A;--warn:#F2C58A;--warn-soft:#3A2A14;--ideal:#7C889C;--chip:#1E3150;--track:#24324A;color-scheme:dark}}
:root[data-theme="dark"]{--bg:#0F1726;--surface:#172236;--fg:#E7ECF4;--muted:#A9B4C6;--line:#2B3A55;--grid:#24324A;--accent:#6FA3E0;--accent-fg:#0B1220;--accent-soft:#1E3150;--warm:#E8964A;
--head:#0B1220;--head-fg:#E7ECF4;--head-muted:#A9B4C6;--head-line:#1E2B44;--ok:#5CC48A;--ok-soft:#14301F;--bad:#F08A8A;--bad-soft:#3A1A1A;--warn:#F2C58A;--warn-soft:#3A2A14;--ideal:#7C889C;--chip:#1E3150;--track:#24324A;color-scheme:dark}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;font-family:system-ui,"Segoe UI",Roboto,Arial,sans-serif;background:var(--bg);color:var(--fg);line-height:1.45}
.gutter{padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px))}
header{background:var(--head);color:var(--head-fg);padding-block:16px}
header h1{margin:0;font-size:1.35rem;text-wrap:balance}header p{margin:4px 0 0;color:var(--head-muted);font-size:.9rem;max-width:70ch}
nav{display:flex;gap:4px;background:var(--head);border-top:1px solid var(--head-line);overflow-x:auto;scrollbar-width:none}
nav button{background:transparent;color:var(--head-muted);border-radius:8px 8px 0 0;padding:10px 18px;white-space:nowrap;flex:none}
nav button.on{background:var(--bg);color:var(--fg)}
main{max-width:1320px;margin:0 auto;padding-block:20px;display:grid;grid-template-columns:minmax(0,330px) minmax(0,1fr);gap:20px;align-items:start}
main>section,main>aside{min-width:0}
@media(max-width:900px){main{grid-template-columns:minmax(0,1fr)}aside.card{position:static!important}}
.card{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:18px}
aside.card{position:sticky;top:12px}
h2{font-size:1.1rem;margin:0 0 12px;text-wrap:balance}
h3{font-size:.75rem;text-transform:uppercase;letter-spacing:.08em;color:var(--warm);margin:14px 0 8px}h3:first-child{margin-top:0}
label{display:flex;flex-direction:column;font-size:.82rem;font-weight:600;gap:5px;margin-bottom:10px}
label small,.nota{font-weight:400;color:var(--muted);font-size:.78rem}
.nota{margin:-4px 0 10px}
input,select{font:inherit;font-size:1rem;padding:9px;border:1px solid var(--line);border-radius:8px;background:var(--surface);color:var(--fg);width:100%;min-height:44px}
input:focus-visible,select:focus-visible,button:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.fila{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}
.modos{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px;margin-bottom:10px}
.modos button{background:var(--surface);color:var(--fg);border:1px solid var(--line);font-size:.85rem;padding:8px}
.modos button.on{background:var(--fg);color:var(--bg);border-color:var(--fg)}
.chips{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:10px}.chips button{font-size:.8rem;padding:6px 12px;background:var(--chip);color:var(--fg);min-height:36px}
.chips button.on{background:var(--accent);color:var(--accent-fg)}
button{font:inherit;font-weight:600;padding:10px 16px;border:0;border-radius:8px;cursor:pointer;color:var(--accent-fg);background:var(--accent);min-height:44px}
button:disabled{opacity:.55;cursor:not-allowed}
.acciones{display:flex;gap:8px;margin-top:12px}.acciones button{flex:1;font-size:1rem;padding:12px}
button.alto{background:var(--bad);color:var(--surface)}
.aviso{font-size:.82rem;padding:8px 10px;border-radius:8px;background:var(--warn-soft);color:var(--warn);margin:6px 0 10px}
#estado{font-size:.9rem;color:var(--muted);margin:10px 0 0;min-height:20px}.err{color:var(--bad)!important;white-space:pre-wrap;overflow-wrap:anywhere}
.spin{display:inline-block;width:14px;height:14px;border:2px solid var(--line);border-top-color:var(--accent);border-radius:50%;animation:g 1s linear infinite;vertical-align:-2px;margin-right:6px}
@keyframes g{to{transform:rotate(360deg)}}
.vacio{color:var(--muted);text-align:center;padding:48px 12px;line-height:1.6}
code{font-family:ui-monospace,Consolas,monospace;font-size:.9em}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;margin-bottom:16px}
.kpi{border:1px solid var(--line);border-radius:10px;padding:12px;min-width:0}.kpi b{display:block;font-size:1.45rem;font-variant-numeric:tabular-nums}
.kpi span{font-size:.75rem;color:var(--muted)}.kpi.ok{border-color:var(--ok);background:var(--ok-soft)}.kpi.ok b{color:var(--ok)}
.kpi.mal{border-color:var(--bad);background:var(--bad-soft)}.kpi.mal b{color:var(--bad)}
table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums;font-size:.88rem}
th,td{padding:7px 9px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap}
th:first-child,td:first-child{text-align:left}th{background:var(--head);color:var(--head-fg);font-weight:600}
tr.activo td{background:var(--accent-soft)}.tabla{overflow-x:auto;margin-bottom:16px;-webkit-overflow-scrolling:touch}
.imgs{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,380px),1fr));gap:14px}.imgs figure{margin:0;min-width:0}
.imgs img{width:100%;max-width:100%;height:auto;border:1px solid var(--line);border-radius:8px;background:#FFFFFF}
.imgs svg{width:100%;max-width:100%;height:auto;border:1px solid var(--line);border-radius:8px;background:var(--surface)}
.imgs figcaption{font-size:.8rem;color:var(--muted);margin-top:4px}
.ch-grid{stroke:var(--grid)}.ch-axis{fill:var(--muted)}.ch-x{fill:var(--fg)}.ch-val{fill:var(--fg);font-weight:600}
.ch-ideal{stroke:var(--ideal);fill:none}.ch-ideal-t{fill:var(--ideal)}.ch-ref{stroke:var(--accent)}.ch-ref-t{fill:var(--accent)}
.ch-line{stroke:var(--warm);fill:none}.ch-mark{fill:var(--warm)}.ch-err{stroke:var(--fg)}
.barra{height:8px;background:var(--track);border-radius:4px;overflow:hidden;margin:6px 0 14px}.barra div{height:100%;background:var(--accent);transition:width .3s}
.pill{display:inline-block;padding:2px 8px;border-radius:10px;font-size:.75rem;font-weight:600}
.pill.esp{background:var(--track);color:var(--muted)}.pill.run{background:var(--accent-soft);color:var(--accent)}.pill.ok{background:var(--ok-soft);color:var(--ok)}.pill.mal{background:var(--bad-soft);color:var(--bad)}
.oculto{display:none!important}
@media(max-width:520px){header h1{font-size:1.1rem}h2{font-size:1rem}.kpi b{font-size:1.2rem}.card{padding:14px}.acciones{position:sticky;bottom:0;background:var(--surface);padding-block:8px;margin-inline:-14px;padding-inline:14px;border-top:1px solid var(--line)}}
@media (prefers-reduced-motion: reduce){.spin{animation:none}.barra div{transition:none}}
</style></head><body>
<header class="gutter"><h1>Simulador Monte Carlo de riesgo de inundación · G8</h1>
<p>Ejecuta el programa real (imagen Docker pp-g8) y compara la versión secuencial con la paralela, con la misma semilla.</p></header>
<nav class="gutter"><button data-v="sim" class="on">Simular</button><button data-v="bar">Barrido en vivo</button><button data-v="omp">Barrido oficial OpenMP</button></nav>
<main id="vista" class="gutter">
<aside class="card" id="panel"><form id="f" onsubmit="return false">
<h3>Versión paralela</h3>
<div class="modos" id="modos">
<button type="button" data-m="openmp" class="on">OpenMP</button><button type="button" data-m="mpi_estatico">MPI estático</button>
<button type="button" data-m="mpi_dinamico">MPI dinámico</button><button type="button" data-m="hibrido">Híbrido MPI+OpenMP</button></div>
<input type="hidden" name="modo" value="openmp">
<div class="fila"><label id="lHilos">Hilos<span class="nota" id="nHilos"></span><input name="hilos" type="number" value="16" min="1" max="64"></label>
<label id="lProc" class="oculto">Procesos MPI<input name="procesos" type="number" value="4" min="2" max="32"></label></div>
<div id="bloqueBarrido" class="oculto">
<label>Puntos del barrido<small id="sPuntos">hilos a probar, separados por coma</small><input name="puntos" value="1,2,4,8,16"></label>
<div class="chips" id="chipsPuntos"><button type="button" data-p="1,2,4,8,16">1–16</button><button type="button" data-p="1,2,4,8,16,24">1–24</button><button type="button" data-p="2,4,8,16">2–16</button></div>
<label>Repeticiones por punto<select name="reps"><option>1</option><option selected>3</option><option>5</option></select></label>
</div>
<label id="lSch">Reparto (schedule)<select name="schedule"><option>static</option><option>dynamic,1</option><option>dynamic,64</option></select></label>
<div id="sobre" class="aviso oculto"></div>
<p class="nota" id="nModo"></p>
<h3>Modelo</h3>
<label>Estación y régimen<select name="config" id="config"></select></label>
<div class="fila"><label>Capacidad C<small>mm/día · vacío = config</small><input name="capacidad" type="number" step="any"></label>
<label>Umbral U<small>mm · vacío = config</small><input name="umbral" type="number" step="any"></label></div>
<h3>Carga</h3>
<div class="fila"><label>N escenarios<input name="n" type="number" value="1000000" min="1000" max="20000000" step="1000"></label>
<label>Semilla<input name="semilla" type="number" value="20261015" min="0"></label></div>
<div class="chips" id="chipsN"><button type="button" data-n="100000">Rápida 10⁵</button><button type="button" data-n="1000000" class="on">Demo 10⁶</button><button type="button" data-n="5000000">5·10⁶</button><button type="button" data-n="20000000">Oficial 2·10⁷</button></div>
<p class="nota" id="nEstim"></p>
<div class="acciones"><button id="bGo" type="submit">Simular</button><button id="bStop" type="button" class="alto oculto">Detener</button></div>
<p id="estado" role="status" aria-live="polite"></p></form></aside>
<section id="vSim">
<div class="card" id="res"><div class="vacio">Elegí la versión paralela y los parámetros, y presioná <b>Simular</b>.<br>Primero corre la versión secuencial y después la paralela, con la misma semilla.<br><small>Atajo: Ctrl + Enter.</small></div></div>
<div class="card" id="hist" style="margin-top:20px" hidden><h2>Historial de esta sesión</h2><div class="tabla"><table id="tHist"></table></div></div>
</section>
<section id="vBar" class="oculto">
<div class="card" id="bar"><div class="vacio">El barrido mide la versión secuencial (T1) y después cada punto, uno por uno.<br>Los gráficos se actualizan en vivo a medida que termina cada punto, y cada punto se valida contra el secuencial (V1).</div></div>
</section>
<section id="vOmp" class="oculto">
<div class="card" id="omp"><div class="vacio">Gráficos generados con <code>graficar_openmp_ashley.py</code> a partir de los CSV oficiales (N = 2·10⁷, 5 repeticiones).<br><br><button id="bOmp" type="button">Generar gráficos del barrido oficial</button></div></div>
</section></main>
<script>
const $=s=>document.querySelector(s),$$=s=>[...document.querySelectorAll(s)],f=$('#f'),est=$('#estado'),NUC=24;
let historial=[],vista='sim',detener=false,ocupado=false;
const nf=(x,d=0)=>Number(x).toLocaleString('es',{minimumFractionDigits:d,maximumFractionDigits:d});
const nombre=c=>c.replace('.yaml','').replaceAll('_',' ');
fetch('/api/configs').then(r=>r.json()).then(cs=>{$('#config').innerHTML=cs.map(c=>`<option value="${c}" ${c==='sintetico.yaml'?'selected':''}>${nombre(c)}</option>`).join('')});
const ETQ={openmp:'OpenMP',mpi_estatico:'MPI estático',mpi_dinamico:'MPI dinámico',hibrido:'Híbrido'};
const NOTA={openmp:'Hilos en un solo proceso; memoria compartida y reducción al final.',
 mpi_estatico:'Cada proceso recibe un bloque contiguo de escenarios decidido antes de empezar.',
 mpi_dinamico:'El rango 0 es maestro: reparte bloques a pedido y no simula. Con p procesos trabajan p − 1.',
 hibrido:'p procesos MPI con h hilos OpenMP cada uno (p × h unidades).'};
function ui(){const m=f.modo.value,bar=vista==='bar',mpi=m.startsWith('mpi_');
 $$('#modos button').forEach(b=>b.classList.toggle('on',b.dataset.m===m));
 $('#lHilos').classList.toggle('oculto',mpi||(bar&&m==='openmp'));
 $('#lProc').classList.toggle('oculto',m==='openmp'||bar);
 $('#lSch').classList.toggle('oculto',mpi);
 $('#bloqueBarrido').classList.toggle('oculto',!bar);
 $('#nHilos').textContent=m==='hibrido'?'por proceso':'';
 $('#sPuntos').textContent=m==='openmp'?'hilos a probar, separados por coma':m==='hibrido'?'procesos a probar (con los hilos por proceso de arriba)':'procesos a probar (mínimo 2)';
 $('#nModo').textContent=NOTA[m];$('#panel').classList.toggle('oculto',vista==='omp');
 $('#bGo').textContent=bar?'Iniciar barrido':'Simular';$('#vista').style.gridTemplateColumns=vista==='omp'?'1fr':'';
 const h=mpi?1:+f.hilos.value,p=m==='openmp'?1:+f.procesos.value,maxp=Math.max(...puntos());
 const r=bar?(m==='openmp'?maxp:maxp*(m==='hibrido'?h:1)):h*p,a=$('#sobre');
 a.classList.toggle('oculto',r<=NUC);a.textContent=`Hasta ${r} unidades de ejecución sobre ${NUC} núcleos: habrá sobresuscripción y la eficiencia bajará.`;
 const n=+f.n.value,t1=n*3e-6;$('#nEstim').textContent=`Secuencial estimado: ≈ ${t1<1?nf(t1,2):nf(t1,0)} s (3 µs por escenario).`;
 $$('#chipsN button').forEach(b=>b.classList.toggle('on',+b.dataset.n===n));
 $$('#chipsPuntos button').forEach(b=>b.classList.toggle('on',b.dataset.p===f.puntos.value.replace(/\s/g,'')));}
function puntos(){return [...new Set(f.puntos.value.split(',').map(x=>parseInt(x)).filter(x=>x>0&&x<=64))].sort((a,b)=>a-b)}
$$('#modos button').forEach(b=>b.onclick=()=>{if(!ocupado){f.modo.value=b.dataset.m;
 if(b.dataset.m.startsWith('mpi_')&&f.puntos.value.startsWith('1,'))f.puntos.value='2,4,8,16';ui()}});
$$('#chipsN button').forEach(b=>b.onclick=()=>{f.n.value=b.dataset.n;ui()});
$$('#chipsPuntos button').forEach(b=>b.onclick=()=>{f.puntos.value=b.dataset.p;ui()});
f.oninput=ui;
$$('nav button').forEach(b=>b.onclick=()=>{if(ocupado)return;vista=b.dataset.v;$$('nav button').forEach(x=>x.classList.toggle('on',x===b));
 $('#vSim').classList.toggle('oculto',vista!=='sim');$('#vBar').classList.toggle('oculto',vista!=='bar');$('#vOmp').classList.toggle('oculto',vista!=='omp');ui()});
document.addEventListener('keydown',e=>{if(e.ctrlKey&&e.key==='Enter'&&!ocupado&&vista!=='omp')$('#bGo').click()});
function bloquear(on){ocupado=on;$$('button').forEach(b=>{if(b.id!=='bStop')b.disabled=on});$('#bStop').classList.toggle('oculto',!(on&&vista==='bar'))}
async function post(url,body){const r=await fetch(url,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body||{})});
 const j=await r.json();if(!r.ok)throw new Error(j.error||r.statusText);return j}
function reloj(texto){const t0=performance.now();const id=setInterval(()=>{est.className='';est.innerHTML=`<span class="spin"></span>${texto()} · ${((performance.now()-t0)/1000).toFixed(1)} s`},100);
 return {fin:()=>{clearInterval(id);return (performance.now()-t0)/1000}}}
const kpi=(v,t,c='')=>`<div class="kpi ${c}"><b>${v}</b><span>${t}</span></div>`;
const fig=(b,alt,cap)=>b?`<figure><img alt="${alt}" src="data:image/png;base64,${b}"><figcaption>${cap}</figcaption></figure>`:'';
function datos(){return Object.fromEntries(new FormData(f))}

/* ---------- Simular ---------- */
async function simular(){bloquear(true);const r=reloj(()=>'Ejecutando secuencial y paralelo en Docker');
 try{const j=await post('/api/simular',datos());const t=r.fin();est.textContent=`Listo en ${nf(t,1)} s (incluye arranque y gráficos).`;pintarSim(j)}
 catch(e){r.fin();est.className='err';est.textContent='Error: '+e.message}finally{bloquear(false)}}
function pintarSim(j){const p=j.parametros,s=j.serial,q=j.paralelo;
 const fila=(n,x)=>`<tr><td>${n}</td><td>${x.procesos}</td><td>${x.hilos}</td><td>${x.schedule}</td><td>${nf(x.k)}</td><td>${nf(x.p_hat,6)}</td><td>± ${nf(x.mitad,6)}</td><td>${nf(x.tiempo_s,3)} s</td><td>${nf(x.us_por_escenario,3)}</td><td>${nf(x.escenarios_s/1e6,2)}</td></tr>`;
 const rangos=j.rangos.length?`<h3>Trabajo por proceso</h3><div class="tabla"><table><tr><th>Rango</th><th>Temporadas</th><th>% del total</th><th>${p.modo==='mpi_dinamico'?'Bloques':'Intervalo [inicio, fin)'}</th></tr>${j.rangos.map(r=>`<tr><td>R${r.rango}${p.modo==='mpi_dinamico'&&r.n_local===0?' · maestro':''}</td><td>${nf(r.n_local)}</td><td>${nf(100*r.n_local/p.n,1)} %</td><td>${r.bloques!==null?nf(r.bloques)+(r.n_local===0?' repartidos':' recibidos'):`[${nf(r.inicio)}, ${nf(r.fin)})`}</td></tr>`).join('')}</table></div>`:'';
 $('#res').innerHTML=`<h2>${j.etiqueta} · ${nombre(p.config)} · C = ${p.capacidad} mm/día · U = ${p.umbral} mm · N = ${nf(p.n)}</h2>
 <div class="kpis">${kpi(j.identico?'Idéntico':'Distinto','k e histograma vs secuencial (V1)',j.identico?'ok':'mal')}
 ${kpi(nf(q.p_hat*100,2)+' %','probabilidad de inundación p̂')}${kpi('± '+nf(q.mitad*100,3)+' pp','mitad del IC de Wilson 95 %')}
 ${kpi(nf(j.speedup,2)+'×','speedup T1 / Tp')}${kpi(nf(j.eficiencia*100,0)+' %',`eficiencia (${j.recursos} unidades)`)}
 ${kpi(nf(q.escenarios_s/1e6,1)+' M/s','escenarios por segundo')}</div>
 ${j.sobresuscrito?`<p class="aviso">Corrida sobresuscrita: ${j.recursos} unidades sobre ${p.nucleos} núcleos.</p>`:''}
 <div class="tabla"><table><tr><th>Versión</th><th>Proc.</th><th>Hilos</th><th>Schedule</th><th>k</th><th>p̂</th><th>Wilson ±</th><th>Tiempo</th><th>µs/esc.</th><th>M esc./s</th></tr>${fila('Secuencial',s)}${fila(j.etiqueta,q)}</table></div>
 ${rangos}<div class="imgs">${fig(j.imagenes.histograma,'Histograma de Amax','Histogramas superpuestos: si coinciden, el paralelismo no cambió el resultado.')}
 ${fig(j.imagenes.riesgo,'Curva de riesgo','P(Amax > u) para todo umbral u, leída del mismo histograma.')}
 ${fig(j.imagenes.tiempo,'Tiempo','Tiempo de pared medido por cada ejecutable.')}
 ${fig(j.imagenes.rangos,'Trabajo por proceso','Temporadas que simuló cada proceso MPI.')}</div>
 <p class="nota" style="margin-top:10px">CPU: ${p.cpu} · semilla ${p.semilla} · corrida única de demostración.</p>`;
 historial.unshift({e:j.etiqueta,c:nombre(p.config),n:p.n,k:q.k,ok:j.identico,t1:s.tiempo_s,tp:q.tiempo_s,sp:j.speedup,ef:j.eficiencia});
 $('#hist').hidden=false;$('#tHist').innerHTML=`<tr><th>Versión</th><th>Config</th><th>N</th><th>k</th><th>V1</th><th>T1</th><th>Tp</th><th>Speedup</th><th>Eficiencia</th></tr>`+
 historial.map(h=>`<tr><td>${h.e}</td><td>${h.c}</td><td>${nf(h.n)}</td><td>${nf(h.k)}</td><td>${h.ok?'sí':'NO'}</td><td>${nf(h.t1,2)} s</td><td>${nf(h.tp,2)} s</td><td>${nf(h.sp,2)}×</td><td>${nf(h.ef*100,0)} %</td></tr>`).join('')}

/* ---------- Barrido en vivo ---------- */
function svgGrafico({xs,ys,err,ideal,ymax,ylab,xlab,fmt,tipo,ref,refLab}){
 const W=600,H=320,L=60,R=18,T=22,B=48,w=W-L-R,h=H-T-B,n=xs.length;
 const X=i=>L+(n===1?w/2:(i+0.5)*w/n),Y=v=>T+h-(Math.min(v,ymax)/ymax)*h,bw=Math.min(56,w/n*0.55);
 let s=`<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${ylab}" font-family="system-ui,Segoe UI,Arial" font-size="13">`;
 for(let i=0;i<=4;i++){const v=ymax*i/4,y=Y(v);s+=`<line class="ch-grid" x1="${L}" x2="${W-R}" y1="${y}" y2="${y}"/><text class="ch-axis" x="${L-8}" y="${y+4}" text-anchor="end">${fmt(v)}</text>`}
 xs.forEach((x,i)=>{s+=`<text class="ch-x" x="${X(i)}" y="${H-B+18}" text-anchor="middle">${x}</text>`});
 s+=`<text class="ch-axis" x="${L+w/2}" y="${H-8}" text-anchor="middle">${xlab}</text><text class="ch-axis" transform="translate(14 ${T+h/2}) rotate(-90)" text-anchor="middle">${ylab}</text>`;
 if(ref!=null){const y=Y(ref);s+=`<line class="ch-ref" x1="${L}" x2="${W-R}" y1="${y}" y2="${y}" stroke-dasharray="5 4"/><text class="ch-ref-t" x="${W-R}" y="${y-6}" text-anchor="end">${refLab}</text>`}
 if(ideal){s+=`<polyline class="ch-ideal" stroke-dasharray="6 5" stroke-width="1.5" points="${xs.map((x,i)=>`${X(i)},${Y(ideal[i])}`).join(' ')}"/>`;
  s+=`<text class="ch-ideal-t" x="${X(n-1)}" y="${Y(ideal[n-1])-8}" text-anchor="end">ideal</text>`}
 if(tipo==='barra'){ys.forEach((v,i)=>{if(v==null)return;const y=Y(v);s+=`<rect class="ch-mark" x="${X(i)-bw/2}" y="${y}" width="${bw}" height="${T+h-y}" rx="3"/>`;
  if(err&&err[i]){s+=`<line class="ch-err" x1="${X(i)}" x2="${X(i)}" y1="${Y(v+err[i])}" y2="${Y(Math.max(0,v-err[i]))}"/>`}
  s+=`<text class="ch-val" x="${X(i)}" y="${Math.max(T+10,y-6)}" text-anchor="middle">${fmt(v)}</text>`})}
 else{const pts=ys.map((v,i)=>v==null?null:`${X(i)},${Y(v)}`).filter(Boolean);
  if(pts.length>1)s+=`<polyline class="ch-line" stroke-width="2.5" points="${pts.join(' ')}"/>`;
  ys.forEach((v,i)=>{if(v==null)return;s+=`<circle class="ch-mark" cx="${X(i)}" cy="${Y(v)}" r="5"/><text class="ch-val" x="${X(i)}" y="${Math.max(T+10,Y(v)-10)}" text-anchor="middle">${fmt(v)}</text>`})}
 return s+'</svg>'}
async function barrido(){const d=datos(),m=d.modo,pts=puntos().filter(x=>m==='openmp'||x>=2);
 if(!pts.length){est.className='err';est.textContent='Indicá al menos un punto válido.';return}
 const unid=x=>m==='openmp'?x:m==='hibrido'?x*(+d.hilos):x;
 const filas=[{et:'Secuencial (T1)',body:{...d,modo:'serial'},u:1}].concat(pts.map(x=>({et:m==='openmp'?`${x} hilos`:m==='hibrido'?`${x} proc. × ${d.hilos} hilos`:`${x} procesos`,
  body:{...d,...(m==='openmp'?{hilos:x}:{procesos:x})},u:unid(x),x})));
 const total=filas.length;let hechos=0,t1=null,ref=null;detener=false;bloquear(true);const reloj0=performance.now();
 const xs=pts.map(x=>m==='hibrido'?`${x}×${d.hilos}`:String(x));
 const ideal=pts.map(x=>m==='mpi_dinamico'?x-1:unid(x));
 const pintar=()=>{const sp=filas.slice(1).map(r=>r.res&&t1?t1/r.res.media:null),ef=filas.slice(1).map((r,i)=>sp[i]!=null?sp[i]/r.u:null),tp=filas.slice(1).map(r=>r.res?r.res.media:null);
  const ymax=Math.max(...ideal,...sp.filter(v=>v!=null))*1.12||1,okAll=filas.filter(r=>r.res).every(r=>r.v1!==false);
  const mejor=sp.reduce((a,v,i)=>v!=null&&(a<0||v>sp[a])?i:a,-1);
  $('#bar').innerHTML=`<h2>Barrido en vivo · ${ETQ[m]}${m==='hibrido'?` (${d.hilos} hilos por proceso)`:''} · ${nombre(d.config)} · N = ${nf(+d.n)} · ${d.reps} rep.</h2>
  <div class="barra"><div style="width:${100*hechos/total}%"></div></div>
  <div class="kpis">${kpi(t1?nf(t1,2)+' s':'—','T1 secuencial (media)')}
  ${kpi(mejor>=0?nf(sp[mejor],2)+'×':'—',mejor>=0?`mejor speedup (${xs[mejor]})`:'mejor speedup')}
  ${kpi(mejor>=0?nf(ef[mejor]*100,0)+' %':'—','eficiencia en ese punto')}
  ${kpi(filas.some(r=>r.res)?(okAll?'Idéntico':'Distinto'):'—','V1 en todos los puntos',filas.some(r=>r.res)?(okAll?'ok':'mal'):'')}</div>
  <div class="tabla"><table><tr><th>Punto</th><th>Unidades</th><th>Estado</th><th>Tiempo medio</th><th>Desv.</th><th>Speedup</th><th>Eficiencia</th><th>k</th><th>V1</th></tr>
  ${filas.map((r,i)=>{const e=r.err?'<span class="pill mal">error</span>':r.res?'<span class="pill ok">listo</span>':r.run?'<span class="pill run">ejecutando…</span>':'<span class="pill esp">en cola</span>';
   const s=i>0&&r.res&&t1?t1/r.res.media:null;
   return `<tr class="${r.run?'activo':''}"><td>${r.et}</td><td>${r.u}</td><td>${e}</td><td>${r.res?nf(r.res.media,3)+' s':''}</td><td>${r.res&&r.res.tiempos.length>1?'± '+nf(r.res.desv,3):''}</td><td>${s!=null?nf(s,2)+'×':''}</td><td>${s!=null?nf(100*s/r.u,0)+' %':''}</td><td>${r.res?nf(r.res.k):''}</td><td>${r.res?(i===0?'referencia':(r.v1?'sí':'NO')):''}</td></tr>`}).join('')}</table></div>
  <div class="imgs"><figure>${svgGrafico({xs,ys:sp,ideal,ymax,ylab:'Speedup T1 / Tp',xlab:m==='openmp'?'Hilos':'Procesos',fmt:v=>nf(v,1)})}<figcaption>Speedup medido frente al ideal${m==='mpi_dinamico'?' (p − 1: el maestro no simula)':''}.</figcaption></figure>
  <figure>${svgGrafico({xs,ys:ef.map(v=>v==null?null:v*100),ymax:110,ylab:'Eficiencia (%)',xlab:m==='openmp'?'Hilos':'Procesos',fmt:v=>nf(v,0),tipo:'barra',ref:100,refLab:'100 %'})}<figcaption>Eficiencia = speedup / unidades de ejecución.</figcaption></figure>
  <figure>${svgGrafico({xs,ys:tp,err:filas.slice(1).map(r=>r.res?r.res.desv:null),ymax:(t1||Math.max(...tp.filter(v=>v!=null),1))*1.15,ylab:'Tiempo (s)',xlab:m==='openmp'?'Hilos':'Procesos',fmt:v=>nf(v,v<10?2:1),tipo:'barra',ref:t1,refLab:t1?`T1 = ${nf(t1,2)} s`:''})}<figcaption>Tiempo medio por punto (barra de error = desviación estándar).</figcaption></figure></div>`};
 pintar();
 for(const r of filas){if(detener)break;r.run=true;pintar();
  const rel=reloj(()=>`Punto ${hechos+1} de ${total}: ${r.et}`);
  try{r.res=await post('/api/punto',r.body);if(r.u===1&&!r.x){t1=r.res.media;ref=r.res}else r.v1=ref&&r.res.k===ref.k&&r.res.huella===ref.huella&&r.res.estable}
  catch(e){r.err=e.message;rel.fin();r.run=false;est.className='err';est.textContent='Error: '+e.message;pintar();break}
  rel.fin();r.run=false;hechos++;pintar()}
 const t=(performance.now()-reloj0)/1000;bloquear(false);
 if(!est.classList.contains('err'))est.textContent=detener?`Barrido detenido tras ${hechos} de ${total} puntos (${nf(t,1)} s).`:`Barrido completo: ${total} puntos en ${nf(t,1)} s.`}
$('#bStop').onclick=()=>{detener=true;$('#bStop').disabled=true;est.textContent='Deteniendo al terminar el punto actual…'};
$('#bGo').onclick=()=>{if(ocupado)return;$('#bStop').disabled=false;vista==='bar'?barrido():simular()};

/* ---------- Barrido oficial ---------- */
$('#bOmp').onclick=async()=>{bloquear(true);const r=reloj(()=>'Generando gráficos');
 try{const j=await post('/api/openmp');r.fin();est.textContent='';
  $('#omp').innerHTML=`<h2>Barrido oficial OpenMP</h2><p class="nota">Fuente: ${j.fuente}</p><div class="imgs">${Object.entries(j.imagenes).map(([n,b])=>fig(b,n,n.replace('openmp_',''))).join('')}</div>`}
 catch(e){r.fin();$('#omp').insertAdjacentHTML('beforeend',`<p class="err">Error: ${e.message}</p>`)}finally{bloquear(false)}};
ui();
</script></body></html>"""


class Manejador(BaseHTTPRequestHandler):
    def _json(self, codigo: int, obj) -> None:
        cuerpo = json.dumps(obj).encode()
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def do_GET(self):
        if self.path == "/":
            cuerpo = PAGINA.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(cuerpo)))
            self.end_headers()
            self.wfile.write(cuerpo)
        elif self.path == "/api/configs":
            self._json(200, configs())
        else:
            self._json(404, {"error": "no encontrado"})

    def do_POST(self):
        largo = int(self.headers.get("Content-Length") or 0)
        try:
            datos = json.loads(self.rfile.read(largo) or b"{}")
            if self.path == "/api/simular":
                self._json(200, simular(datos))
            elif self.path == "/api/punto":
                self._json(200, punto(datos))
            elif self.path == "/api/openmp":
                self._json(200, graficos_openmp())
            else:
                self._json(404, {"error": "no encontrado"})
        except (ValueError, RuntimeError, subprocess.TimeoutExpired) as e:
            log.error("%s %s -> %s", self.path, type(e).__name__, e)
            self._json(400, {"error": str(e)})

    def log_message(self, fmt, *args):
        log.info("http %s | %s", self.client_address[0], fmt % args)


def main() -> None:
    # Inside a container the port must listen on all interfaces so `-p 8000:8000` reaches it.
    srv = ThreadingHTTPServer(("0.0.0.0" if EN_DOCKER else "127.0.0.1", PUERTO), Manejador)
    url = f"http://127.0.0.1:{PUERTO}"
    log.info("Demo G8 en %s (modo %s, raíz %s, %d núcleos) · Ctrl+C para salir",
             url, "docker" if EN_DOCKER else "host", RAIZ, NUCLEOS)
    if not EN_DOCKER:
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
