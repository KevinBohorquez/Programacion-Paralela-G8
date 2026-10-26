# T13 | Responsable: Lita | Revisión: Ashley | V6: validación estadística del generador de lluvia.
#
# Definición del proyecto, §7.7: se comparan la frecuencia de días lluviosos, la media y la desviación
# de la lluvia diaria, los percentiles 95 y 99, la longitud media de las rachas lluviosas y el máximo
# diario por temporada. Aceptación: error relativo <= 10 % en cada estadístico y Kolmogorov–Smirnov
# no rechazado al 5 % para los montos.
#
# Dos partes:
#   1. Frente al modelo: la referencia es el valor EXACTO que implica Markov + gamma con los mismos
#      parámetros. Verifica el código del generador; corre en CTest y en el CI.
#   2. Frente a lo observado (test_v6_frente_a_observado): series SENAMHI y parametros.csv de T06–T10,
#      que no están en Git. Se compara en la temporada de cada zona, la misma que usa calibrar.py
#      (costa norte y Chosica enero–abril; Lima junio–setiembre), con día lluvioso >= 0,1 mm.
#      Se omite si faltan los datos y no forma parte de CTest.
#
# Uso (tras compilar):  python3 -m pytest -v -s tests/unit/test_estadistico.py
# Variables opcionales: PP_V6_GENERADOR=<ruta a pp_v6_generador> (por defecto build/pp_v6_generador)
#                       PP_V6_N=<temporadas>  (por defecto 20000; la definición usa 10^8 para la corrida oficial)
#                       PP_V6_PARAMETROS, PP_V6_UMBRAL_LLUVIA, PP_V6_N_OBS (parte 2; ver más abajo)
import calendar
import csv
import datetime
import importlib.util
import math
import os
import statistics
import subprocess
from collections import defaultdict
from pathlib import Path

import numpy as np
import pytest
from scipy import integrate, stats

RAIZ = Path(__file__).resolve().parents[2]
GENERADOR = Path(os.environ.get("PP_V6_GENERADOR", RAIZ / "build" / "pp_v6_generador"))
N = int(os.environ.get("PP_V6_N", "20000"))
SEMILLA = 20261015
TOLERANCIA = 0.10
ALFA_KS = 0.05

# alfa < 1 recorre la rama gamma(a+1)·U^(1/a) de Marsaglia–Tsang; alfa > 1 la rama directa.
CASOS = {
    "sintetico_alfa_menor_1": dict(p01=0.15, p11=0.60, alfa=0.7, theta=9.0, dias=120),
    "alfa_mayor_1": dict(p01=0.25, p11=0.55, alfa=2.5, theta=6.0, dias=120),
    "lluvioso_persistente": dict(p01=0.40, p11=0.80, alfa=1.0, theta=12.0, dias=90),
}

pytestmark = pytest.mark.skipif(not GENERADOR.exists(),
                                reason=f"compile primero (cmake --build build); no existe {GENERADOR}")


def prob_lluvia_por_dia(p01, p11, dias):
    """P(día d lluvioso) con el día previo a la temporada seco, como simular_escenario."""
    p, salida = 0.0, []
    for _ in range(dias):
        p = p01 * (1.0 - p) + p11 * p
        salida.append(p)
    return salida


def esperados(p01, p11, alfa, theta, dias):
    gamma = stats.gamma(alfa, scale=theta)
    pd = prob_lluvia_por_dia(p01, p11, dias)

    # Racha cerrada = transición lluvia→seco dentro de la temporada. Los días que forman rachas cerradas
    # son todos los lluviosos menos los de la racha abierta al final de la temporada.
    cerradas = sum(pd[d] * (1.0 - p11) for d in range(dias - 1))
    abiertas = sum(pd[d] * p11 ** (dias - 1 - d) for d in range(dias))
    racha_media = (sum(pd) - abiertas) / cerradas

    def cdf_maximo(x):  # P(max diario de la temporada <= x); sin lluvia el máximo es 0
        seco, lluvia = 1.0, 0.0
        f = gamma.cdf(x)
        for _ in range(dias):
            seco, lluvia = seco * (1 - p01) + lluvia * (1 - p11), (seco * p01 + lluvia * p11) * f
        return seco + lluvia

    max_medio, _ = integrate.quad(lambda x: 1.0 - cdf_maximo(x), 0.0, math.inf, limit=200)
    return {
        "frecuencia_lluvia": sum(pd) / dias,
        "media_monto": alfa * theta,
        "desviacion_monto": math.sqrt(alfa) * theta,
        "p95_monto": gamma.ppf(0.95),
        "p99_monto": gamma.ppf(0.99),
        "racha_media": racha_media,
        "max_diario_temporada_medio": max_medio,
    }


