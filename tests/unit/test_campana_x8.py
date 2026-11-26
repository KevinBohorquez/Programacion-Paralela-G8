"""T56: contrato del medidor X8 sin inventar mediciones de hardware."""
import csv
import importlib
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/bench"))
x8 = importlib.import_module("_campana_x8")


@pytest.fixture
def args(tmp_path):
    hostfile = tmp_path / "hosts"
    hostfile.write_text("pc1 slots=2\npc2 slots=2\n", encoding="utf-8")
    return x8.parser().parse_args(["--experimento", "x8", "--hostfile", str(hostfile),
                                  "--procesos", "3", "--cargas", "1e7,1e8"])


def salida(cluster=True, gpu=True):
    out = ("[verif] rango=0 bloques=4 n_local=0\n"
           "[verif] rango=1 bloques=1 n_local=3\n"
           "[verif] rango=2 bloques=3 n_local=7\n"
           "[verif] suma_n=10 estado=OK\n")
    err = ("[x8-host] rango=0 host=pc1\n[x8-host] rango=1 host=pc1\n"
           f"[x8-host] rango=2 host={'pc2' if cluster else 'pc1'}\n")
    if gpu:
        err += "[gpu] rango=2 dispositivo=0\n"
    return out, err


def test_plan_compara_las_tres_variantes_en_dos_ambitos(args):
    plan = x8.plan(args)
    assert len(plan) == 12
    assert len(set(plan)) == 12
    assert {v for _, _, v in plan} == set(x8.VARIANTES)
    assert {a for _, a, _ in plan} == {"local", "cluster"}


def test_comandos_no_confunden_ext2_con_tres_niveles(args):
    cpu = x8.comando(args, 100, "cluster", "mpi_openmp")
    gpu = x8.comando(args, 100, "local", "mpi_openmp_gpu")
    mpi = x8.comando(args, 100, "cluster", "mpi")
    assert "--hostfile" in cpu and "--hostfile" not in gpu
    assert "localhost:3" in gpu and "none" in cpu
    assert any("pp_mpi_omp_cuda" in c for c in gpu)
    assert any("pp_mpi_dinamico" in c for c in mpi)
    assert not any("pp_mpi_dinamico_gpu" in c for c in gpu)
    assert "--hilos" not in mpi and "--hilos" in cpu
    assert "python3" in cpu and any("_lanzador_x8.py" in c for c in cpu)


@pytest.mark.parametrize("campo,valor", [("procesos", 2), ("hilos", 0), ("lote", 0),
                                         ("repeticiones", 0), ("cargas", "0"), ("cargas", "1e7,1e7")])
def test_parametros_invalidos(args, campo, valor):
    setattr(args, campo, valor)
    with pytest.raises(ValueError):
        x8.plan(args)


def test_no_suma_bloques_del_maestro():
    out, err = salida()
    r = x8.verificar_rangos(out, err, 10, 3, "cluster", "mpi_openmp_gpu", 3)
    assert sum(x["bloques"] for x in r if x["tipo"] != "maestro") == 4
    assert r[2]["host"] == "pc2" and r[2]["tipo"] == "gpu"


@pytest.mark.parametrize("cambio", ["estado", "rango", "host", "suma", "bloques", "gpu"])
def test_rechaza_evidencia_incompleta_o_falsa(cambio):
    out, err = salida()
    if cambio == "estado":
        out = out.replace("estado=OK", "")
    elif cambio == "rango":
        out = out.replace("[verif] rango=1 bloques=1 n_local=3\n", "")
    elif cambio == "host":
        err = err.replace("[x8-host] rango=2 host=pc2\n", "")
    elif cambio == "suma":
        out = out.replace("n_local=7", "n_local=6")
    elif cambio == "bloques":
        out = out.replace("bloques=3", "bloques=2")
    elif cambio == "gpu":
        err = err.replace("[gpu] rango=2 dispositivo=0\n", "")
    with pytest.raises(ValueError):
        x8.verificar_rangos(out, err, 10, 3, "cluster", "mpi_openmp_gpu", 3)


def test_cluster_no_se_simula_en_una_pc():
    out, err = salida(cluster=False)
    with pytest.raises(ValueError, match="número de PC"):
        x8.verificar_rangos(out, err, 10, 3, "cluster", "mpi_openmp_gpu", 3)


def test_cpu_no_acepta_gpu_activa():
    out, err = salida()
    with pytest.raises(ValueError, match="variante CPU"):
        x8.verificar_rangos(out, err, 10, 3, "cluster", "mpi_openmp", 3)


def test_firma_exige_n_k_histograma_y_tiempo():
    fila = dict(n="10", k="2", hist512=";".join(map(str, [8, 2] + [0] * 510)), tiempo_s=".1")
    assert x8.firma(fila, 10)[0] == 2
    with pytest.raises(ValueError):
        x8.firma({**fila, "tiempo_s": "nan"}, 10)
    with pytest.raises(ValueError):
        x8.firma({**fila, "n": "11"}, 10)


def test_hardware_compara_binarios_y_configuracion_por_rango(tmp_path):
    exe, config = tmp_path / "exe", tmp_path / "config"
    exe.write_bytes(b"binario")
    config.write_bytes(b"config")
    from _lanzador_x8 import sha256
    d = dict(rango=0, host="pc1", cpu="CPU", nucleos_fisicos=8, ram_gb=16,
             binario_sha256=sha256(exe), config_sha256=sha256(config))
    err = "[x8-hardware] " + json.dumps(d)
    assert x8.verificar_hardware(err, [{"rango": 0, "host": "pc1"}], exe, config)[0]["cpu"] == "CPU"
    config.write_bytes(b"distinta")
    with pytest.raises(ValueError, match="distintos"):
        x8.verificar_hardware(err, [{"rango": 0, "host": "pc1"}], exe, config)


