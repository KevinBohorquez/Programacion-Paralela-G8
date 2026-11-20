"""T07: comprueba el tablero de tareas del cronograma interno sin dependencias externas."""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import posixpath
import re
import sys
from xml.etree import ElementTree as ET
from zipfile import ZipFile


MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
ROLES = {"R1": "David", "R2": "Angela", "R3": "Ashley", "R4": "Lita", "R5": "Miguel", "R6": "Rhamses"}
TEAM = "Todos"  # tarea del equipo completo: válida, pero no cuenta para ningún rol
LAST = 61
EXPECTED = {f"T{number:02d}" for number in range(1, LAST + 1)}
RANGE = f"T01–T{LAST}"
STATES = {"No iniciado", "En curso", "En riesgo", "Completado"}  # lista de validación de la columna J
REQUIRED = {"C": "tarea", "D": "responsable", "F": "semana inicial", "G": "semana final",
            "H": "fecha límite", "I": "criterio de terminado", "J": "estado"}


def _shared_strings(archive: ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    return ["".join(node.itertext()) for node in root.findall(f"{{{MAIN}}}si")]


def _sheet_path(archive: ZipFile, name: str) -> str:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    sheet = next((node for node in workbook.findall(f".//{{{MAIN}}}sheet")
                  if node.attrib.get("name") == name), None)
    if sheet is None:
        raise ValueError(f"No existe la hoja {name!r}")
    relationship_id = sheet.attrib[f"{{{REL}}}id"]
    relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    relation = next(node for node in relationships.findall(f"{{{PKG_REL}}}Relationship")
                    if node.attrib.get("Id") == relationship_id)
    target = relation.attrib["Target"]
    return target.lstrip("/") if target.startswith("/") else posixpath.normpath(posixpath.join("xl", target))


def _cell_value(cell: ET.Element, strings: list[str]) -> str:
    kind = cell.attrib.get("t")
    if kind == "inlineStr":
        inline = cell.find(f"{{{MAIN}}}is")
        return "" if inline is None else "".join(inline.itertext()).strip()
    value = cell.find(f"{{{MAIN}}}v")
    if value is None or value.text is None:
        return ""
    return strings[int(value.text)] if kind == "s" else value.text.strip()


def validate(path: Path) -> tuple[list[str], Counter[str]]:
    errors: list[str] = []
    with ZipFile(path) as archive:
        strings = _shared_strings(archive)
        sheet = ET.fromstring(archive.read(_sheet_path(archive, "Tareas")))
    records: dict[str, dict[str, str]] = {}
    seen: Counter[str] = Counter()
    owners: Counter[str] = Counter()
    for row in sheet.findall(f".//{{{MAIN}}}sheetData/{{{MAIN}}}row"):
        cells = {re.match(r"[A-Z]+", cell.attrib["r"]).group(): _cell_value(cell, strings)
                 for cell in row.findall(f"{{{MAIN}}}c")}
        task_id = cells.get("A", "")
        if not re.fullmatch(r"T\d{2}", task_id):
            continue
        seen[task_id] += 1
        records[task_id] = cells
        owner = cells.get("D", "")
        owners[owner] += 1
        if owner not in ROLES and owner != TEAM:
            errors.append(f"{task_id}: responsable desconocido {owner!r}")
        reviewer = cells.get("E", "")
        if reviewer and reviewer not in ROLES:
            errors.append(f"{task_id}: revisor desconocido {reviewer!r}")
        elif reviewer and reviewer == owner:
            errors.append(f"{task_id}: el revisor coincide con el responsable {owner!r}")
        for column, label in REQUIRED.items():
            if not cells.get(column, "").strip():
                errors.append(f"{task_id}: falta {label} (columna {column})")
        if cells.get("J") not in STATES:
            errors.append(f"{task_id}: estado no reconocido {cells.get('J')!r}")
    for task_id in sorted(EXPECTED - records.keys()):
        errors.append(f"Falta {task_id}")
    for task_id in sorted(records.keys() - EXPECTED):
        errors.append(f"ID fuera de {RANGE}: {task_id}")
    for task_id, count in sorted(seen.items()):
        if count != 1:
            errors.append(f"{task_id} aparece {count} veces")
    for role in ROLES:
        if owners[role] == 0:
            errors.append(f"{role} ({ROLES[role]}) no tiene tareas")
    return errors, owners


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workbook", nargs="?", type=Path,
                        default=Path(__file__).resolve().parents[1] / "cronograma" / "cronograma-interno.xlsx")
    args = parser.parse_args()
    try:
        errors, owners = validate(args.workbook)
    except (OSError, ValueError, KeyError) as exc:
        print(f"No se pudo revisar {args.workbook}: {exc}", file=sys.stderr)
        return 2
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"T07 correcto: {RANGE} únicos, con responsable, revisor distinto, semanas, fecha, estado y criterio.")
    print("Distribución: " + ", ".join(f"{ROLES[role]} {owners[role]}" for role in ROLES)
          + f", {TEAM} {owners[TEAM]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
