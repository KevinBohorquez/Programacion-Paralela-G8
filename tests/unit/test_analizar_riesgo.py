"""T35: tabla Wilson, banda bootstrap, comparación El Niño/normal y figuras de analizar-riesgo.py."""

import csv
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "scripts" / "run"


def cargar(nombre, archivo):
    sys.path.insert(0, str(RUN))
    spec = importlib.util.spec_from_file_location(nombre, RUN / archivo)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


sys.path.insert(0, str(RUN))
comun = importlib.import_module("_comun_cientifico")
x6 = cargar("corrida_oficial", "corrida-oficial.py")
riesgo = cargar("analizar_riesgo", "analizar-riesgo.py")


def escribir_config(ruta, estacion, regimen, config_id, p01):
    ruta.write_text(
        f"estacion: {estacion}\nregimen: {regimen}\nconfig_id: {config_id}\nsemilla: 9\n"
        f"n: 1000\ndias: 120\np01: {p01}\np11: 0.3\nalfa: 0.7\ntheta: 5.5\n"
        f"capacidad: 6\numbral: 50\n", encoding="utf-8")
    return ruta


def prob(p):
    """Probabilidad sintética decreciente en C y creciente en p01."""
    return min(1.0, float(p["p01"]) * 2.0 / float(p["capacidad"]))