def test_dry_run_no_necesita_gpu_ni_crea_resultados(args, tmp_path, capsys):
    salida = tmp_path / "x8.csv"
    assert x8.main(["--experimento", "x8", "--hostfile", str(args.hostfile),
                    "--salida", str(salida), "--dry-run"]) == 0
    assert "24 puntos" in capsys.readouterr().out
    assert not salida.exists()


def test_grafica_desde_fracciones_reales_del_csv(tmp_path):
    ruta = tmp_path / "rangos.csv"
    filas = [dict(n=10, ambito="cluster", variante="mpi", rango=r, host=f"pc{r}", tipo="cpu",
                  calentamiento=0, repeticion=1, fraccion_bloques=fraccion) for r, fraccion in ((1, .25), (2, .75))]
    x8.escribir(ruta, filas)
    x8.graficar(ruta, tmp_path / "figuras")
    assert (tmp_path / "figuras/x8_fraccion_bloques.svg").is_file()
    assert (tmp_path / "figuras/x8_fraccion_bloques.png").is_file()


@pytest.mark.parametrize("fallar", [False, True])
def test_campana_completa_o_error_quedan_diferenciados(tmp_path, monkeypatch, fallar):
    """Ejecutor doble de prueba: verifica el flujo, no produce evidencia científica."""
    from _lanzador_x8 import sha256
    cpu, gpu = tmp_path / "cpu", tmp_path / "gpu"
    for build in (cpu, gpu):
        build.mkdir()
        (build / "CMakeCache.txt").write_text("CMAKE_BUILD_TYPE:STRING=Release\n")
        for exe in ("mpi/pp_mpi_dinamico", "cuda/pp_mpi_omp_cuda", "serial/pp_serial"):
            ruta = build / "src/backends" / exe
            ruta.parent.mkdir(parents=True, exist_ok=True)
            ruta.write_bytes(b"doble-de-prueba")
    config, hosts = tmp_path / "config.yaml", tmp_path / "hosts"
    config.write_text("dias: 120\n")
    hosts.write_text("pc1 slots=2\npc2 slots=2\n")
    t1, salida_csv = tmp_path / "t1.csv", tmp_path / "x8.csv"
    x8.escribir(t1, [dict(commit="abc", tipo_build="Release", repeticiones=5, semilla=20261015,
                         config_id=0, cpu="CPU prueba", n=10000000, k=2, media=2,
                         **{f"t{i}": 2 for i in range(1, 6)})])
    monkeypatch.setattr(x8.cb, "commit_git", lambda: "abc")
    monkeypatch.setattr(x8.cb, "info_cpu", lambda: ("CPU prueba", 24, 24))
    monkeypatch.setattr(x8.cb, "info_gpu", lambda: "GPU prueba")
    llamadas = []

    def falso(cmd, env, log, timeout):
        llamadas.append(cmd)
        n = int(cmd[cmd.index("--n") + 1])
        hist = ";".join(map(str, [n - 2, 2] + [0] * 510))
        fila = dict(n=str(n), k="2", hist512=hist, tiempo_s="1.0", commit="abc")
        if cmd[0] != "mpirun":
            return fila, "", ""
        con_gpu = any(str(gpu) in c for c in cmd)
        if con_gpu and fallar:
            raise ValueError("GPU no disponible (fallo simulado de prueba)")
        cluster = "--hostfile" in cmd
        bloques = n // 62500
        out = (f"[verif] rango=0 bloques={bloques} n_local=0\n"
               "[verif] rango=1 bloques=1 n_local=62500\n"
               f"[verif] rango=2 bloques={bloques - 1} n_local={n - 62500}\n"
               "[verif] estado=OK\n")
        exe = cmd[cmd.index("python3") + 2]
        err = ""
        for r in range(3):
            host = "pc2" if cluster and r == 2 else "pc1"
            h = dict(rango=r, host=host, cpu="CPU prueba", nucleos_fisicos=24, ram_gb=16, gpu="GPU prueba",
                     binario_sha256=sha256(exe), config_sha256=sha256(config))
            err += f"[x8-host] rango={r} host={host}\n[x8-hardware] {json.dumps(h)}\n"
        if con_gpu:
            err += "[gpu] rango=2 dispositivo=0\n"
        return fila, out, err

    monkeypatch.setattr(x8, "correr", falso)
    argv = ["--experimento", "x8", "--build-dir", str(gpu), "--build-cpu-dir", str(cpu),
            "--config", str(config), "--hostfile", str(hosts), "--t1-csv", str(t1),
            "--procesos", "3", "--cargas", "1e7,1e8", "--host-en-reposo",
            "--salida", str(salida_csv), "--figuras", str(tmp_path / "figuras")]
    assert x8.main(argv) == int(fallar)
    estado = json.loads(salida_csv.with_suffix(".json").read_text())
    assert estado["estado"] == ("error" if fallar else "completada")
    with salida_csv.open(newline="", encoding="utf-8") as f:
        filas = list(csv.DictReader(f))
    assert len(filas) == (2 if fallar else 12)
    assert all(f["t_calentamiento"] == "1.0" for f in filas)
    if not fallar:
        assert len(llamadas) == 12 * 6 + 2
        assert all(f["speedup_t1"] == "" for f in filas if f["n"] == "100000000")
        assert all(f["speedup_t1"] == "2.0" for f in filas if f["n"] == "10000000")
