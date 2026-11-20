"""T13 (H5): cruce de X6/X7 sin H5 y con H5 de comparar_h5.py con tablas sintéticas, sin simular."""

import csv
import importlib.util
import math
from pathlib import Path
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "scripts" / "run"

sys.path.insert(0, str(RUN))
_spec = importlib.util.spec_from_file_location("comparar_h5", RUN / "comparar_h5.py")
h5 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(h5)


def escribir_csv(ruta, campos, filas):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=campos, lineterminator="\n")
        w.writeheader()
        w.writerows(filas)


def riesgo(estacion, regimen, capacidad, p, banda=("", "")):
    return {"estacion": estacion, "regimen": regimen, "capacidad": capacidad, "umbral": "50",
            "p_hat": p, "banda_inf": banda[0], "banda_sup": banda[1]}


def escribir_tablas(carpeta, riesgos, sensibilidad, enso):
    escribir_csv(carpeta / "riesgo.csv",
                 ["estacion", "regimen", "capacidad", "umbral", "p_hat", "banda_inf", "banda_sup"], riesgos)
    escribir_csv(carpeta / "sensibilidad.csv", ["estacion", "regimen", "capacidad", "umbral", "p_hat"],
                 sensibilidad)
    escribir_csv(carpeta / "comparacion_enso.csv", ["estacion", "capacidad", "umbral", "riesgo_relativo"], enso)


class CompararH5Tests(unittest.TestCase):
    def setUp(self):
        scratch = ROOT / "_build"
        scratch.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=scratch)
        self.addCleanup(self.temp.cleanup)
        self.dir = Path(self.temp.name)
        self.sin, self.con = self.dir / "sin", self.dir / "con"
        escribir_tablas(
            self.sin,
            [riesgo("a", "normal", "6", "0.25", ("0.2", "0.3")), riesgo("a", "normal", "8", "0.1"),
             riesgo("a", "el_nino", "6.000000001", "0"), riesgo("b", "normal", "6", "0.5")],
            [{"estacion": "a", "regimen": "normal", "capacidad": "6", "umbral": "30", "p_hat": "0.4"},
             {"estacion": "a", "regimen": "normal", "capacidad": "6", "umbral": "80", "p_hat": "0.2"}],
            [{"estacion": "a", "capacidad": "6", "umbral": "50", "riesgo_relativo": "3.6"},
             {"estacion": "a", "capacidad": "8", "umbral": "50", "riesgo_relativo": "9"}])
        escribir_tablas(
            self.con,
            [riesgo("a", "normal", "6", "0.30"), riesgo("a", "normal", "8", "0.2"),
             riesgo("a", "el_nino", "6", "0.6")],
            [{"estacion": "a", "regimen": "normal", "capacidad": "6", "umbral": "30", "p_hat": "0.5"}],
            [{"estacion": "a", "capacidad": "6", "umbral": "50", "riesgo_relativo": ""}])

    def test_x6_solo_la_capacidad_de_referencia_y_grupos_comunes(self):
        x6, _, _ = h5.comparar(self.sin, self.con, 6.0)
        self.assertEqual([(f["estacion"], f["regimen"], f["capacidad"]) for f in x6],
                         [("a", "el_nino", 6.0), ("a", "normal", 6.0)])  # "b" solo está sin H5
        normal = x6[1]
        self.assertAlmostEqual(normal["p_sin_h5"], 0.25)
        self.assertAlmostEqual(normal["p_con_h5"], 0.30)
        self.assertAlmostEqual(normal["cambio_absoluto"], 0.05)
        self.assertAlmostEqual(normal["razon"], 1.2)
        self.assertEqual(normal["banda_sin_h5"], "0.2–0.3")
        self.assertEqual(normal["banda_con_h5"], "—")

    def test_razon_indefinida_si_sin_h5_es_cero(self):
        x6, _, _ = h5.comparar(self.sin, self.con, 6.0)
        el_nino = x6[0]
        self.assertAlmostEqual(el_nino["cambio_absoluto"], 0.6)
        self.assertTrue(math.isnan(el_nino["razon"]))

    def test_x7_y_enso_cruzan_por_clave(self):
        _, x7, enso = h5.comparar(self.sin, self.con, 6.0)
        self.assertEqual([(f["umbral"], f["p_sin_h5"], f["p_con_h5"]) for f in x7], [(30.0, 0.4, 0.5)])
        self.assertEqual(enso, [{"estacion": "a", "riesgo_relativo_sin_h5": 3.6, "riesgo_relativo_con_h5": "—"}])

    def test_main_escribe_las_tablas(self):
        destino = self.dir / "salida"
        h5.main(["--sin", str(self.sin), "--con", str(self.con), "--destino", str(destino)])
        with (destino / "comparacion_h5_x6.csv").open(encoding="utf-8", newline="") as f:
            filas = list(csv.DictReader(f))
        self.assertEqual(len(filas), 2)
        self.assertEqual(filas[0]["razon"], "")  # nan se escribe vacío
        for nombre in ("comparacion_h5_x7.csv", "comparacion_h5_x6.md", "comparacion_h5_x7.md",
                       "comparacion_h5_enso.md"):
            self.assertTrue((destino / nombre).exists(), nombre)


if __name__ == "__main__":
    unittest.main()
