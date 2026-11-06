"""Wilson, huella del histograma, curva P(Amax > u) y lectura mínima de config/*.yaml."""
from __future__ import annotations

import hashlib
import math
from pathlib import Path

Z95 = 1.959963984540054  # el mismo z que pp::wilson


def wilson(k: int, n: int, z: float = Z95) -> tuple[float, float]:
    """Intervalo de Wilson al 95 %, igual a src/stats/wilson.cpp."""
    if n == 0:
        return 0.0, 1.0
    p = k / n
    z2 = z * z
    den = 1.0 + z2 / n
    centro = (p + z2 / (2.0 * n)) / den
    mitad = z * math.sqrt(p * (1.0 - p) / n + z2 / (4.0 * n * n)) / den
    lo, hi = max(0.0, centro - mitad), min(1.0, centro + mitad)
    if k == 0:
        lo = 0.0
    if k == n:
        hi = 1.0
    return lo, hi


def leer_hist(texto: str) -> list[int]:
    """Columna hist512 del CSV (512 enteros separados por `;`)."""
    return [int(x) for x in texto.strip().split(";")]


def huella(hist: list[int]) -> str:
    """SHA-256 corto (12 hex) del vector hist512, calculado sobre su forma CSV `h0;h1;...;h511`."""
    return hashlib.sha256(";".join(str(h) for h in hist).encode()).hexdigest()[:12]


def curva_riesgo(hist: list[int]) -> dict:
    """P(Amax > u) para u = 1, 2, ... mm desde el histograma de clases de 1 mm.

    La clase b cuenta floor(Amax) = b, así que Amax > u (u entero >= 1) equivale a floor(Amax) >= u
    salvo el empate exacto Amax = u. u = 0 no se puede leer (la clase 0 mezcla 0 y (0, 1)).
    La curva termina en el primer u con probabilidad 0 (incluido).
    """
    n = sum(hist)
    us, ps, los, his = [], [], [], []
    cola = n - hist[0] if hist else 0
    for u in range(1, len(hist)):
        k = cola
        lo, hi = wilson(k, n)
        us.append(u)
        ps.append(k / n if n else 0.0)
        los.append(lo)
        his.append(hi)
        if k == 0:
            break
        cola -= hist[u]
    return {"u": us, "p": ps, "lo": los, "hi": his, "n": n}


def leer_yaml_plano(texto: str) -> dict[str, str]:
    """Pares `clave: valor` sin anidar; `#` inicia un comentario (docs/contratos.md §3)."""
    datos = {}
    for linea in texto.splitlines():
        linea = linea.split("#", 1)[0].strip()
        if ":" not in linea:
            continue
        clave, valor = linea.split(":", 1)
        datos[clave.strip()] = valor.strip().strip("'\"")
    return datos


def listar_configs(directorio: Path) -> list[dict]:
    salida = []
    for ruta in sorted(directorio.glob("*.yaml")):
        d = leer_yaml_plano(ruta.read_text(encoding="utf-8"))
        salida.append({"id": ruta.stem, "estacion": d.get("estacion", "sintetica"),
                       "regimen": d.get("regimen", "normal"),
                       "c": float(d.get("capacidad", 0) or 0), "u": float(d.get("umbral", 0) or 0)})
    return salida
