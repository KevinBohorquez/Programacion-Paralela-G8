# Sala de control | Pruebas de las partes puras del servidor (scripts/demo/sala_control.py y scripts/demo/sala/).
"""Pruebas del servidor de la sala de control sin ejecutar los binarios reales.

Cubre: el analizador de líneas `[prog]` (los 3 formatos), el evento `fin` desde una fila CSV real y
sus líneas `[verif]`, la diferencia entre muestras de /proc/stat, Wilson, la curva P(Amax > u) desde
hist512, el programa de tiempos del replay, la respuesta 409 con una corrida en curso y una corrida
completa con un binario falso (avance real y estimado).

Uso:   python3 -m pytest -q tests/unit/test_sala_control.py
"""
import hashlib
import json
import os
import stat
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "scripts" / "demo"))

import sala_control  # noqa: E402
from sala import cpu, grabacion, lanzador, riesgo  # noqa: E402
from sala.eventos import Difusor  # noqa: E402

# Corrida real: mpirun -np 4 pp_mpi_estatico --config config/sintetico.yaml --n 10007 (hist512 sin la cola de ceros).
HIST_PREFIJO = ("1;1;6;12;12;24;37;50;67;79;115;158;149;181;229;240;266;294;297;329;325;300;326;322;313;292;310;"
                "314;329;284;269;280;259;230;216;203;200;188;182;157;156;146;127;116;119;90;100;88;80;79;67;66;61;"
                "71;64;55;69;52;42;34;31;26;28;27;21;26;29;16;23;16;18;14;10;9;12;12;9;14;9;10;13;7;9;6;13;5;6;4;"
                "4;1;2;3;4;4;3;4;2;1;3;2;1;0;0;4;1;1;1;1;3;0;0;1;0;2;0;2;2;0;0;0;0;1;0;1;1;0;0;0;0;0;0;0;1")
HIST = [int(x) for x in HIST_PREFIJO.split(";")] + [0] * (512 - len(HIST_PREFIJO.split(";")))
HIST_CSV = ";".join(map(str, HIST))
CABECERA = ("backend,estacion,regimen,config_id,semilla,n,k,p_hat,wilson_inf,wilson_sup,dias,capacidad,umbral,p01,"
            "p11,alfa,theta,hilos,procesos,repeticion,calentamiento,schedule,afinidad,tiempo_s,commit,cpu,"
            "nucleos_fisicos,nucleos_logicos,hist512,hardware,nodos,distribucion,bloques,hilos_por_bloque")
FILA = ("mpi_estatico,sintetica,normal,0,20261015,10007,1060,0.10592585190366743,0.10004679458283591,"
        "0.11210734526215657,120,6,50,0.14999999999999999,0.59999999999999998,0.69999999999999996,9,1,4,1,0,,"
        "OMP_PROC_BIND=no_definida;OMP_PLACES=no_definida,0.0073624780000000004,desconocido,"
        f"Intel(R) Core(TM) Ultra 9 275HX,24,24,{HIST_CSV},host=95e37b31710d;ram_gb=31.1,1,95e37b31710d:4,,")
VERIF = """[verif] backend=mpi_estatico procesos=4 n_solicitado=10007 nivel_hilos_mpi=MPI_THREAD_FUNNELED nucleo=pp_core
[verif] rango=0 inicio=0 fin=2502 n_local=2502
[verif] rango=1 inicio=2502 fin=5004 n_local=2502
[verif] rango=2 inicio=5004 fin=7506 n_local=2502
[verif] rango=3 inicio=7506 fin=10007 n_local=2501
[verif] suma_n=10007 suma_n_rangos=10007 suma_hist=10007 k=1060 estado=OK
[verif] tiempo_s=0.00736248""".splitlines()


def fila_dict():
    return dict(zip(CABECERA.split(","), FILA.split(",")))


def test_muestra_coherente():
    assert sum(HIST) == 10007 and len(HIST) == 512
    assert sum(HIST[50:]) == 1060  # k = #(Amax > 50) leído del histograma