class AnalizarRiesgoTests(unittest.TestCase):
    def setUp(self):
        scratch = ROOT / "_build"
        scratch.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name)
        self.cfgs = [escribir_config(self.dir / "s1_normal.yaml", "s1", "normal", 0, 0.5),
                     escribir_config(self.dir / "s1_el_nino.yaml", "s1", "el_nino", 1, 1.0)]

    def correr_x6(self, n=1000):
        plan = x6.generar_plan(self.cfgs, [2, 4], n=n)
        salida = self.dir / "x6.csv"
        comun.ejecutar_plan(plan, salida=salida, logs=self.dir / "logs",
                            manifiesto=self.dir / "m.json", experimento="x6", backend="openmp",
                            build_dir=self.dir, hilos=1, procesos=1,
                            runner=comun.RunnerFalso(prob=prob))
        return salida

    def test_wilson_coincide_con_valores_de_referencia(self):
        inf, sup = comun.wilson(50, 100)
        self.assertAlmostEqual(inf, 0.40383, places=4)
        self.assertAlmostEqual(sup, 0.59617, places=4)
        self.assertEqual(comun.wilson(0, 10)[0], 0.0)
        self.assertEqual(comun.wilson(10, 10)[1], 1.0)
        self.assertEqual(comun.wilson(0, 0), (0.0, 1.0))

    def test_tabla_desde_csv_sintetico(self):
        filas = comun.leer_resultados(self.correr_x6())
        tabla = riesgo.tabla_riesgo(filas, [])
        self.assertEqual(len(tabla), 6)
        fila = next(t for t in tabla if t["regimen"] == "normal" and t["capacidad"] == 4.0)
        self.assertEqual((fila["k"], fila["n"]), (250, 1000))
        self.assertAlmostEqual(fila["p_hat"], 0.25)
        inf, sup = comun.wilson(250, 1000)
        self.assertAlmostEqual(fila["wilson_inf"], inf)
        self.assertAlmostEqual(fila["wilson_sup"], sup)
        self.assertEqual(fila["banda_inf"], "")
        self.assertIn("V6", fila["nota"])

    def test_con_duplicados_se_queda_con_el_mayor_n(self):
        salida = self.correr_x6(n=1000)
        plan = x6.generar_plan(self.cfgs[:1], [2], n=4000)
        comun.ejecutar_plan(plan, salida=salida, logs=self.dir / "logs", manifiesto=self.dir / "m.json",
                            experimento="x6", backend="openmp", build_dir=self.dir, hilos=1,
                            procesos=1, runner=comun.RunnerFalso(prob=prob))
        tabla = riesgo.tabla_riesgo(comun.leer_resultados(salida), [])
        fila = next(t for t in tabla if t["regimen"] == "normal" and t["capacidad"] == 2.0)
        self.assertEqual(fila["n"], 4000)

    def test_percentiles_de_la_banda(self):
        filas = [{"estacion": "s", "regimen": "normal", "capacidad": "6", "umbral": "50",
                  "k": str(i), "n": "100"} for i in range(1, 11)]
        banda = riesgo.banda_bootstrap(filas)
        inf, med, sup, k = banda[("s", "normal", 6.0, 50.0)]
        self.assertEqual(k, 10)
        self.assertAlmostEqual(inf, 0.01225)
        self.assertAlmostEqual(med, 0.055)
        self.assertAlmostEqual(sup, 0.09775)

    def test_plan_bootstrap_escribe_yaml_por_replica(self):
        boot = self.dir / "boot.csv"
        with boot.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["estacion", "regimen", "replica", "semilla_remuestreo", "p01", "p11", "alfa", "theta"])
            for reg in ("normal", "el_nino"):
                for r in range(1, 6):
                    w.writerow(["s1", reg, r, 1, f"0.{r}", "0.3", "0.7", "5.5"])
            w.writerow(["otra", "normal", 1, 1, "0.1", "0.3", "0.7", "5.5"])
        destino = self.dir / "cfg_boot"
        plan = riesgo.generar_plan_bootstrap(self.cfgs, comun.leer_resultados(boot), k=3,
                                             capacidades=[2, 6], n=500, destino=destino)
        self.assertEqual(len(plan), 2 * 3 * 2)
        self.assertEqual(len(list(destino.glob("*.yaml"))), 6)
        yaml = comun.leer_yaml_plano(destino / "s1_normal_b002.yaml")
        self.assertEqual((yaml["p01"], yaml["config_id"], yaml["estacion"]), ("0.2", "0", "s1"))
        self.assertEqual({p.n for p in plan}, {500})
        # Las réplicas difieren solo en parámetros: la reanudación las distingue.
        self.assertEqual(len({comun.clave_punto(p) for p in plan}), len(plan))

    def test_bootstrap_y_analisis_de_punta_a_punta(self):
        x6_csv = self.correr_x6()
        boot = self.dir / "boot.csv"
        with boot.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["estacion", "regimen", "replica", "semilla_remuestreo", "p01", "p11", "alfa", "theta"])
            for reg, base in (("normal", 0.5), ("el_nino", 1.0)):
                for r in range(1, 5):
                    w.writerow(["s1", reg, r, 1, f"{base * (0.9 + 0.05 * r):.6f}", "0.3", "0.7", "5.5"])
        tablas, figuras = self.dir / "tablas", self.dir / "figs"
        codigo = riesgo.main(["bootstrap", "--configs", *map(str, self.cfgs), "--bootstrap", str(boot),
                              "--k", "3", "--n", "1000", "--capacidades", "2,4",
                              "--salida", str(self.dir / "b.csv"), "--logs", str(self.dir / "logs"),
                              "--manifiesto", str(self.dir / "bm.json"), "--dir-configs",
                              str(self.dir / "cb"), "--runner-falso"])
        self.assertEqual(codigo, 0)
        codigo = riesgo.main(["analizar", "--x6", str(x6_csv), "--bootstrap-csv", str(self.dir / "b.csv"),
                              "--tablas", str(tablas), "--figuras", str(figuras)])
        self.assertEqual(codigo, 0)
        with (tablas / "riesgo.csv").open(encoding="utf-8", newline="") as f:
            filas = list(csv.DictReader(f))
        self.assertEqual(len(filas), 6)
        self.assertTrue(all(fila["banda_inf"] != "" for fila in filas if fila["capacidad"] in ("2", "4")))
        self.assertTrue((tablas / "riesgo.md").read_text(encoding="utf-8").startswith("#"))
        self.assertTrue((tablas / "comparacion_enso.csv").exists())
        for nombre in ("riesgo_s1", "riesgo_hist_s1", "riesgo_comparacion_enso"):
            for ext in ("png", "svg"):
                self.assertGreater((figuras / f"{nombre}.{ext}").stat().st_size, 0, nombre)

    def test_comparacion_enso(self):
        filas = comun.leer_resultados(self.correr_x6())
        comp = riesgo.comparacion_enso(riesgo.tabla_riesgo(filas, []))
        fila = next(c for c in comp if c["capacidad"] == 4.0)
        self.assertAlmostEqual(fila["p_normal"], 0.25)
        self.assertAlmostEqual(fila["p_el_nino"], 0.5)
        self.assertAlmostEqual(fila["riesgo_relativo"], 2.0)
        self.assertEqual(fila["ic_solapan"], 0)


if __name__ == "__main__":
    unittest.main()
