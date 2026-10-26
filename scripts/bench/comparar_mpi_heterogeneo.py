#!/usr/bin/env python3
# T32 | Responsable: Lita (infraestructura: Miguel) | Comparación MPI estático/dinámico sobre nodos heterogéneos.
"""Compara E1 (pp_mpi_estatico) y E2 (pp_mpi_dinamico) con los MISMOS procesos, carga y semilla
repartidos entre varios nodos, usando ejecutar_barridos.py como biblioteca.

Por cada número de procesos: calentamiento + --reps repeticiones de cada esquema, verificación de k
entre ambos (deben coincidir), desbalance = max/media del trabajo (n_local) de los rangos que
trabajan (en E2 el maestro, rango 0, no procesa escenarios) y trabajo por nodo, asignando los rangos
con `--map-by slot` (llenan los slots de cada host en orden).

En nodos heterogéneos E1 reparte N/P fijo y espera al rango más lento; E2 da más bloques a los
nodos rápidos: su trabajo por nodo debería inclinarse hacia ellos. En un solo anfitrión (Compose)
los nodos son iguales y se espera desbalance ~1 en ambos.

Salidas: CSV completo (una fila por esquema y procesos), CSV resumen y una tabla Markdown en stdout.

Ejemplos (dentro del contenedor lanzador):
  python3 scripts/bench/comparar_mpi_heterogeneo.py --n 2e7 --procesos 4,8 \\
      --hosts nodo1:4,nodo2:4 --red-tcp eth0 --build-dir /opt/pp/build
  python3 scripts/bench/comparar_mpi_heterogeneo.py --n 2e5 --procesos 2 --reps 1 --build-dir build/docker
"""
import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _comun_bench as cb  # noqa: E402
import ejecutar_barridos as eb  # noqa: E402

ESQUEMAS = {"mpi_estatico": "e1", "mpi_dinamico": "e2"}


def construir_parser():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=float, default=2e7)
    ap.add_argument("--procesos", default="4", help="lista separada por comas")
    ap.add_argument("--hosts", default="")
    ap.add_argument("--hostfile", default="")
    ap.add_argument("--red-tcp", default="")
    ap.add_argument("--lote", type=int, default=0)
    ap.add_argument("--reps", type=int, default=5)
    ap.add_argument("--referencia", default="primera", choices=["serial", "primera", "ninguna"],
                    help="primera: E2 debe dar el mismo k que E1 (sin correr el secuencial)")
    ap.add_argument("--build-dir", default=str(eb.RAIZ / "build" / "docker"))
    ap.add_argument("--config", default=str(eb.RAIZ / "config" / "sintetico.yaml"))
    ap.add_argument("--semilla", type=int, default=20261015)
    ap.add_argument("--bind-mpi", default="")
    ap.add_argument("--salida", default=str(eb.RAIZ / "results" / "bench" / "mpi_heterogeneo.csv"))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--permitir-debug", action="store_true")
    return ap


def argumentos_ejecutor(a):
    """Traduce los argumentos de este script a los de ejecutar_barridos.py (x3 con una carga)."""
    args = ["--experimento", "x3", "--backend", "mpi_estatico,mpi_dinamico", "--recursos", a.procesos,
            "--cargas", str(int(a.n)), "--reps", str(a.reps), "--referencia", a.referencia,
            "--build-dir", a.build_dir, "--config", a.config, "--semilla", str(a.semilla),
            "--salida", a.salida]
    for bandera, valor in (("--hosts", a.hosts), ("--hostfile", a.hostfile), ("--red-tcp", a.red_tcp),
                           ("--bind-mpi", a.bind_mpi)):
        if valor:
            args += [bandera, valor]
    if a.lote:
        args += ["--lote", str(a.lote)]
    if a.dry_run:
        args.append("--dry-run")
    if a.permitir_debug:
        args.append("--permitir-debug")
    return args


def trabajo_nodos_texto(hosts, procesos, trabajo_rangos):
    """'nodo1=..;nodo2=..' a partir del n_local por rango ('a;b;c')."""
    if not trabajo_rangos:
        return ""
    trabajos = [int(x) for x in str(trabajo_rangos).split(";")]
    total = cb.trabajo_por_nodo(cb.asignar_rangos(hosts, int(procesos)), trabajos)
    return ";".join(f"{h}={t}" for h, t in total.items())


def resumir(filas, hosts):
    """Una fila por (procesos, n) con E1 y E2 lado a lado."""
    grupos = {}
    for f in filas:
        clave = (int(f["procesos"]), int(f["n"]))
        grupos.setdefault(clave, {})[ESQUEMAS[f["backend"]]] = f
    resumen = []
    for (procesos, n), g in grupos.items():
        r = dict(procesos=procesos, n=n)
        for e in ("e1", "e2"):
            f = g.get(e)
            r[f"t_{e}"] = float(f["media"]) if f else ""
            r[f"sd_{e}"] = float(f["desviacion"]) if f else ""
            r[f"desbalance_{e}"] = float(f["desbalance"]) if f and f.get("desbalance") not in ("", None) else ""
            r[f"nodos_{e}"] = trabajo_nodos_texto(hosts, procesos, f.get("trabajo_rangos")) if f else ""
        ambos = "e1" in g and "e2" in g
        r["razon_e2_e1"] = r["t_e2"] / r["t_e1"] if ambos and r["t_e1"] else ""
        r["mas_rapido"] = ("E2" if r["t_e2"] < r["t_e1"] else "E1") if ambos else ""
        r["equivalentes"] = int(all(str(f["equivalente"]) == "1" for f in g.values()))
        resumen.append(r)
    return resumen


def _fmt(x, dec):
    return f"{x:.{dec}f}" if isinstance(x, float) else str(x)


def tabla_markdown(resumen):
    cab = ["procesos", "n", "t_E1 (s)", "t_E2 (s)", "E2/E1", "más rápido", "desb. E1", "desb. E2",
           "trabajo por nodo E1", "trabajo por nodo E2", "V1"]
    lineas = ["| " + " | ".join(cab) + " |", "|" + "---|" * len(cab)]
    for r in resumen:
        celdas = [r["procesos"], r["n"], _fmt(r["t_e1"], 4), _fmt(r["t_e2"], 4), _fmt(r["razon_e2_e1"], 3),
                  r["mas_rapido"], _fmt(r["desbalance_e1"], 3), _fmt(r["desbalance_e2"], 3), r["nodos_e1"],
                  r["nodos_e2"], "ok" if r["equivalentes"] else "FALLA"]
        lineas.append("| " + " | ".join(str(c) for c in celdas) + " |")
    return "\n".join(lineas)


def main(argv=None):
    a = construir_parser().parse_args(argv)
    args_eb = argumentos_ejecutor(a)
    codigo = eb.main(args_eb)
    if a.dry_run or codigo not in (0, 2):
        return codigo
    hosts = cb.parsear_hosts(a.hosts) if a.hosts else (cb.leer_hostfile(a.hostfile) if a.hostfile else [])
    with open(a.salida, newline="") as f:
        filas = list(csv.DictReader(f))
    resumen = resumir(filas, hosts)
    ruta_resumen = Path(a.salida).with_name(Path(a.salida).stem + "_resumen.csv")
    with open(ruta_resumen, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(resumen[0].keys()))
        w.writeheader()
        w.writerows(resumen)
    tabla = tabla_markdown(resumen)
    Path(a.salida).with_name(Path(a.salida).stem + "_resumen.md").write_text(tabla + "\n", encoding="utf-8")
    print(tabla)
    print(f"escrito {ruta_resumen}")
    return codigo


if __name__ == "__main__":
    sys.exit(main())