# --- [prog] ---
@pytest.mark.parametrize("linea, esperado", [
    ("[prog] hecho=200000 total=20000000",
     {"tipo": "avance", "rango": None, "hecho": 200000, "total": 20000000}),
    ("[prog] rango=3 hecho=50 total=2501\n",
     {"tipo": "avance", "rango": 3, "hecho": 50, "total": 2501}),
    ("[prog] rango=2 bloque=62500,125000",
     {"tipo": "bloque", "rango": 2, "i0": 62500, "i1": 125000}),
])
def test_parsear_prog(linea, esperado):
    assert lanzador.parsear_prog(linea) == esperado


@pytest.mark.parametrize("linea", ["[verif] rango=0 inicio=0 fin=2 n_local=2", "[prog] hecho=x total=3",
                                   "n=20000 k=2127", "[prog] rango=1 bloque=5"])
def test_parsear_prog_ignora_otras(linea):
    assert lanzador.parsear_prog(linea) is None


# --- fin ---
def test_construir_fin_desde_csv_y_verif():
    fin = lanzador.construir_fin("c1-mpi_estatico", fila_dict(), VERIF, speedup=3.5)
    assert fin["t"] == "fin" and fin["id"] == "c1-mpi_estatico"
    assert (fin["k"], fin["n"]) == (1060, 10007)
    assert fin["p"] == pytest.approx(1060 / 10007)
    assert fin["wilson"] == pytest.approx([0.10004679458283591, 0.11210734526215657])
    assert fin["segundos"] == pytest.approx(0.007362478)
    assert fin["trabajo_rangos"] == [2502, 2502, 2502, 2501]
    assert fin["speedup"] == 3.5
    assert fin["huella"] == hashlib.sha256(HIST_CSV.encode()).hexdigest()[:12]
    assert len(fin["huella"]) == 12 and int(fin["huella"], 16) >= 0


def test_fin_sin_rangos_es_null():
    fila = fila_dict() | {"backend": "openmp"}
    assert lanzador.construir_fin("c1-openmp", fila, [])["trabajo_rangos"] is None


def test_trabajo_rangos_dinamico_e_hibrido():
    lineas = ["[verif] rango=0 bloques=10 n_local=0", "[verif] rango=1 bloques=6 n_local=375000",
              "[verif] rango=1 inicio=0 fin=5004 hilos=4 n_local=5004"]
    assert lanzador.trabajo_rangos(lineas[:2]) == [0, 375000]
    assert lanzador.trabajo_rangos(lineas[2:]) == [5004]


def test_huella_igual_entre_backends():
    otra = list(HIST)
    assert riesgo.huella(otra) == riesgo.huella(HIST)
    otra[0] += 1
    assert riesgo.huella(otra) != riesgo.huella(HIST)


# --- /proc/stat ---
STAT_0 = """cpu  300 0 300 1400 0 0 0 0 0 0
cpu0 100 0 100 800 0 0 0 0 0 0
cpu1 200 0 200 600 0 0 0 0 0 0
intr 12345
"""
STAT_1 = """cpu  500 0 500 1600 0 0 0 0 0 0
cpu0 175 0 25 800 0 0 0 0 0 0
cpu1 200 0 200 700 100 0 0 0 0 0
intr 12399
"""


def test_proc_stat_lee_por_cpu():
    assert cpu.leer_proc_stat(STAT_0) == [(1000, 800), (1000, 600)]


def test_proc_stat_diferencias():
    m0, m1 = cpu.leer_proc_stat(STAT_0), cpu.leer_proc_stat(STAT_1)
    # cpu0: +75 user, -75 system → total sin cambio → 0; cpu1: +100 idle, +100 iowait → todo inactivo → 0
    assert cpu.utilizacion(m0, m1) == [0.0, 0.0]
    m2 = [(1100, 825), (1200, 650)]  # cpu0: 100 de total, 25 inactivo → 0,75; cpu1: 200, 50 → 0,75
    assert cpu.utilizacion(cpu.leer_proc_stat(STAT_0), m2) == [0.75, 0.75]


def test_proc_stat_ignora_guest():
    texto = "cpu0 10 0 0 10 0 0 0 0 99 99\n"
    assert cpu.leer_proc_stat(texto) == [(20, 10)]


