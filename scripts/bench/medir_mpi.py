#!/usr/bin/env python3
# T21 | Responsable: Ashley | Barrido MPI de 2, 4, 8 y 16 procesos (E1 estático y E2 dinámico).
"""Mide E1 (pp_mpi_estatico) y E2 (pp_mpi_dinamico) frente al secuencial con la MISMA carga y semilla.

Por cada punto (esquema x procesos): una corrida de calentamiento (no cuenta) y N repeticiones
(5 por defecto). Antes de calcular speedup se comprueba V1: k, n e histograma de cada corrida deben
ser idénticos a los de pp_serial con los mismos N, semilla y configuración.

T1 se toma de results/bench/secuencial_t1.csv (T14) cuando coincide en N, semilla, config_id, días
y k; si no coincide, se mide aquí con el mismo protocolo. Los valores por defecto (N = 2e7, semilla
20261015, config/sintetico.yaml) son los del barrido OpenMP, así los speedups son comparables.

E2 usa un maestro: el rango 0 solo reparte bloques (REQ/WORK/STOP) y no simula, así que con P
procesos computan P-1. El resumen trae `procesos_computo`, `eficiencia` (speedup / P, recursos
ocupados) y `eficiencia_computo` (speedup / procesos de cómputo), además de la columna `nota`.

Salidas (con --salida results/bench/mpi.csv, el valor por defecto):
  mpi.csv          UNA fila por corrida (calentamiento = repetición 0, luego 1..5) con tiempo, k, V1,
                   nodos, distribución por nodo (CSV del simulador), escenarios por rango y bloques (E2).
  mpi_resumen.csv  UNA fila por punto: tiempos, media, desviación estándar muestral, speedup vs T1,
                   eficiencia, distribución por nodo, reparto por rango, marca `sobresuscrito`
                   (procesos > núcleos físicos), hardware, compilador y commit.
  mpi_secuencial_ref.csv  solo si T1 se midió en este barrido.

El script se niega a medir un build Debug (use --permitir-debug solo para probarlo).

Ejemplo (en la imagen pp-g8, build Release con -DPP_BUILD_MPI=ON):
    python3 scripts/bench/medir_mpi.py --build-dir build/docker --procesos 2,4,8,16
"""
import argparse
import datetime
import platform
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _comun_mpi as cm  # noqa: E402

RAIZ = cm.RAIZ
EJECUTABLES = {"mpi_estatico": "pp_mpi_estatico", "mpi_dinamico": "pp_mpi_dinamico"}


def plan(esquemas, procesos):
    return [(e, p) for e in esquemas for p in procesos]