def correr_generador(params, n=N):
    cmd = [str(GENERADOR), "--n", str(n), "--semilla", str(SEMILLA)]
    for clave, valor in params.items():
        cmd += [f"--{clave}", str(valor)]
    r = subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=1800)
    return dict(linea.split("=", 1) for linea in r.stdout.splitlines() if "=" in linea)


@pytest.fixture(scope="module", params=list(CASOS))
def caso(request):
    params = CASOS[request.param]
    return request.param, params, correr_generador(params), esperados(**params)


def test_v6_estadisticos_dentro_de_10_por_ciento(caso):
    nombre, params, obs, esp = caso
    print(f"\n[V6] caso={nombre} N={N} semilla={SEMILLA} params={params} dias_simulados={obs['dias']}")
    print(f"[V6] {'estadistico':28s} {'esperado':>14s} {'observado':>14s} {'error_rel':>10s}")
    fallos = []
    for clave, valor_esp in esp.items():
        valor_obs = float(obs[clave])
        error = abs(valor_obs - valor_esp) / abs(valor_esp)
        print(f"[V6] {clave:28s} {valor_esp:14.6f} {valor_obs:14.6f} {error:10.4%}")
        if error > TOLERANCIA:
            fallos.append(f"{clave}: esperado {valor_esp:.6g}, observado {valor_obs:.6g} ({error:.2%})")
    assert not fallos, f"{nombre}: error relativo > {TOLERANCIA:.0%} en " + "; ".join(fallos)


def test_v6_kolmogorov_smirnov_montos(caso):
    nombre, params, obs, _ = caso
    muestra = [float(x) for x in obs["muestra"].split(";")]
    resultado = stats.kstest(muestra, "gamma", args=(params["alfa"], 0.0, params["theta"]))
    print(f"\n[V6] caso={nombre} KS n={len(muestra)} D={resultado.statistic:.5f} p={resultado.pvalue:.4f} "
          f"(se rechaza si p < {ALFA_KS})")
    assert len(muestra) >= 1000
    assert resultado.pvalue >= ALFA_KS, f"{nombre}: KS rechaza gamma(alfa, theta) con p={resultado.pvalue:.4g}"


def test_v6_reproducible_con_semilla_fija():
    params = CASOS["sintetico_alfa_menor_1"]
    assert correr_generador(params) == correr_generador(params)


def test_v6_control_negativo_detecta_parametros_equivocados():
    """Si el generador usara otro theta, V6 debe notarlo; si no, un 'pasa' no valdría nada."""
    params = CASOS["alfa_mayor_1"]
    obs = correr_generador(params)
    esp = esperados(**dict(params, theta=params["theta"] * 1.3))
    assert abs(float(obs["media_monto"]) - esp["media_monto"]) / esp["media_monto"] > TOLERANCIA
    muestra = [float(x) for x in obs["muestra"].split(";")]
    assert stats.kstest(muestra, "gamma", args=(params["alfa"], 0.0, params["theta"] * 1.3)).pvalue < ALFA_KS


# ---------- V6 frente a lo OBSERVADO (series SENAMHI de T06–T10, fuera de Git) ----------
# Se omite si faltan data/raw/*.csv o data/processed/{parametros,regimenes}.csv (p. ej. en el CI).
DATOS_RAW = RAIZ / "data" / "raw"
PARAMETROS = Path(os.environ.get("PP_V6_PARAMETROS", RAIZ / "data" / "processed" / "parametros.csv"))
REGIMENES = RAIZ / "data" / "processed" / "regimenes.csv"
# Umbral de día lluvioso en la serie OBSERVADA; debe ser el mismo con el que se calibró parametros.csv
# (definición §7.6: >= 0,1 mm; 0 significa > 0). En lo simulado todo día lluvioso del modelo cuenta,
# porque la gamma se ajustó a esos días.
UMBRAL_LLUVIA = float(os.environ.get("PP_V6_UMBRAL_LLUVIA", "0.1"))
N_OBS = int(os.environ.get("PP_V6_N_OBS", "20000"))  # temporadas simuladas por grupo


def temporada_de(estacion):
    """Meses y días de la temporada de la estación, tomados de calibrar.py (T10) para usar la misma
    ventana que la calibración: costa norte y Chosica enero–abril (120 d), Lima junio–setiembre (122 d)."""
    spec = importlib.util.spec_from_file_location("calibrar_t10", RAIZ / "scripts" / "run" / "calibrar.py")
    calibrar = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(calibrar)
    meses = calibrar.meses_temporada_de(estacion, calibrar.cargar_zonas().get(estacion, "costa_norte"))
    return meses, sum(calendar.monthrange(2001, m)[1] for m in meses)  # 2001: año no bisiesto