# --- Wilson ---
def test_wilson_coincide_con_el_csv():
    lo, hi = riesgo.wilson(1060, 10007)
    assert lo == pytest.approx(0.10004679458283591, rel=1e-12)
    assert hi == pytest.approx(0.11210734526215657, rel=1e-12)


def test_wilson_bordes():
    assert riesgo.wilson(0, 0) == (0.0, 1.0)
    lo, hi = riesgo.wilson(0, 100)
    assert lo == 0.0 and 0 < hi < 0.05
    lo, hi = riesgo.wilson(100, 100)
    assert hi == 1.0 and lo > 0.95


# --- curva P(Amax > u) ---
def test_curva_desde_hist512():
    c = riesgo.curva_riesgo(HIST)
    assert c["n"] == 10007 and c["u"][0] == 1
    assert c["p"][c["u"].index(50)] == pytest.approx(1060 / 10007)  # en U coincide con k / n
    assert c["p"][0] == pytest.approx((10007 - HIST[0]) / 10007)
    assert all(a >= b for a, b in zip(c["p"], c["p"][1:]))  # no creciente
    assert c["p"][-1] == 0.0 and c["u"][-1] == 133  # termina en el primer cero
    assert all(lo <= p <= hi for p, lo, hi in zip(c["p"], c["lo"], c["hi"]))


def test_curva_cola_en_511():
    hist = [0] * 512
    hist[511] = 4
    c = riesgo.curva_riesgo(hist)
    assert len(c["u"]) == 511 and c["p"][-1] == 1.0


# --- YAML ---
def test_configs_desde_yaml():
    cs = {c["id"]: c for c in riesgo.listar_configs(RAIZ / "config")}
    assert cs["piura_miraflores_el_nino"] == {"id": "piura_miraflores_el_nino", "estacion": "piura_miraflores",
                                              "regimen": "el_nino", "c": 6.0, "u": 50.0}


# --- replay ---
def test_programa_replay_respeta_tiempos():
    eventos = [{"t": "cpu", "ts": 10.0}, {"t": "inicio", "ts": 10.5}, {"t": "fin", "ts": 12.0}]
    assert [r for r, _ in grabacion.programa_replay(eventos)] == [0.0, 0.5, 2.0]
    assert [r for r, _ in grabacion.programa_replay(eventos, velocidad=2.0)] == [0.0, 0.25, 1.0]
    assert grabacion.programa_replay([]) == []
    with pytest.raises(ValueError):
        grabacion.programa_replay(eventos, velocidad=0)


def test_programa_replay_no_retrocede():
    eventos = [{"ts": 5.0}, {"ts": 4.0}, {"ts": 6.0}]
    assert [r for r, _ in grabacion.programa_replay(eventos)] == [0.0, 0.0, 1.0]


def test_reproducir_reescribe_ts():
    salida = []
    programa = grabacion.programa_replay([{"t": "cpu", "ts": 1.0}, {"t": "fin", "ts": 1.02}])
    assert grabacion.reproducir(programa, salida.append, threading.Event(), time.monotonic)
    assert [e["ts_original"] for e in salida] == [1.0, 1.02]
    assert all("ts" not in e and e["replay"] for e in salida)


def test_grabar_y_cargar(tmp_path):
    d = Difusor()
    g = grabacion.Grabadora(tmp_path)
    d.agregar_oyente(g)
    g.iniciar("ensayo")
    d.emitir({"t": "cpu", "nucleos": [0.5]})
    d.emitir({"t": "estado", "modo": "vivo"})  # el estado no se graba
    g.detener()
    d.emitir({"t": "cpu", "nucleos": [0.1]})
    eventos = grabacion.cargar(tmp_path, "ensayo")
    assert [e["t"] for e in eventos] == ["cpu"] and "ts" in eventos[0]
    assert grabacion.listar(tmp_path)[0]["nombre"] == "ensayo"
    with pytest.raises(ValueError):
        grabacion.validar_nombre("../fuera")


