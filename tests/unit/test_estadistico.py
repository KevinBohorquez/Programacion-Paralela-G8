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
#   2. Frente a lo observado (test_v6_frente_a_observado): series SENAMHI y parametros.csv de T06–T10.
#      Se compara en la temporada de cada zona, la misma que usa calibrar.py (costa norte y Chosica
#      enero–abril; Lima junio–setiembre), con día lluvioso >= 0,1 mm. Aquí la referencia es una MUESTRA
#      de 17–30 temporadas, no un valor exacto, así que el criterio tiene en cuenta su incertidumbre
#      (ver docs/validacion-v6.md §«Criterio estadístico»):
#        - cada estadístico pasa si el error relativo es <= 10 % (criterio de la definición) o si el valor
#          simulado cae dentro del IC bootstrap del observado, remuestreando temporadas completas;
#        - KS compara los montos tal como los registraría un pluviómetro (redondeo a 0,1 mm y >= 0,1 mm) y
#          su valor p sale de un bootstrap paramétrico con el mismo número de temporadas que lo observado;
#        - los 8 contrastes de un grupo (7 estadísticos + KS) se corrigen con Bonferroni: 5 % por grupo.
#      Los grupos que no pasan con el modelo vigente están en FALLOS_CONOCIDOS como xfail estricto.
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


# Grupos que NO pasan con el modelo vigente (Markov + gamma + escala por temporada H5, parámetros de T10).
# Serían limitaciones del modelo documentadas en docs/validacion-v6.md, no errores de código, y se marcan
# como xfail ESTRICTO: si un cambio del modelo o de la calibración los hace pasar, la prueba falla con
# XPASS y obliga a actualizar esta lista y el documento.
# Con H5 (kappa calibrado por grupo) los 16 grupos pasan los estadísticos y KS, y las listas quedan vacías.
# Sin H5 (kappa = inf) fallaban 3 grupos en estadísticos (cola ligera: desviación y p99 de El Tigre normal,
# Puerto Pizarro normal y Chulucanas normal) y 13 en KS (forma del cuerpo, D = 0,10-0,20); el detalle
# está en results/validacion/diagnostico_v6.log y en docs/validacion-v6.md.
FALLOS_CONOCIDOS_ESTADISTICOS: dict = {}
FALLOS_CONOCIDOS_KS: dict = {}


def grupos_calibrados(conocidos=None):
    if not (PARAMETROS.exists() and REGIMENES.exists() and any(DATOS_RAW.glob("*.csv"))):
        return [pytest.param(None, None, None, marks=pytest.mark.skip(reason="faltan los datos SENAMHI de T06–T10"))]
    conocidos = conocidos or {}
    with PARAMETROS.open(newline="", encoding="utf-8") as f:
        filas = list(csv.DictReader(f))
    return [pytest.param(fila["estacion"], fila["regimen"],
                         {**{k: float(fila[k]) for k in ("p01", "p11", "alfa", "theta")},
                          "kappa": float(fila.get("kappa") or "inf")},
                         id=f"{fila['estacion']}-{fila['regimen']}",
                         marks=[pytest.mark.xfail(strict=True, reason=conocidos[(fila["estacion"], fila["regimen"])])]
                         if (fila["estacion"], fila["regimen"]) in conocidos else [])
            for fila in filas]


# Criterio estadístico (docs/validacion-v6.md §«Criterio estadístico»).
ESTADISTICOS_V6 = ("frecuencia_lluvia", "media_monto", "desviacion_monto", "p95_monto", "p99_monto",
                   "racha_media", "max_diario_temporada_medio")
ALFA_GRUPO = 0.05                                  # error de tipo I por grupo estación × régimen
ALFA_CONTRASTE = ALFA_GRUPO / (len(ESTADISTICOS_V6) + 1)   # Bonferroni sobre 7 estadísticos + KS
B_IC = int(os.environ.get("PP_V6_B_IC", "5000"))   # remuestreos de temporadas para el IC
B_KS = int(os.environ.get("PP_V6_B_KS", "999"))    # réplicas del bootstrap paramétrico de KS
RESOLUCION = 0.1                                    # mm: resolución de las series SENAMHI


