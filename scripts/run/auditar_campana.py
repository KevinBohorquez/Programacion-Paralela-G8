#!/usr/bin/env python3
"""T34: cuenta escenarios y sella CSV, logs y manifiestos sin ejecutar simulaciones.

No suma campañas de modelos distintos para alcanzar la meta. Los respaldos se
verifican contra archivos reales; no se crean ni se declaran automáticamente.
"""
import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
META = 13_000_000_000


def sha256(ruta):
    h = hashlib.sha256()
    with Path(ruta).open("rb") as f:
        for bloque in iter(lambda: f.read(1024 * 1024), b""):
            h.update(bloque)
    return h.hexdigest()


def resumen_csv(ruta):
    total, filas, claves, repetidas = 0, 0, set(), 0
    with Path(ruta).open(encoding="utf-8", newline="") as f:
        for fila in csv.DictReader(f):
            n, k = int(fila["n"]), int(fila["k"])
            hist = [int(x) for x in fila["hist512"].split(";")]
            if n <= 0 or not 0 <= k <= n or len(hist) != 512 or min(hist) < 0 or sum(hist) != n:
                raise ValueError(f"{ruta}: fila {filas + 2}, n/k/hist512 incoherentes")
            # Incluye semilla, réplica y parámetros: capacidades iguales con
            # parámetros distintos no son duplicados; una fila repetida sí lo es.
            clave = tuple(fila.get(c, "") for c in (
                "estacion", "regimen", "config_id", "semilla", "n", "dias",
                "capacidad", "umbral", "p01", "p11", "alfa", "theta", "kappa", "replica"))
            if clave in claves:
                repetidas += 1
            claves.add(clave)
            total += n
            filas += 1
    if not filas:
        raise ValueError(f"{ruta}: CSV vacío")
    return {"filas": filas, "escenarios": total, "configuraciones_distintas": len(claves),
            "filas_con_parametros_repetidos": repetidas}


def registro(ruta, raiz):
    return {"ruta": ruta.relative_to(raiz).as_posix(), "bytes": ruta.stat().st_size,
            "sha256": sha256(ruta)}


def verificar(raiz, inventario):
    errores = []
    for archivo in inventario["archivos"]:
        ruta = Path(raiz) / archivo["ruta"]
        if not ruta.is_file() or sha256(ruta) != archivo["sha256"]:
            errores.append(archivo["ruta"])
    return errores