def test_difusor_cola_por_cliente():
    d = Difusor()
    a, b = d.suscribir(), d.suscribir()
    d.emitir({"t": "cpu"})
    assert a.get_nowait()["t"] == "cpu" and b.get_nowait()["t"] == "cpu"
    d.desuscribir(a)
    d.emitir({"t": "fin"})
    assert a.empty() and b.get_nowait()["t"] == "fin"


# --- comandos y afinidad ---
def test_comando_hibrido_afinidad():
    esp = lanzador.Especificacion("h1-close", "hibrido", 1000, "sintetico", 4, 6, "close")
    argv, env = lanzador.construir_comando(esp, Path("/b"), Path("/c"), Path("/o.csv"), progreso=True)
    assert argv[argv.index("--bind-to") + 1] == "none" and env["OMP_PROC_BIND"] == "close"
    assert "--progreso" in argv and argv[argv.index("--hilos") + 1] == "6"
    esp.afinidad = "false"
    argv, env = lanzador.construir_comando(esp, Path("/b"), Path("/c"), Path("/o.csv"), progreso=False)
    assert env["OMP_PROC_BIND"] == "false" and "--progreso" not in argv


def test_comando_mpi_y_openmp():
    esp = lanzador.Especificacion("c1-mpi_dinamico", "mpi_dinamico", 1000, procesos=24)
    argv, _ = lanzador.construir_comando(esp, Path("/b"), Path("/c"), Path("/o.csv"), progreso=True)
    assert argv[argv.index("--bind-to") + 1] == "core" and argv[argv.index("-np") + 1] == "24"
    esp = lanzador.Especificacion("c1-openmp", "openmp", 1000, hilos=24)
    _, env = lanzador.construir_comando(esp, Path("/b"), Path("/c"), Path("/o.csv"), progreso=True)
    assert env == {"OMP_PROC_BIND": "close", "OMP_PLACES": "cores"}


def test_reparto_hibrido():
    assert sala_control.reparto_hibrido(24) == (4, 6)
    assert sala_control.reparto_hibrido(6) == (3, 2)
    assert sala_control.reparto_hibrido(7) == (1, 7)


