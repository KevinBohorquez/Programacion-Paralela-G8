#!/usr/bin/env python3
# T33,T45 | Responsable: Rhamses | Lectura normalizada de los CSV de rendimiento y métricas comunes.
"""Piezas comunes de analizar-rendimiento.py (T33) y graficar-final.py (T45).

Normaliza los CSV de los barridos a un registro por punto medido:
  openmp.csv (T16), mpi_resumen.csv (T21), hibrido_resumen.csv (T27), x1/x2/x3.csv (T26, T30, T31)
y resuelve T1 con, en este orden: la columna `t_serial` del propio resumen, secuencial_t1.csv (T14)
con el mismo N, o la fila `serial` de la misma fuente con el mismo N.

Métricas: media, desviación, CV, speedup S = T1/Tp, eficiencia E = S/p, eficiencia sobre rangos de
cómputo (E2: el rango 0 es maestro), throughput (escenarios/s), Karp–Flatt e = (1/S − 1/p)/(1 − 1/p),
eficiencia de escalado débil T1(N)/Tp(pN) para X2 y ajuste lineal tiempo-vs-N para X3.
Toda entrada ausente se omite con un AVISO por stderr.
"""
import csv
import statistics
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]

# Núcleos de rendimiento (P) de CPU híbridas conocidas: por encima, el planificador usa núcleos E.
NUCLEOS_P = {"Ultra 9 275HX": 8, "Ultra 7 255HX": 8, "i9-12900": 8, "i9-13900": 8, "i9-14900": 8,
             "i7-12700": 8, "i7-13700": 8, "i7-14700": 8, "i5-12600K": 6, "i5-13600": 6}

FUENTES = {
    "openmp": "openmp.csv",
    "mpi": "mpi_resumen.csv",
    "hibrido": "hibrido_resumen.csv",
    "x1": "x1.csv",
    "x2": "x2.csv",
    "x3": "x3.csv",
}
T1_CSV = "secuencial_t1.csv"


def aviso(texto):
    print(f"AVISO: {texto}", file=sys.stderr)


def leer_csv(ruta):
    """Filas del CSV o None (con AVISO) si no existe o está vacío."""
    ruta = Path(ruta)
    if not ruta.exists():
        aviso(f"no existe {ruta}; se omite")
        return None
    with open(ruta, newline="", encoding="utf-8") as f:
        filas = list(csv.DictReader(f))
    if not filas:
        aviso(f"{ruta} está vacío; se omite")
        return None
    return filas


def num(valor, defecto=None):
    try:
        if valor is None or str(valor).strip() in ("", "-"):
            return defecto
        return float(valor)
    except ValueError:
        return defecto


def entero(valor, defecto=None):
    v = num(valor)
    return int(v) if v is not None else defecto


# ---------- métricas puras ----------
def karp_flatt(s, p):
    """Fracción serial experimental; None si p <= 1 o S no es positivo."""
    if s is None or s <= 0 or p is None or p <= 1:
        return None
    return (1.0 / s - 1.0 / p) / (1.0 - 1.0 / p)


def ajuste_lineal(puntos):
    """Mínimos cuadrados t = a + b·N sobre [(N, t)]; b en s/escenario y µs/escenario."""
    if len(puntos) < 2:
        return None
    xs, ys = [float(x) for x, _ in puntos], [float(y) for _, y in puntos]
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        return None
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    a = my - b * mx
    sst = sum((y - my) ** 2 for y in ys)
    sse = sum((y - (a + b * x)) ** 2 for x, y in zip(xs, ys))
    return dict(pendiente=b, intercepto=a, r2=1.0 - sse / sst if sst else 1.0, us_por_escenario=b * 1e6,
                puntos=len(xs))


def nucleos_p(cpu):
    for clave, p in NUCLEOS_P.items():
        if clave in (cpu or ""):
            return p
    return None


def nota_nucleos(cpu, recursos):
    """Aviso P/E: con más recursos que núcleos P, parte del trabajo cae en núcleos E (más lentos)."""
    p = nucleos_p(cpu)
    if p is None or recursos is None:
        return ""
    if recursos > p:
        return f"p>{p} núcleos P: incluye núcleos E"
    if recursos == p:
        return f"p={p}: todos los núcleos P"
    return ""


def tiempos_de(fila):
    """Repeticiones medidas: columna `tiempos` (a;b;c) o t1..tN."""
    if fila.get("tiempos"):
        return [float(t) for t in str(fila["tiempos"]).split(";") if t.strip()]
    ts, i = [], 1
    while f"t{i}" in fila:
        v = num(fila[f"t{i}"])
        if v is not None:
            ts.append(v)
        i += 1
    return ts


# ---------- normalización ----------
def _base(fila, fuente, experimento, backend, variante, procesos, hilos, recursos):
    media = num(fila.get("media"))
    ts = tiempos_de(fila)
    if media is None and ts:
        media = statistics.fmean(ts)
    sd = num(fila.get("desviacion"))
    if sd is None:
        sd = statistics.stdev(ts) if len(ts) > 1 else 0.0
    computo = entero(fila.get("procesos_computo"))
    if computo is None:
        computo = procesos - 1 if backend == "mpi_dinamico" and procesos > 1 else procesos
    fisicos = entero(fila.get("nucleos_fisicos"))
    sobre = entero(fila.get("sobresuscrito"))
    if sobre is None:
        sobre = int(fisicos is not None and recursos > fisicos)
    return dict(fuente=fuente, experimento=experimento, backend=backend, variante=variante or "-",
                procesos=procesos, hilos=hilos, recursos=recursos, recursos_computo=computo * hilos,
                n=entero(fila.get("n")), media=media, desviacion=sd, repeticiones=len(ts),
                t_serial=num(fila.get("t_serial")), sobresuscrito=sobre, cpu=fila.get("cpu", ""),
                nucleos_fisicos=fisicos, commit=fila.get("commit", ""))


