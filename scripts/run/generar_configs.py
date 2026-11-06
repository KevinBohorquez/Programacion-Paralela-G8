#!/usr/bin/env python3
"""T10 | Selecciona las estaciones de trabajo y genera config/<estacion>_<regimen>.yaml.

Entradas (salidas de la tubería vigente de T08–T10, todas de HEAD):
    data/processed/auditoria_calidad.csv  (auditoria_datos.py: elegibilidad por estacion/anio)
    data/processed/parametros.csv         (calibrar.py: p01, p11, alfa, theta por estacion/regimen)
    data/metadata/inventario_senamhi.csv  (zona de cada estacion)
    scripts/run/calibrar.py               (ventana de temporada por zona: define `dias`)

Salidas:
    data/processed/estaciones_seleccionadas.csv  (las estaciones que entran al estudio y por qué)
    config/<estacion>_<regimen>.yaml             (una por estacion seleccionada y regimen calibrado)

Selección (docs/criterio-seleccion-estaciones.md): solo califican estaciones con al menos 20 años
elegibles (T08). Se ordenan primero las elegibles como estación completa (>= 90 % de años elegibles) y
luego por % de faltantes promedio en su temporada; se toman las 5 primeras. Si ninguna de la zona
Lima entra y alguna califica, la mejor de Lima ocupa la última plaza (la definición exige costa norte
y Lima).

Cada YAML usa las claves planas `clave: valor` que lee cargar_archivo_configuracion() en
src/io/configuracion.cpp. estacion, regimen, p01, p11, alfa, theta salen de parametros.csv; `dias` es
el largo de la temporada de la zona (enero–abril = 120, junio–setiembre = 122, año no bisiesto); el
resto (semilla, n, capacidad, umbral) se copia de la plantilla (config/sintetico.yaml). config_id se
asigna 0, 1, 2, ... en orden para que el índice global c*N + j no se repita entre configuraciones.
Las filas con NaN, fuera de rango (mismas reglas que validar() en configuracion.cpp) o con
estado_validacion distinto de OK se omiten y se informa por salida estándar.

Uso (en la imagen pp-g8, tras auditoria_datos.py, clasificar_regimenes.py y calibrar.py):
    python3 scripts/run/generar_configs.py
"""
from __future__ import annotations

import argparse
import calendar
import csv
import importlib.util
import math
import re
import subprocess
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
CALIBRADAS = ("p01", "p11", "alfa", "theta")
# Claves que asignar() de configuracion.cpp acepta; cualquier otra haría fallar la carga.
CLAVES_CONTRATO = {
    "backend", "estacion", "regimen", "config_id", "semilla", "n", "hilos", "schedule", "salida",
    "lote", "repeticion", "p01", "p11", "alfa", "theta", "capacidad", "umbral", "dias",
}
MIN_ANIOS_ELEGIBLES = 20
FRACCION_ESTACION_ELEGIBLE = 0.9  # misma regla que auditoria_datos.py
N_ESTACIONES = 5
MUESTRA_PEQUENA = 5  # años por grupo por debajo de los cuales se advierte en la cabecera del YAML