def grupos_calibrados():
    if not (PARAMETROS.exists() and REGIMENES.exists() and any(DATOS_RAW.glob("*.csv"))):
        return [pytest.param(None, None, None, marks=pytest.mark.skip(reason="faltan los datos SENAMHI de T06–T10"))]
    with PARAMETROS.open(newline="", encoding="utf-8") as f:
        return [pytest.param(fila["estacion"], fila["regimen"],
                             {k: float(fila[k]) for k in ("p01", "p11", "alfa", "theta")},
                             id=f"{fila['estacion']}-{fila['regimen']}")
                for fila in csv.DictReader(f)]


def estadisticos_observados(estacion, regimen, umbral, meses):
    """Meses de la temporada en los años de regimenes.csv con ese régimen. Un día faltante o un salto de
    fechas corta la racha abierta sin contarla, igual que el auxiliar solo cuenta rachas cerradas."""
    with REGIMENES.open(newline="", encoding="utf-8") as f:
        anios = {int(r["anio"]) for r in csv.DictReader(f) if r["estacion"] == estacion and r["regimen"] == regimen}
    dias = rachas = dias_en_rachas = racha = 0
    montos, max_anio, previa = [], defaultdict(float), None
    with (DATOS_RAW / f"{estacion}.csv").open(newline="", encoding="utf-8") as f:
        for fila in csv.DictReader(f):
            fecha = datetime.date.fromisoformat(fila["fecha"])
            if fecha.year not in anios or fecha.month not in meses:
                previa, racha = None, 0
                continue
            if previa is None or (fecha - previa).days != 1:
                racha = 0
            previa = fecha
            texto = fila["precipitacion_mm"]
            if texto == "" or float(texto) < 0:
                racha = 0
                continue
            v = float(texto)
            dias += 1
            max_anio[fecha.year] = max(max_anio[fecha.year], v)
            if (v >= umbral) if umbral > 0 else (v > 0):
                montos.append(v)
                racha += 1
            elif racha:
                rachas, dias_en_rachas, racha = rachas + 1, dias_en_rachas + racha, 0
    return {
        "frecuencia_lluvia": len(montos) / dias,
        "media_monto": statistics.mean(montos),
        "desviacion_monto": statistics.stdev(montos),
        "p95_monto": float(np.percentile(montos, 95)),
        "p99_monto": float(np.percentile(montos, 99)),
        "racha_media": dias_en_rachas / rachas,
        "max_diario_temporada_medio": statistics.mean(max_anio.values()),
    }, montos, len(anios)


@pytest.mark.parametrize("estacion,regimen,params", grupos_calibrados())
def test_v6_frente_a_observado(estacion, regimen, params):
    meses, dias = temporada_de(estacion)
    esp, montos_obs, n_anios = estadisticos_observados(estacion, regimen, UMBRAL_LLUVIA, meses)
    sim = correr_generador(dict(params, dias=dias), n=N_OBS)
    muestra = [float(x) for x in sim["muestra"].split(";") if x]
    ks = stats.ks_2samp(montos_obs, muestra)
    print(f"\n[V6-obs] {estacion}/{regimen} meses={meses} anios={n_anios} dias_lluviosos_obs={len(montos_obs)} "
          f"umbral={UMBRAL_LLUVIA} mm N_sim={N_OBS}x{dias} d params={params}")
    print(f"[V6-obs] {'estadistico':28s} {'observado':>12s} {'simulado':>12s} {'error_rel':>10s}")
    fallos = []
    for clave, valor_obs in esp.items():
        valor_sim = float(sim[clave])
        error = abs(valor_sim - valor_obs) / abs(valor_obs)
        print(f"[V6-obs] {clave:28s} {valor_obs:12.4f} {valor_sim:12.4f} {error:10.2%}{'  <-- >10%' if error > TOLERANCIA else ''}")
        if error > TOLERANCIA:
            fallos.append(f"{clave} {error:.0%}")
    print(f"[V6-obs] KS dos muestras: D={ks.statistic:.4f} p={ks.pvalue:.4g} (n_obs={len(montos_obs)}, n_sim={len(muestra)})")
    if ks.pvalue < ALFA_KS:
        fallos.append(f"KS p={ks.pvalue:.2g}")
    assert not fallos, f"{estacion}/{regimen}: " + "; ".join(fallos)
