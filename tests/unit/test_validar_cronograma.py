"""T07: validador del cronograma interno con el libro versionado y con libros sintéticos mínimos."""

import importlib.util
from pathlib import Path
import tempfile
import unittest
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("validar_cronograma", ROOT / "scripts" / "validar_cronograma.py")
vc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vc)

ROLES = ["R1", "R2", "R3", "R4", "R5", "R6"]

WORKBOOK = ('<?xml version="1.0" encoding="UTF-8"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            '<sheets><sheet name="Tareas" sheetId="1" r:id="rId1"/></sheets></workbook>')
RELS = ('<?xml version="1.0" encoding="UTF-8"?>'
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/'
        'relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')


def _celda(ref, valor):
    if isinstance(valor, int):
        return f'<c r="{ref}"><v>{valor}</v></c>'
    return f'<c r="{ref}" t="inlineStr"><is><t>{valor}</t></is></c>'


def tareas_base(ultima=58):
    """Una fila por tarea, con responsables rotando entre R1–R6 y revisor distinto."""
    filas = []
    for n in range(1, ultima + 1):
        resp = ROLES[(n - 1) % 6]
        filas.append({"A": f"T{n:02d}", "C": f"Tarea {n}", "D": resp, "E": ROLES[n % 6],
                      "F": 6, "G": 6, "H": 46300, "I": "Criterio verificable", "J": "No iniciado"})
    return filas


def escribir_libro(ruta, filas):
    cuerpo = []
    for i, fila in enumerate(filas, start=5):
        celdas = "".join(_celda(f"{col}{i}", valor) for col, valor in fila.items())
        cuerpo.append(f'<row r="{i}">{celdas}</row>')
    hoja = ('<?xml version="1.0" encoding="UTF-8"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            f'<sheetData>{"".join(cuerpo)}</sheetData></worksheet>')
    with ZipFile(ruta, "w") as libro:
        libro.writestr("xl/workbook.xml", WORKBOOK)
        libro.writestr("xl/_rels/workbook.xml.rels", RELS)
        libro.writestr("xl/worksheets/sheet1.xml", hoja)


class ValidarCronograma(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.ruta = Path(self._tmp.name) / "cronograma.xlsx"

    def tearDown(self):
        self._tmp.cleanup()

    def validar(self, filas):
        escribir_libro(self.ruta, filas)
        return vc.validate(self.ruta)

    def test_cronograma_versionado_es_valido(self):
        errores, responsables = vc.validate(ROOT / "cronograma" / "cronograma-interno.xlsx")
        self.assertEqual(errores, [])
        self.assertEqual(responsables["R5"], 1)
        self.assertEqual(responsables["Todos"], 1)

    def test_libro_completo_t01_t58_es_valido(self):
        errores, _ = self.validar(tareas_base())
        self.assertEqual(errores, [])

    def test_todos_es_responsable_valido_y_no_cuenta_para_un_rol(self):
        filas = tareas_base()
        filas[50]["D"] = "Todos"
        errores, responsables = self.validar(filas)
        self.assertEqual(errores, [])
        self.assertEqual(responsables["Todos"], 1)

    def test_rechaza_id_fuera_de_t01_t58(self):
        errores, _ = self.validar(tareas_base(59))
        self.assertIn("ID fuera de T01–T58: T59", errores)

    def test_detecta_tarea_faltante(self):
        errores, _ = self.validar(tareas_base(57))
        self.assertIn("Falta T58", errores)

    def test_cada_rol_necesita_al_menos_una_tarea(self):
        filas = tareas_base()
        for fila in filas:
            if fila["D"] == "R5":
                fila["D"], fila["E"] = "R1", "R2"
        errores, _ = self.validar(filas)
        self.assertIn("R5 (Miguel) no tiene tareas", errores)

    def test_rechaza_revisor_igual_al_responsable(self):
        filas = tareas_base()
        filas[0]["E"] = filas[0]["D"]
        errores, _ = self.validar(filas)
        self.assertIn("T01: el revisor coincide con el responsable 'R1'", errores)

    def test_rechaza_revisor_desconocido(self):
        filas = tareas_base()
        filas[0]["E"] = "Todos"
        errores, _ = self.validar(filas)
        self.assertIn("T01: revisor desconocido 'Todos'", errores)

    def test_estados_de_la_lista_del_libro(self):
        filas = tareas_base()
        for fila, estado in zip(filas, ("No iniciado", "En curso", "En riesgo", "Completado")):
            fila["J"] = estado
        filas[4]["J"] = "Bloqueado"
        errores, _ = self.validar(filas)
        self.assertEqual(errores, ["T05: estado no reconocido 'Bloqueado'"])


if __name__ == "__main__":
    unittest.main()
