#!/usr/bin/env python3
# T14 | Responsable: Miguel | Medición de línea base T1 (secuencial).
"""Mide T1: el tiempo del backend secuencial (pp_serial) con la MISMA carga y semilla que el barrido OpenMP.

Protocolo (igual que scripts/bench/medir_openmp.py): una corrida de calentamiento (no cuenta) y
N repeticiones (5 por defecto). Todas las corridas deben dar el mismo k (semilla determinista); si no,
el script falla sin escribir nada.

Salida (por defecto results/bench/secuencial_t1.csv): UNA fila con carga (n, semilla, config_id, días),
k, hardware (CPU, núcleos físicos/lógicos, RAM), compilador, tipo de build, commit, fecha, SO, el tiempo
de calentamiento, t1..tN, media, desviación estándar muestral y µs por temporada (escenario). El archivo
se lee tal cual con `graficar_openmp_ashley.py --t1-csv` (columnas t1..t5).

Riesgo de la definición (§16.1, tabla de riesgos): «El costo real por temporada supera 10 µs». Si
us_por_escenario >= 10, el script avisa y marca supera_10us=1; la mitigación (bajar N por conjunto a
5 × 10⁵ o reducir las capacidades a 7) es una decisión del equipo, no de este script.

IMPORTANTE: los tiempos solo valen en la máquina de referencia con el binario en Release. El script
se niega a medir un build Debug (use --permitir-debug solo para probar el script).

Ejemplo (tras `cmake -S . -B build/docker -DCMAKE_BUILD_TYPE=Release && cmake --build build/docker`;
--build-dir vale build/docker por defecto):
    python3 scripts/bench/medir_secuencial.py --n 20000000 --repeticiones 5
"""
import argparse
import csv
import datetime
import os
import platform
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
# Se reutilizan la ejecución y la captura de hardware/entorno del barrido OpenMP (T16).
from medir_openmp import RAIZ, commit_git, correr, info_cpu, leer_cache, ram_gb, version_compilador  # noqa: E402

UMBRAL_US = 10.0  # disparador del riesgo «costo por temporada > 10 µs» (definición §16.1)


def resumir(tiempos):
    """Media y desviación estándar muestral (0 si hay una sola repetición)."""
    return statistics.mean(tiempos), (statistics.stdev(tiempos) if len(tiempos) > 1 else 0.0)


def us_por_escenario(media_s, n):
    """Microsegundos por temporada simulada (un escenario = una temporada de D días)."""
    return media_s * 1e6 / n


def verificar_k(corridas):
    """Exige k (y el histograma) idénticos en todas las corridas; devuelve k o termina con error."""
    ref = (corridas[0]["k"], corridas[0].get("hist512"))
    distintas = [i for i, r in enumerate(corridas) if (r["k"], r.get("hist512")) != ref]
    if distintas:
        ks = ", ".join(r["k"] for r in corridas)
        sys.exit(f"k distinto entre corridas con la misma semilla (k = {ks}; corridas {distintas}, "
                 "0 = calentamiento): el resultado no es determinista; no use esta medición.")
    return ref[0]


def construir_fila(cal, reps, n, semilla, config_id, meta):
    """Fila del CSV a partir del calentamiento, las repeticiones y los metadatos del entorno."""
    k = verificar_k([cal, *reps])
    tiempos = [float(r["tiempo_s"]) for r in reps]
    media, desviacion = resumir(tiempos)
    us = us_por_escenario(media, n)
    fila = dict(backend="serial", n=n, semilla=semilla, config_id=config_id, dias=reps[0].get("dias", ""),
                k=k, repeticiones=len(reps), **meta, t_calentamiento=float(cal["tiempo_s"]))
    for i, t in enumerate(tiempos, 1):
        fila[f"t{i}"] = t
    fila.update(media=media, desviacion=desviacion, us_por_escenario=us,
                supera_10us=int(round(us, 9) >= UMBRAL_US))
    return fila


def escribir_csv(ruta, fila):
    ruta = Path(ruta)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(fila.keys()))
        w.writeheader()
        w.writerow(fila)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--build-dir", default=str(RAIZ / "build" / "docker"))
    ap.add_argument("--config", default=str(RAIZ / "config" / "sintetico.yaml"),
                    help="configuración con los parámetros del modelo (sintéticos hasta recibir T10)")
    ap.add_argument("--n", type=int, default=20_000_000, help="escenarios por corrida (la misma N que el barrido)")
    ap.add_argument("--semilla", type=int, default=20261015)
    ap.add_argument("--config-id", type=int, default=0)
    ap.add_argument("--repeticiones", type=int, default=5)
    ap.add_argument("--salida", default=str(RAIZ / "results" / "bench" / "secuencial_t1.csv"))
    ap.add_argument("--permitir-debug", action="store_true")
    a = ap.parse_args(argv)
    if a.repeticiones < 1 or a.n < 1:
        sys.exit("--repeticiones y --n deben ser >= 1")
    if a.repeticiones != 5:
        print("AVISO: el protocolo pide 5 repeticiones; --t1-csv de graficar_openmp_ashley.py lee t1..t5.",
              file=sys.stderr)

    bd = Path(a.build_dir)
    serial = bd / "src/backends/serial/pp_serial"
    if not serial.exists():
        sys.exit(f"no existe {serial}; compile primero (cmake --build {bd})")
    tipo = leer_cache(bd, "CMAKE_BUILD_TYPE") or "desconocido"
    if tipo in ("Debug", "", "desconocido") and not a.permitir_debug:
        sys.exit(f"el build es '{tipo}': los tiempos no sirven. Recompile con -DCMAKE_BUILD_TYPE=Release.")

    cpu, fisicos, logicos = info_cpu()
    meta = dict(cpu=cpu, nucleos_fisicos=fisicos, nucleos_logicos=logicos, ram_gb=ram_gb(),
                compilador=version_compilador(bd), tipo_build=tipo, commit=commit_git(),
                fecha=datetime.datetime.now().astimezone().isoformat(timespec="seconds"), so=platform.platform())
    comunes = ["--config", a.config, "--n", str(a.n), "--semilla", str(a.semilla), "--config-id", str(a.config_id)]

    cal = correr(serial, comunes, [], os.environ)  # calentamiento: no cuenta
    reps = []
    for i in range(1, a.repeticiones + 1):
        reps.append(correr(serial, comunes, [], os.environ))
        print(f"repetición {i}: {float(reps[-1]['tiempo_s']):.4f} s  k={reps[-1]['k']}", flush=True)

    fila = construir_fila(cal, reps, a.n, a.semilla, a.config_id, meta)  # falla aquí si k no coincide
    escribir_csv(a.salida, fila)
    print(f"T1 = {fila['media']:.4f} s (sd {fila['desviacion']:.4f} s), {fila['us_por_escenario']:.3f} µs/temporada, "
          f"k={fila['k']} idéntico en {a.repeticiones + 1} corridas")
    print(f"escrito {a.salida}")
    if fila["supera_10us"]:
        print(f"AVISO: {fila['us_por_escenario']:.3f} µs por temporada >= {UMBRAL_US:g} µs: se dispara el riesgo "
              "«costo real por temporada supera 10 µs» (definición §16.1). Mitigación: bajar N por conjunto "
              "a 5 × 10⁵ o reducir las capacidades a 7 (decisión del equipo).", file=sys.stderr)


if __name__ == "__main__":
    main()