def normalizar(fuente, fila):
    if fuente == "openmp":
        h = entero(fila.get("hilos"), 1)
        return _base(fila, fuente, "openmp", fila.get("backend") or "openmp", fila.get("schedule"), 1, h, h)
    if fuente == "mpi":
        p = entero(fila.get("procesos"), 1)
        return _base(fila, fuente, "mpi", fila.get("esquema") or fila.get("backend"), "-", p, 1, p)
    if fuente == "hibrido":
        p, h = entero(fila.get("procesos"), 1), entero(fila.get("hilos"), 1)
        b = entero(fila.get("nucleos_totales"), p * h)
        return _base(fila, fuente, "hibrido", "hibrido", fila.get("factorizacion") or f"{p}x{h}", p, h, b)
    p, h = entero(fila.get("procesos"), 1), entero(fila.get("hilos"), 1)
    backend = fila.get("backend", "")
    variante = f"{p}x{h}" if backend == "hibrido" else (fila.get("schedule") if backend == "openmp" else "-")
    return _base(fila, fuente, fila.get("experimento") or fuente, backend, variante, p, h,
                 entero(fila.get("recursos"), p * h))


def cargar_registros(bench):
    """Registros normalizados de todas las fuentes presentes y la tabla T1 {N: (media, sd)}."""
    bench = Path(bench)
    t1 = {}
    for f in leer_csv(bench / T1_CSV) or []:
        n, m = entero(f.get("n")), num(f.get("media"))
        if n is not None and m is not None:
            t1[n] = (m, num(f.get("desviacion"), 0.0))
    registros = []
    for fuente, nombre in FUENTES.items():
        for fila in leer_csv(bench / nombre) or []:
            r = normalizar(fuente, fila)
            if r["media"] is not None and r["n"] is not None:
                registros.append(r)
    return registros, t1


def _t1_para(r, t1, seriales):
    if r["t_serial"]:
        return r["t_serial"], "t_serial"
    if r["n"] in t1:
        return t1[r["n"]][0], T1_CSV
    s = seriales.get((r["fuente"], r["n"]))
    if s:
        return s, f"serial de {FUENTES[r['fuente']]}"
    return None, ""


def calcular(registros, t1):
    """Añade las métricas a cada registro (en sitio) y devuelve la lista."""
    seriales = {(r["fuente"], r["n"]): r["media"] for r in registros if r["backend"] == "serial"}
    for r in registros:
        t_ref, fuente = _t1_para(r, t1, seriales)
        m, p = r["media"], r["recursos"]
        s = t_ref / m if t_ref and m else None
        r.update(t1=t_ref, fuente_t1=fuente, cv=(r["desviacion"] / m if m else None), speedup=s,
                 eficiencia=(s / p if s and p else None),
                 eficiencia_computo=(s / r["recursos_computo"] if s and r["recursos_computo"] else None),
                 throughput=(r["n"] / m if m else None), us_por_escenario=(m * 1e6 / r["n"] if r["n"] else None),
                 karp_flatt=karp_flatt(s, p), eficiencia_debil=None,
                 nota_nucleos=nota_nucleos(r["cpu"], p))
    _escalado_debil(registros, t1)
    return registros


def _escalado_debil(registros, t1):
    """X2: E_w = T1(N0) / Tp(p·N0), con N0 = N/p. T1(N0) de la fila serial de X2, T14 o el p=1 propio."""
    x2 = [r for r in registros if r["experimento"] == "x2"]
    seriales = {r["n"]: r["media"] for r in x2 if r["backend"] == "serial"}
    propios = {(r["backend"], r["variante"]): r["media"] for r in x2 if r["recursos"] == 1}
    for r in x2:
        n0 = r["n"] // r["recursos"] if r["recursos"] else None
        base = seriales.get(n0) or (t1.get(n0) or (None,))[0] or propios.get((r["backend"], r["variante"]))
        if base and r["media"]:
            r["eficiencia_debil"] = base / r["media"]


def ajustes_x3(registros):
    """Ajuste lineal tiempo-vs-N por (backend, variante, recursos) de X3."""
    grupos = {}
    for r in registros:
        if r["experimento"] == "x3":
            grupos.setdefault((r["backend"], r["variante"], r["recursos"]), []).append(r)
    salida = []
    for (b, v, p), rs in sorted(grupos.items()):
        aj = ajuste_lineal(sorted((r["n"], r["media"]) for r in rs))
        if aj:
            salida.append(dict(backend=b, variante=v, recursos=p, **aj))
    return salida


def pie(registros):
    """Texto de procedencia: commit(s) y hardware tomados del CSV."""
    commits = sorted({r["commit"] for r in registros if r.get("commit")})
    cpus = sorted({f"{r['cpu']} ({r['nucleos_fisicos']} núcleos)" if r.get("nucleos_fisicos") else r["cpu"]
                   for r in registros if r.get("cpu")})
    return f"commit {', '.join(commits) or 'desconocido'} · {'; '.join(cpus) or 'hardware desconocido'}"