def auditar(raiz=ROOT, actualizar=False, respaldos=()):
    raiz = Path(raiz).resolve()
    carpeta = raiz / "results/cientifico"
    campanas, archivos, actualizaciones = {}, set(), []
    for modelo, sufijo in (("sin_h5", ""), ("h5", "_h5")):
        resultados = {}
        for experimento in ("x6", "bootstrap"):
            csv_path = carpeta / f"{experimento}{sufijo}.csv"
            manifiesto = carpeta / f"{experimento}{sufijo}_manifiesto.json"
            datos = json.loads(manifiesto.read_text(encoding="utf-8"))
            resultados[experimento] = resumen_csv(csv_path)
            puntos = [p for p in datos["puntos"] if p["estado"] == "ok"]
            if (len(puntos) != resultados[experimento]["filas"] or
                    sum(int(p["n"]) for p in puntos) != resultados[experimento]["escenarios"]):
                raise ValueError(f"{manifiesto}: puntos y CSV no coinciden")
            fuentes = [csv_path]
            for sesion in datos["sesiones"]:
                log = raiz / sesion["log"]
                if not log.is_file():
                    raise ValueError(f"falta log: {log}")
                fuentes.append(log)
            fuentes = sorted(set(fuentes))
            if actualizar:
                datos["integridad"] = {"algoritmo": "SHA-256",
                    "archivos": [registro(p, raiz) for p in fuentes]}
                actualizaciones.append((manifiesto, datos))
            archivos.update([manifiesto, *fuentes])
        total = sum(r["escenarios"] for r in resultados.values())
        campanas[modelo] = {**resultados, "escenarios_total": total,
                           "meta_documentada": META, "faltan_para_meta": max(0, META - total),
                           "meta_cumplida": total >= META}
    # Validar las cuatro fuentes antes de modificar cualquiera de los manifiestos.
    for manifiesto, datos in actualizaciones:
        with manifiesto.open("w", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(datos, ensure_ascii=False, indent=2) + "\n")
    # El respaldo de results/cientifico incluye también X7 y las tablas.
    archivos.update(p for p in carpeta.rglob("*") if p.is_file() and
                    p.suffix in (".csv", ".log", ".json", ".md") and p.name != "t34_integridad.json")
    inventario = {"version": 1, "fecha_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "alcance": "Auditoría de archivos existentes; no constituye una nueva corrida ni aprobación de la meta",
        "campanas": campanas, "archivos": [registro(p, raiz) for p in sorted(archivos)], "respaldos": []}
    equipos = set()
    for equipo, ubicacion in respaldos:
        if not equipo.strip() or equipo in equipos:
            raise ValueError("cada respaldo debe identificar un equipo distinto")
        equipos.add(equipo)
        copia = Path(ubicacion).resolve()
        if copia == raiz or copia.is_relative_to(raiz) or raiz.is_relative_to(copia):
            raise ValueError("un respaldo no puede ser la copia de trabajo ni una carpeta dentro de ella")
        errores = verificar(copia, inventario)
        inventario["respaldos"].append({"equipo_declarado": equipo, "raiz": str(copia),
            "integridad_verificada": not errores, "errores": errores})
    inventario["dos_respaldos_verificados"] = sum(r["integridad_verificada"] for r in inventario["respaldos"]) >= 2
    return inventario


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--raiz", type=Path, default=ROOT)
    ap.add_argument("--salida", type=Path, default=Path("results/cientifico/t34_integridad.json"))
    ap.add_argument("--actualizar-manifiestos", action="store_true")
    ap.add_argument("--verificar", action="store_true", help="comprueba el inventario guardado sin modificarlo")
    ap.add_argument("--respaldo", action="append", default=[], metavar="EQUIPO=RAIZ_COPIA",
                    help="raíz que contiene results/cientifico; el equipo se declara, los hashes se comprueban")
    a = ap.parse_args(argv)
    salida = a.salida if a.salida.is_absolute() else a.raiz / a.salida
    try:
        if a.verificar:
            if a.actualizar_manifiestos or a.respaldo:
                raise ValueError("--verificar no admite actualizar manifiestos ni registrar respaldos")
            datos = json.loads(salida.read_text(encoding="utf-8"))
            errores = verificar(a.raiz, datos)
            print(f"SHA-256: {len(datos['archivos'])} archivos; errores={len(errores)}")
            for e in errores:
                print(f"ERROR: {e}")
            return int(bool(errores))
        respaldos = []
        for valor in a.respaldo:
            equipo, sep, ubicacion = valor.partition("=")
            if not sep or not ubicacion:
                raise ValueError("use --respaldo EQUIPO=RAIZ_COPIA")
            respaldos.append((equipo, ubicacion))
        datos = auditar(a.raiz, a.actualizar_manifiestos, respaldos)
        salida.parent.mkdir(parents=True, exist_ok=True)
        with salida.open("w", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(datos, ensure_ascii=False, indent=2) + "\n")
        for modelo, c in datos["campanas"].items():
            print(f"{modelo}: {c['escenarios_total']:,} escenarios; faltan {c['faltan_para_meta']:,} para la meta")
        print(f"SHA-256: {len(datos['archivos'])} archivos; dos respaldos verificados={datos['dos_respaldos_verificados']}")
        print(f"escrito {salida}")
        return int(any(r["errores"] for r in datos["respaldos"]))
    except (OSError, ValueError, KeyError) as e:
        print(f"ERROR: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
