#!/usr/bin/env python3
"""T34 | Responsable: Miguel | Corrida científica oficial X6 en CPU.

Corre el simulador para cada configuración estación × régimen (config/<estacion>_<regimen>.yaml, 10
archivos) y cada capacidad C de una grilla (más la C de la propia configuración), con el umbral
oficial U del YAML (50 mm) y N escenarios por punto. Cada punto agrega una fila del contrato
(docs/contratos.md §5, con hist512) a results/cientifico/x6.csv.

- Semillas fijas: `semilla` y `config_id` de cada YAML (números aleatorios comunes entre capacidades,
  ver scripts/run/_comun_cientifico.py); quedan en el manifiesto.
- Reanudable: los puntos (estación, régimen, C, U, N, parámetros) que ya están en el CSV se omiten.
- Logs del simulador en results/cientifico/logs/; manifiesto JSON con commit, hardware, semillas y
  duración de cada punto en results/cientifico/x6_manifiesto.json.

Uso (en la imagen pp-g8, tras compilar en build-c):
    python3 scripts/run/corrida-oficial.py --dry-run
    python3 scripts/run/corrida-oficial.py --n 1e7 --backend openmp --hilos 16
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _comun_cientifico as comun  # noqa: E402


def generar_plan(configs: list[Path], capacidades: list[float], n: float,
                 umbral: float | None = None) -> list[comun.Punto]:
    """Un punto por configuración y capacidad (grilla ∪ capacidad del YAML), en orden de C."""
    plan = []
    for ruta in configs:
        base = comun.punto_desde_config(ruta, umbral=umbral, n=n)
        for c in sorted({float(x) for x in capacidades} | {base.capacidad}):
            plan.append(comun.punto_desde_config(ruta, capacidad=c, umbral=umbral, n=n))
    return plan


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    comun.agregar_args_ejecucion(ap, "results/cientifico/x6.csv",
                                 "results/cientifico/x6_manifiesto.json", 1e7)
    ap.add_argument("--capacidades", default=",".join(map(str, comun.CAPACIDADES_X6)),
                    help="grilla de C en mm/día, separada por comas (se agrega la C del YAML)")
    ap.add_argument("--umbral", type=float, default=None, help="U en mm (por defecto, el del YAML)")
    args = ap.parse_args(argv)

    configs = args.configs or comun.configs_por_defecto()
    if not configs:
        print("error: no hay configuraciones")
        return 2
    if not comun.verificar_binario(args):
        return 2
    plan = generar_plan(configs, comun.lista_numeros(args.capacidades), args.n, args.umbral)
    resumen = comun.ejecutar_plan(
        plan, salida=args.salida, logs=args.logs, manifiesto=args.manifiesto, experimento="x6",
        backend=args.backend, build_dir=args.build_dir, hilos=args.hilos, procesos=args.procesos,
        runner=comun.runner_de(args), dry_run=args.dry_run,
        extra={"capacidades": args.capacidades, "n": int(args.n)})
    if not args.dry_run:
        print(f"[x6] corridos={resumen['corridos']} omitidos={resumen['omitidos']} "
              f"errores={resumen['errores']} -> {args.salida}")
    return 1 if resumen["errores"] else 0


if __name__ == "__main__":
    sys.exit(main())