def temporadas_observadas(estacion, regimen, umbral, meses):
    """Registros por temporada (año) en los años de regimenes.csv con ese régimen. Un día faltante o un
    salto de fechas corta la racha abierta sin contarla, igual que el auxiliar solo cuenta rachas
    cerradas. Cada temporada guarda lo necesario para recomponer los 7 estadísticos al remuestrear."""
    with REGIMENES.open(newline="", encoding="utf-8") as f:
        anios = {int(r["anio"]) for r in csv.DictReader(f) if r["estacion"] == estacion and r["regimen"] == regimen}
    t = {a: {"dias": 0, "montos": [], "rachas": 0, "dias_en_rachas": 0, "maximo": 0.0} for a in anios}
    racha, previa = 0, None
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
            s = t[fecha.year]
            s["dias"] += 1
            s["maximo"] = max(s["maximo"], v)
            if (v >= umbral) if umbral > 0 else (v > 0):
                s["montos"].append(v)
                racha += 1
            elif racha:
                s["rachas"] += 1
                s["dias_en_rachas"] += racha
                racha = 0
    return [t[a] for a in sorted(t) if t[a]["dias"] > 0]


def agregar(temporadas):
    """Los 7 estadísticos de V6 sobre un conjunto de temporadas (con repetición si es un remuestreo)."""
    montos = np.concatenate([np.asarray(s["montos"], float) for s in temporadas])
    dias = sum(s["dias"] for s in temporadas)
    rachas = sum(s["rachas"] for s in temporadas)
    if len(montos) < 2 or rachas == 0:
        return None
    return {
        "frecuencia_lluvia": len(montos) / dias,
        "media_monto": float(montos.mean()),
        "desviacion_monto": float(montos.std(ddof=1)),
        "p95_monto": float(np.percentile(montos, 95)),
        "p99_monto": float(np.percentile(montos, 99)),
        "racha_media": sum(s["dias_en_rachas"] for s in temporadas) / rachas,
        "max_diario_temporada_medio": float(np.mean([s["maximo"] for s in temporadas])),
    }


def estadisticos_observados(estacion, regimen, umbral, meses):
    temporadas = temporadas_observadas(estacion, regimen, umbral, meses)
    montos = [v for s in temporadas for v in s["montos"]]
    return agregar(temporadas), montos, len(temporadas)


def ic_bootstrap(temporadas, alfa, b=B_IC, semilla=SEMILLA):
    """IC (1 - alfa) por percentiles, remuestreando temporadas completas: conserva la dependencia
    entre los días de un mismo año, que es donde está la variabilidad de la cola (1983, 1998)."""
    rng = np.random.default_rng(semilla)
    muestras = defaultdict(list)
    for _ in range(b):
        e = agregar([temporadas[i] for i in rng.integers(0, len(temporadas), len(temporadas))])
        if e is not None:
            for k, v in e.items():
                muestras[k].append(v)
    return {k: (float(np.quantile(v, alfa / 2)), float(np.quantile(v, 1 - alfa / 2))) for k, v in muestras.items()}


def registrar(montos):
    """Montos tal como los anota un pluviómetro de 0,1 mm: redondeo y día lluvioso solo si >= 0,1 mm."""
    r = np.round(np.asarray(montos, float) / RESOLUCION) * RESOLUCION
    return r[r >= UMBRAL_LLUVIA - 1e-9]


def montos_modelo(params, dias, temporadas, rng):
    """Montos de 'temporadas' temporadas del modelo Markov + gamma con el día previo seco, como
    simular_escenario; con kappa finito (H5) los montos de cada temporada se multiplican por
    M ~ Gamma(kappa, 1/kappa). La parte 1 de V6 comprueba que pp_v6_generador produce este modelo.
    Con kappa infinito consume los mismos números aleatorios que antes de H5."""
    estado = np.zeros(temporadas, bool)
    lluviosos = np.zeros(temporadas, int)
    for _ in range(dias):
        estado = rng.random(temporadas) < np.where(estado, params["p11"], params["p01"])
        lluviosos += estado
    montos = rng.gamma(params["alfa"], params["theta"], int(lluviosos.sum()))
    kappa = params.get("kappa", math.inf)
    if math.isfinite(kappa):
        montos *= np.repeat(rng.gamma(kappa, 1.0 / kappa, temporadas), lluviosos)
    return montos


def ks_bootstrap(montos_obs, muestra_sim, params, dias, temporadas, b=B_KS, semilla=SEMILLA):
    """KS de dos muestras entre lo observado y lo simulado, ambos registrados a 0,1 mm. Con datos
    discretizados (empates) el valor p asintótico no vale, así que la distribución nula se obtiene
    simulando b conjuntos de 'temporadas' temporadas del propio modelo, registrados igual."""
    ref = registrar(muestra_sim)
    d_obs = stats.ks_2samp(registrar(montos_obs), ref).statistic
    rng = np.random.default_rng(semilla)
    mayores = 0
    for _ in range(b):
        nulo = registrar(montos_modelo(params, dias, temporadas, rng))
        if len(nulo) == 0 or stats.ks_2samp(nulo, ref).statistic >= d_obs:
            mayores += 1
    return d_obs, (mayores + 1) / (b + 1)