def cargar_calibrar():
    spec = importlib.util.spec_from_file_location("calibrar_t10", RAIZ / "scripts" / "run" / "calibrar.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def dias_temporada(meses):
    """Días de la temporada en un año no bisiesto (el simulador no modela el 29 de febrero)."""
    return sum(calendar.monthrange(2001, m)[1] for m in meses)


def leer_csv(ruta):
    with open(ruta, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def resumir_auditoria(filas):
    """Por estación: años auditados, años elegibles y % de faltantes promedio de la temporada."""
    acum = defaultdict(lambda: {"auditados": 0, "elegibles": 0, "pct": 0.0})
    for f in filas:
        a = acum[f["estacion"]]
        a["auditados"] += 1
        a["elegibles"] += f["elegible"].strip().lower() == "true"
        a["pct"] += float(f["pct_faltantes"])
    return {e: {"auditados": a["auditados"], "elegibles": a["elegibles"],
                "pct_faltantes": 100.0 * a["pct"] / a["auditados"],
                "estacion_elegible": a["elegibles"] >= FRACCION_ESTACION_ELEGIBLE * a["auditados"]}
            for e, a in acum.items()}


def seleccionar(resumen, zonas, n=N_ESTACIONES, minimo=MIN_ANIOS_ELEGIBLES):
    """Devuelve [(estacion, motivo)] según la regla del docstring."""
    calificadas = [e for e, r in resumen.items() if r["elegibles"] >= minimo]
    orden = sorted(calificadas, key=lambda e: (not resumen[e]["estacion_elegible"], resumen[e]["pct_faltantes"], e))
    elegidas = [(e, "elegible como estación completa" if resumen[e]["estacion_elegible"]
                 else f">= {minimo} años elegibles; siguiente por menor % faltante") for e in orden[:n]]
    if not any(zonas.get(e) == "lima" for e, _ in elegidas):
        lima = [e for e in orden if zonas.get(e) == "lima"]
        if lima and elegidas:
            elegidas[-1] = (lima[0], "mejor estación de Lima (la definición exige costa norte y Lima)")
    return elegidas


def leer_plantilla(ruta):
    """Pares clave/valor con la misma regla que el lector C++: se descarta desde '#', 'clave: valor'."""
    pares = {}
    for num, linea in enumerate(Path(ruta).read_text(encoding="utf-8").splitlines(), 1):
        linea = linea.split("#", 1)[0].strip()
        if not linea:
            continue
        if ":" not in linea:
            raise ValueError(f"{ruta}:{num}: se esperaba 'clave: valor'")
        k, v = (x.strip() for x in linea.split(":", 1))
        if k not in CLAVES_CONTRATO:
            raise ValueError(f"{ruta}:{num}: clave desconocida '{k}'")
        pares[k] = v
    return pares


def validar_parametros(p):
    """Mismas reglas de rango que validar() en src/io/configuracion.cpp; NaN no pasa ninguna."""
    if not (0.0 <= p["p01"] <= 1.0 and 0.0 <= p["p11"] <= 1.0):
        raise ValueError("p01 y p11 deben estar en [0,1]")
    if not (p["alfa"] > 0.0 and p["theta"] > 0.0):
        raise ValueError("alfa y theta deben ser > 0")


def nombre_archivo(estacion, regimen):
    """Nombre seguro: minúsculas ASCII, [a-z0-9_]."""
    base = unicodedata.normalize("NFKD", f"{estacion}_{regimen}").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", base.lower()).strip("_") + ".yaml"


def commit_actual():
    try:
        r = subprocess.run(["git", "-C", str(RAIZ), "rev-parse", "--short", "HEAD"],
                           capture_output=True, text=True, timeout=10)
        return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else "desconocido"
    except (OSError, subprocess.SubprocessError):
        return "desconocido"


def escribir_configs(filas, estaciones, dias_por_estacion, plantilla, ruta_plantilla, ruta_param, destino, commit):
    """Escribe un YAML por fila de parametros.csv cuya estación esté en `estaciones` (en ese orden)."""
    destino.mkdir(parents=True, exist_ok=True)
    escritos, config_id = [], 0
    filas = sorted((f for f in filas if f["estacion"].strip() in estaciones),
                   key=lambda f: (estaciones.index(f["estacion"].strip()), f["regimen"].strip()))
    for fila in filas:
        est, reg = fila["estacion"].strip(), fila["regimen"].strip()
        try:
            if fila.get("estado_validacion", "OK").strip() != "OK":
                raise ValueError(f"estado_validacion={fila['estado_validacion']}")
            p = {k: float(fila[k]) for k in CALIBRADAS}
            if any(math.isnan(v) for v in p.values()):
                raise ValueError("parámetro NaN")
            validar_parametros(p)
        except (KeyError, ValueError) as e:
            print(f"omitida {est}/{reg}: {e}")
            continue

        valores = dict(plantilla)
        valores.pop("salida", None)  # la ruta de salida la decide cada corrida
        valores.update({"estacion": est, "regimen": reg, "config_id": str(config_id),
                        "dias": str(dias_por_estacion[est])})
        valores.update({k: repr(v) for k, v in p.items()})
        n_anios = fila.get("n_anios", "?")
        cabecera = [
            f"# T10 | Configuración calibrada: {est} / {reg}.",
            f"# Generado por scripts/run/generar_configs.py desde {ruta_param} (commit {commit}).",
            f"# Calibración: scripts/run/calibrar.py (temporada por zona, Thom); años del grupo = {n_anios}.",
            f"# Claves no calibradas copiadas de {ruta_plantilla}.",
        ]
        if n_anios.isdigit() and int(n_anios) < MUESTRA_PEQUENA:
            cabecera.append(f"# ADVERTENCIA: muestra pequeña (n_anios = {n_anios}).")
        orden = ["estacion", "regimen", "config_id", "semilla", "n", "dias", *CALIBRADAS, "capacidad", "umbral"]
        claves = [k for k in orden if k in valores] + sorted(k for k in valores if k not in orden)
        ruta = destino / nombre_archivo(est, reg)
        ruta.write_text("\n".join(cabecera + [f"{k}: {valores[k]}" for k in claves]) + "\n", encoding="utf-8")
        escritos.append(ruta)
        config_id += 1
    return escritos


def main(argv=None):
    ap = argparse.ArgumentParser(description="Selecciona estaciones y genera YAML por estación y régimen (T10).")
    ap.add_argument("--auditoria", default="data/processed/auditoria_calidad.csv")
    ap.add_argument("--parametros", default="data/processed/parametros.csv")
    ap.add_argument("--inventario", default="data/metadata/inventario_senamhi.csv")
    ap.add_argument("--plantilla", default="config/sintetico.yaml")
    ap.add_argument("--seleccion", default="data/processed/estaciones_seleccionadas.csv")
    ap.add_argument("--salida-dir", default="config")
    ap.add_argument("--n-estaciones", type=int, default=N_ESTACIONES)
    ap.add_argument("--commit", default=None, help="commit a registrar (por defecto: git rev-parse HEAD)")
    a = ap.parse_args(argv)

    calibrar = cargar_calibrar()
    zonas = {f["id_estacion"]: f["zona"] for f in leer_csv(RAIZ / a.inventario)}
    resumen = resumir_auditoria(leer_csv(RAIZ / a.auditoria))
    elegidas = seleccionar(resumen, zonas, n=a.n_estaciones)
    if not elegidas:
        print("ninguna estación califica")
        return 1

    dias = {e: dias_temporada(calibrar.meses_temporada_de(e, zonas[e])) for e, _ in elegidas}
    with open(RAIZ / a.seleccion, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["estacion", "zona", "meses_temporada", "dias", "anios_auditados", "anios_elegibles",
                    "pct_faltantes_temporada", "estacion_elegible", "motivo_seleccion"])
        for e, motivo in elegidas:
            r = resumen[e]
            meses = ";".join(str(m) for m in calibrar.meses_temporada_de(e, zonas[e]))
            w.writerow([e, zonas[e], meses, dias[e], r["auditados"], r["elegibles"],
                        f"{r['pct_faltantes']:.2f}", int(r["estacion_elegible"]), motivo])

    escritos = escribir_configs(leer_csv(RAIZ / a.parametros), [e for e, _ in elegidas], dias,
                                leer_plantilla(RAIZ / a.plantilla), a.plantilla, a.parametros,
                                RAIZ / a.salida_dir, a.commit or commit_actual())
    print(f"seleccionadas {len(elegidas)} estaciones: {', '.join(e for e, _ in elegidas)}")
    print(f"escritos {len(escritos)} YAML en {a.salida_dir}")
    return 0 if escritos else 1


if __name__ == "__main__":
    sys.exit(main())