def fila_resumen(esquema, procesos, cal, reps, verif, t_serial, fuente_t1, equivalente, fisicos, logicos, base):
    """Fila del resumen de un punto. `reps` son filas CSV del simulador; `verif`, el [verif] de la rep. 1."""
    tiempos = [float(r["tiempo_s"]) for r in reps]
    media, desviacion = cm.resumir(tiempos)
    computo = cm.procesos_de_computo(esquema, procesos)
    fila = dict(esquema=esquema, procesos=procesos, procesos_computo=computo, **base,
                t_calentamiento=cal["tiempo_s"])
    for i, t in enumerate(tiempos, 1):
        fila[f"t{i}"] = t
    fila.update(media=media, desviacion=desviacion, t_serial=t_serial, fuente_t1=fuente_t1,
                speedup=cm.speedup(t_serial, media),
                eficiencia=cm.eficiencia(t_serial, media, procesos),
                eficiencia_computo=cm.eficiencia(t_serial, media, computo),
                k=reps[0]["k"], equivalente_serial=int(equivalente),
                nodos=reps[0].get("nodos", ""), distribucion=reps[0].get("distribucion", ""),
                reparto_rangos=cm.reparto_texto(verif["rangos"]),
                bloques_rangos=cm.bloques_texto(verif["rangos"]),
                nucleos_fisicos=fisicos, nucleos_logicos=logicos,
                sobresuscrito=cm.sobresuscrito(procesos, fisicos),
                excede_logicos=cm.sobresuscrito(procesos, logicos),
                nota=cm.NOTA_E2 if esquema == "mpi_dinamico" else "")
    return fila


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--build-dir", default=str(RAIZ / "build" / "docker"))
    ap.add_argument("--config", default=str(RAIZ / "config" / "sintetico.yaml"))
    ap.add_argument("--n", type=int, default=20_000_000, help="escenarios por corrida (igual en todo el barrido)")
    ap.add_argument("--semilla", type=int, default=20261015)
    ap.add_argument("--config-id", type=int, default=0)
    ap.add_argument("--procesos", default="2,4,8,16")
    ap.add_argument("--esquemas", default="mpi_estatico,mpi_dinamico")
    ap.add_argument("--lote", type=int, help="tamaño de bloque de E2 (por defecto el del simulador)")
    ap.add_argument("--reps", "--repeticiones", dest="reps", type=int, default=5)
    ap.add_argument("--bind-to", default="core", help="política --bind-to de mpirun (se registra en `afinidad`)")
    ap.add_argument("--t1-csv", default=str(cm.T1_POR_DEFECTO))
    ap.add_argument("--medir-t1", action="store_true", help="ignorar --t1-csv y medir el secuencial aquí")
    ap.add_argument("--timeout", type=float, default=3600, help="segundos máximos por corrida")
    ap.add_argument("--salida", default=str(RAIZ / "results" / "bench" / "mpi.csv"))
    ap.add_argument("--dry-run", action="store_true", help="solo imprime los comandos")
    ap.add_argument("--permitir-debug", action="store_true")
    a = ap.parse_args()

    procesos = cm.lista_enteros(a.procesos)
    esquemas = [e.strip() for e in a.esquemas.split(",")]
    if any(e not in EJECUTABLES for e in esquemas):
        sys.exit(f"esquemas válidos: {', '.join(EJECUTABLES)}")
    bd = Path(a.build_dir)
    serial = bd / "src/backends/serial/pp_serial"
    exes = {e: bd / "src/backends/mpi" / EJECUTABLES[e] for e in esquemas}
    mpiexec = cm.mpiexec_de(bd)
    cpu, fisicos, logicos = cm.info_cpu()
    comunes = ["--config", a.config, "--n", str(a.n), "--semilla", str(a.semilla), "--config-id", str(a.config_id)]
    extra_e2 = ["--lote", str(a.lote)] if a.lote else []

    def comando(esquema, p):
        args = comunes + (extra_e2 if esquema == "mpi_dinamico" else [])
        return cm.comando_mpi(mpiexec, p, exes[esquema], args, bind_to=a.bind_to, oversubscribe=p > logicos)

    if a.dry_run:
        print(" ".join(map(str, [serial, *comunes])) + "   # referencia V1 (y T1 si no coincide)")
        for e, p in plan(esquemas, procesos):
            print(" ".join(comando(e, p)) + f"   # calentamiento + {a.reps} repeticiones")
        return

    for exe in (serial, *exes.values()):
        if not exe.exists():
            sys.exit(f"no existe {exe}; compile con -DPP_BUILD_MPI=ON (cmake --build {bd})")
    tipo = cm.leer_cache(bd, "CMAKE_BUILD_TYPE") or "desconocido"
    if tipo in ("Debug", "desconocido") and not a.permitir_debug:
        sys.exit(f"el build es '{tipo}': los tiempos no sirven. Recompile con -DCMAKE_BUILD_TYPE=Release.")

    meta = dict(cpu=cpu, ram_gb=cm.ram_gb(), compilador=cm.version_compilador(bd), tipo_build=tipo,
                commit=cm.commit_git(), fecha=datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
                so=platform.platform(), mpiexec=mpiexec)
    entorno = cm.entorno_mpi(PP_COMMIT=meta["commit"])
    ref, t_serial, fuente_t1, filas_serial = cm.referencia_serial(
        serial, comunes, entorno, a.t1_csv, a.n, a.semilla, a.config_id, a.reps, forzar=a.medir_t1)
    print(f"referencia secuencial k={ref['k']}  T1={t_serial:.4f}s ({fuente_t1})", flush=True)

    base = dict(n=a.n, semilla=a.semilla, config_id=a.config_id, dias=ref["dias"])
    corridas, resumen = [], []
    for esquema, p in plan(esquemas, procesos):
        afinidad = f"mpirun --bind-to {a.bind_to}" + (" --oversubscribe" if p > logicos else "")
        (cal, vcal), reps_v = cm.medir_punto(comando(esquema, p), entorno, a.reps, a.timeout)
        reps = [r for r, _ in reps_v]
        todas = [(cal, vcal)] + reps_v
        equivalente = all(cm.equivalente(r, ref) and v["estado"] == "OK" for r, v in todas)
        for i, (r, v) in enumerate(todas):
            corridas.append(dict(
                esquema=esquema, procesos=p, procesos_computo=cm.procesos_de_computo(esquema, p), repeticion=i,
                calentamiento=int(i == 0), tiempo_s=r["tiempo_s"], **base, k=r["k"],
                equivalente_serial=int(cm.equivalente(r, ref)), estado=v["estado"],
                nodos=r.get("nodos", ""), distribucion=r.get("distribucion", ""),
                reparto_rangos=cm.reparto_texto(v["rangos"]), bloques_rangos=cm.bloques_texto(v["rangos"]),
                afinidad=afinidad, sobresuscrito=cm.sobresuscrito(p, fisicos),
                excede_logicos=cm.sobresuscrito(p, logicos), cpu=cpu, nucleos_fisicos=fisicos,
                nucleos_logicos=logicos, hardware=r.get("hardware", ""), commit=meta["commit"]))
        fila = fila_resumen(esquema, p, cal, reps, reps_v[0][1], t_serial, fuente_t1, equivalente,
                            fisicos, logicos, base)
        fila.update(afinidad=afinidad, hardware=reps[0].get("hardware", ""), **meta)
        resumen.append(fila)
        marca = " [SOBRESUSCRITO]" if fila["sobresuscrito"] else ""
        print(f"{esquema:12s} P={p:2d} (computo={fila['procesos_computo']:2d}) media={fila['media']:.4f}s "
              f"sd={fila['desviacion']:.4f}s S={fila['speedup']:.2f} V1={'ok' if equivalente else 'FALLA'}{marca}",
              flush=True)

    salida = Path(a.salida)
    cm.escribir_csv(salida, corridas)
    cm.escribir_csv(salida.with_name(salida.stem + "_resumen.csv"), resumen)
    if filas_serial:
        cm.escribir_csv(salida.with_name(salida.stem + "_secuencial_ref.csv"),
                        [dict(repeticion=i, calentamiento=int(i == 0), tiempo_s=r["tiempo_s"], k=r["k"], **base,
                              commit=meta["commit"]) for i, (r, _) in enumerate(filas_serial)])
    if not all(f["equivalente_serial"] for f in resumen):
        sys.exit("V1 FALLÓ: hay corridas MPI distintas del secuencial; no use este CSV para speedup.")
    if any(f["sobresuscrito"] for f in resumen):
        print(f"AVISO: procesos > {fisicos} núcleos físicos: esos puntos están sobresuscritos y se analizan aparte.")


if __name__ == "__main__":
    main()