_EVALUADOS = {}


def evaluar_frente_a_observado(estacion, regimen, params):
    """Evalúa un grupo una sola vez (las dos pruebas comparten el resultado). Devuelve un dict con
    las filas de cada contraste y los fallos de los estadísticos y de KS por separado."""
    if (estacion, regimen) in _EVALUADOS:
        return _EVALUADOS[(estacion, regimen)]
    meses, dias = temporada_de(estacion)
    temporadas = temporadas_observadas(estacion, regimen, UMBRAL_LLUVIA, meses)
    obs = agregar(temporadas)
    montos_obs = [v for s in temporadas for v in s["montos"]]
    sim = correr_generador(dict(params, dias=dias), n=N_OBS)
    muestra = [float(x) for x in sim["muestra"].split(";") if x]
    ic = ic_bootstrap(temporadas, ALFA_CONTRASTE)
    filas, fallos_est = [], []
    for clave in ESTADISTICOS_V6:
        valor_obs, valor_sim = obs[clave], float(sim[clave])
        error = (valor_sim - valor_obs) / abs(valor_obs)
        lo, hi = ic[clave]
        pasa = abs(error) <= TOLERANCIA or lo <= valor_sim <= hi
        filas.append((clave, valor_obs, valor_sim, error, lo, hi, pasa))
        if not pasa:
            fallos_est.append(f"{clave} {error:+.0%} fuera de [{lo:.4g}, {hi:.4g}]")
    d, p = ks_bootstrap(montos_obs, muestra, params, dias, len(temporadas))
    filas.append(("ks_registrado_0_1mm", d, p, None, None, None, p >= ALFA_CONTRASTE))
    fallos_ks = [] if p >= ALFA_CONTRASTE else [f"KS D={d:.3f} p={p:.3g} < {ALFA_CONTRASTE:.4g}"]
    r = {"meses": meses, "dias": dias, "temporadas": len(temporadas), "lluviosos": len(montos_obs),
         "filas": filas, "fallos_est": fallos_est, "fallos_ks": fallos_ks}
    _EVALUADOS[(estacion, regimen)] = r
    print(f"\n[V6-obs] {estacion}/{regimen} meses={meses} temporadas={r['temporadas']} "
          f"dias_lluviosos_obs={r['lluviosos']} umbral={UMBRAL_LLUVIA} mm N_sim={N_OBS}x{dias} d "
          f"alfa_contraste={ALFA_CONTRASTE:.4%} params={params}")
    print(f"[V6-obs] {'estadistico':28s} {'observado':>11s} {'simulado':>11s} {'error':>8s} "
          f"{'IC bootstrap':>23s}  pasa")
    for clave, a, b, error, lo, hi, pasa in filas:
        if error is None:
            print(f"[V6-obs] {clave:28s} D={a:9.4f} p={b:9.4f} {'':32s}  {'si' if pasa else 'NO'}")
        else:
            print(f"[V6-obs] {clave:28s} {a:11.4f} {b:11.4f} {error:+8.1%} [{lo:10.4f},{hi:10.4f}]  "
                  f"{'si' if pasa else 'NO'}")
    return r


@pytest.mark.parametrize("estacion,regimen,params", grupos_calibrados(FALLOS_CONOCIDOS_ESTADISTICOS))
def test_v6_estadisticos_frente_a_observado(estacion, regimen, params):
    """Los 7 estadísticos: error <= 10 % o dentro del IC bootstrap por temporadas (Bonferroni)."""
    r = evaluar_frente_a_observado(estacion, regimen, params)
    assert not r["fallos_est"], f"{estacion}/{regimen}: " + "; ".join(r["fallos_est"])


@pytest.mark.parametrize("estacion,regimen,params", grupos_calibrados(FALLOS_CONOCIDOS_KS))
def test_v6_ks_frente_a_observado(estacion, regimen, params):
    """KS de los montos registrados a 0,1 mm, con valor p por bootstrap paramétrico (Bonferroni)."""
    r = evaluar_frente_a_observado(estacion, regimen, params)
    assert not r["fallos_ks"], f"{estacion}/{regimen}: " + "; ".join(r["fallos_ks"])