# --- 409 ---
@pytest.fixture
def servidor(tmp_path):
    sala = sala_control.Sala(tmp_path / "bin", dir_grabaciones=tmp_path / "grab")
    srv = sala_control.crear_servidor(sala, "127.0.0.1", 0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield sala, f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()
    srv.server_close()


def post(url, cuerpo):
    req = urllib.request.Request(url, json.dumps(cuerpo).encode(), {"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_409_si_esta_ocupado(servidor):
    sala, url = servidor
    sala.ocupar()
    for ruta, cuerpo in (("/api/carrera", {"backends": ["serial"], "n": 1000}),
                         ("/api/hibrido", {"afinidad": "false", "n": 1000})):
        codigo, j = post(url + ruta, cuerpo)
        assert codigo == 409 and "error" in j
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(url + "/api/riesgo?config=sintetico&n=1000", timeout=5)
    assert e.value.code == 409
    sala.liberar()


def test_sala_ocupar_dos_veces():
    sala = sala_control.Sala(Path("/no/existe"))
    sala.ocupar()
    with pytest.raises(sala_control.Ocupado):
        sala.ocupar()
    sala.liberar()
    sala.ocupar()


def test_http_configs_y_placeholder(servidor):
    _, url = servidor
    with urllib.request.urlopen(url + "/api/configs", timeout=5) as r:
        assert any(c["id"] == "sintetico" for c in json.loads(r.read()))
    with urllib.request.urlopen(url + "/", timeout=5) as r:
        assert b"<html" in r.read()
    codigo, j = post(url + "/api/carrera", {"backends": ["cuda"]})
    assert codigo == 400


# --- --interfaz moderna|clasica ---
def test_interfaz_por_defecto_es_moderna():
    assert sala_control.analizar_argumentos([]).interfaz == "moderna"
    assert sala_control.analizar_argumentos(["--interfaz", "clasica"]).interfaz == "clasica"
    assert sala_control.INTERFACES["moderna"] == sala_control.ESTATICOS
    assert (sala_control.INTERFACES["clasica"] / "index.html").is_file()
    with pytest.raises(SystemExit):
        sala_control.analizar_argumentos(["--interfaz", "otra"])


@pytest.fixture
def servidor_con(tmp_path):
    servidores = []

    def arrancar(estaticos):
        sala = sala_control.Sala(tmp_path / "bin", dir_grabaciones=tmp_path / "grab")
        srv = sala_control.crear_servidor(sala, "127.0.0.1", 0, estaticos)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        servidores.append(srv)
        return f"http://127.0.0.1:{srv.server_address[1]}"

    yield arrancar
    for srv in servidores:
        srv.shutdown()
        srv.server_close()


def leer(url):
    with urllib.request.urlopen(url, timeout=5) as r:
        return r.status, r.headers.get("Content-Type", ""), r.read()


def test_interfaz_clasica_sirve_su_carpeta(servidor_con):
    url = servidor_con(sala_control.INTERFACES["clasica"])
    _, tipo, cuerpo = leer(url + "/")
    assert tipo.startswith("text/html") and b"sala.js" in cuerpo
    codigo, tipo, _ = leer(url + "/static/sala.css")
    assert codigo == 200 and tipo.startswith("text/css")


def test_interfaz_moderna_sirve_assets_bajo_static(servidor_con, tmp_path):
    web = tmp_path / "moderna"
    (web / "assets").mkdir(parents=True)
    (web / "index.html").write_text('<!doctype html><html><script src="/static/assets/app.js"></script></html>')
    (web / "assets" / "app.js").write_text("console.log(1)")
    (web / "assets" / "inter.woff2").write_bytes(b"wOF2")
    url = servidor_con(web)
    assert b"/static/assets/app.js" in leer(url + "/")[2]
    codigo, tipo, cuerpo = leer(url + "/static/assets/app.js")
    assert codigo == 200 and "javascript" in tipo and cuerpo == b"console.log(1)"
    assert leer(url + "/static/assets/inter.woff2")[1] == "font/woff2"
    with pytest.raises(urllib.error.HTTPError) as e:
        urllib.request.urlopen(url + "/static/../../secreto", timeout=5)
    assert e.value.code == 404


# --- corrida completa con un binario falso ---
FALSO = """#!/usr/bin/env python3
import sys, time
a = sys.argv
salida = a[a.index("--salida") + 1]
for h in (0, 5003, 10007):
    if "--progreso" in a:
        print(f"[prog] hecho={h} total=10007", file=sys.stderr, flush=True)
    time.sleep(0.15)
open(salida, "w").write(open(salida + ".src").read())
"""


@pytest.mark.skipif(not hasattr(os, "killpg"), reason="requiere POSIX")
@pytest.mark.parametrize("progreso", [True, False])
def test_lanzador_con_binario_falso(tmp_path, progreso):
    exe = tmp_path / "bin" / "serial" / "pp_serial"
    exe.parent.mkdir(parents=True)
    exe.write_text(FALSO)
    exe.chmod(exe.stat().st_mode | stat.S_IEXEC)
    eventos = []
    lz = lanzador.Lanzador(tmp_path / "bin", RAIZ / "config", eventos.append, progreso=progreso,
                           periodo_estimado=0.05)
    orig = lanzador.construir_comando

    def con_fuente(esp, dir_bin, dir_config, salida, prog):
        Path(str(salida) + ".src").write_text(CABECERA + "\n" + FILA.replace("mpi_estatico", "serial", 1) + "\n")
        return orig(esp, dir_bin, dir_config, salida, prog)

    lanzador.construir_comando = con_fuente
    try:
        fin = lz.ejecutar(lanzador.Especificacion("c1-serial", "serial", 10007), lambda s: 1.0)
    finally:
        lanzador.construir_comando = orig
    tipos = [e["t"] for e in eventos]
    assert tipos[0] == "inicio" and tipos[-1] == "fin" and fin["k"] == 1060 and fin["speedup"] == 1.0
    avances = [e for e in eventos if e["t"] == "avance"]
    assert avances and avances[-1]["hecho"] == 10007
    if progreso:
        assert [a["hecho"] for a in avances] == [0, 5003, 10007] and not any(a.get("estimado") for a in avances)
    else:
        assert all(a["estimado"] for a in avances) and len(avances) >= 3
