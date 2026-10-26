// T19,T20 | Responsable: David | Piezas comunes de los ejecutables MPI (contrato docs/contratos.md).
#include "mpi_comun.hpp"

#include <algorithm>
#include <cstdlib>
#include <exception>
#include <iostream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

#include "simulacion.hpp"

namespace mpi_pi {

namespace {
const char* nombre_nivel(int nivel) {
    switch (nivel) {
        case MPI_THREAD_SINGLE: return "MPI_THREAD_SINGLE";
        case MPI_THREAD_FUNNELED: return "MPI_THREAD_FUNNELED";
        case MPI_THREAD_SERIALIZED: return "MPI_THREAD_SERIALIZED";
        case MPI_THREAD_MULTIPLE: return "MPI_THREAD_MULTIPLE";
        default: return "desconocido";
    }
}

const char* entorno_o(const char* nombre, const char* defecto) {
    const char* e = std::getenv(nombre);
    return (e && *e) ? e : defecto;
}

// Nodos distintos y procesos por nodo ("host:p;host:p", en orden de primer rango). Colectiva: la
// llaman todos los rangos; el resultado solo es válido en el rango 0.
std::pair<int, std::string> distribucion_por_nodo(MPI_Comm comm, int rango, int procesos) {
    char nombre[MPI_MAX_PROCESSOR_NAME] = {};
    int largo = 0;
    MPI_Get_processor_name(nombre, &largo);
    std::vector<char> todos(rango == 0 ? static_cast<size_t>(procesos) * MPI_MAX_PROCESSOR_NAME : 0);
    MPI_Gather(nombre, MPI_MAX_PROCESSOR_NAME, MPI_CHAR, todos.data(), MPI_MAX_PROCESSOR_NAME, MPI_CHAR, 0, comm);
    if (rango != 0) return {0, ""};
    std::vector<std::pair<std::string, int>> cuenta;
    for (int r = 0; r < procesos; ++r) {
        const std::string host(&todos[static_cast<size_t>(r) * MPI_MAX_PROCESSOR_NAME]);
        auto it = std::find_if(cuenta.begin(), cuenta.end(), [&](const auto& c) { return c.first == host; });
        if (it == cuenta.end()) cuenta.emplace_back(host, 1);
        else ++it->second;
    }
    std::string s;
    for (const auto& [host, p] : cuenta) s += (s.empty() ? "" : ";") + host + ":" + std::to_string(p);
    return {static_cast<int>(cuenta.size()), s};
}
}  // namespace

FuncionEscenario escenario_del_modelo(const pp::Configuracion& cfg) {
    const pp::Parametros params = cfg.params;
    const std::uint64_t clave = pp::derivar_clave(cfg.semilla, cfg.config_id);
    const std::uint64_t base = cfg.config_id * cfg.n;  // índice global i = c*N + j
    return [=](std::uint64_t j, pp::Acumulador& acc) { acc.agregar(pp::simular_escenario(params, clave, base + j)); };
}

int ejecutar_mpi(int argc, char** argv, const char* backend, const Esquema& esquema) {
    int provisto = 0;
    if (MPI_Init_thread(&argc, &argv, MPI_THREAD_FUNNELED, &provisto) != MPI_SUCCESS) return 2;
    int rango = 0, procesos = 1;
    MPI_Comm_rank(MPI_COMM_WORLD, &rango);
    MPI_Comm_size(MPI_COMM_WORLD, &procesos);

    pp::Configuracion cfg;
    cfg.backend = backend;
    try {
        if (!pp::parsear_argumentos(argc, argv, cfg)) {  // --ayuda
            MPI_Finalize();
            return 0;
        }
    } catch (const std::exception& e) {
        if (rango == 0) std::cerr << "error: " << e.what() << '\n';
        MPI_Finalize();
        return 2;
    }
    cfg.backend = backend;  // la etiqueta la fija el ejecutable, no el archivo de configuración

    // El híbrido llama a MPI solo desde el hilo principal: exige al menos MPI_THREAD_FUNNELED.
    if (cfg.backend == "hibrido" && provisto < MPI_THREAD_FUNNELED) {
        if (rango == 0)
            std::cerr << "error: MPI concedió " << nombre_nivel(provisto) << " y el híbrido exige MPI_THREAD_FUNNELED\n";
        MPI_Finalize();
        return 2;
    }

    int codigo = 0;
    try {
        const FuncionEscenario escenario = escenario_del_modelo(cfg);
        const auto [nodos, distribucion] = distribucion_por_nodo(MPI_COMM_WORLD, rango, procesos);

        MPI_Barrier(MPI_COMM_WORLD);
        const double t0 = MPI_Wtime();
        pp::Acumulador local;
        const ResumenRango res = esquema(MPI_COMM_WORLD, cfg, escenario, local);

        // Una sola colectiva: k, n y los bins se suman en el rango 0 (contrato §3).
        std::vector<std::uint64_t> en(2 + pp::NBINS), fuera(2 + pp::NBINS, 0);
        en[0] = local.k;
        en[1] = local.n;
        std::copy(local.hist.begin(), local.hist.end(), en.begin() + 2);
        MPI_Reduce(en.data(), fuera.data(), 2 + pp::NBINS, MPI_UINT64_T, MPI_SUM, 0, MPI_COMM_WORLD);
        const double tiempo = MPI_Wtime() - t0;

        const std::uint64_t mio[6] = {res.inicio, res.fin, res.bloques, res.n_local, res.coherente ? 1ULL : 0ULL, res.hilos};
        std::vector<std::uint64_t> todos(rango == 0 ? 6 * static_cast<size_t>(procesos) : 0);
        MPI_Gather(mio, 6, MPI_UINT64_T, todos.data(), 6, MPI_UINT64_T, 0, MPI_COMM_WORLD);

        if (rango == 0) {
            pp::Acumulador g;
            g.k = fuera[0];
            g.n = fuera[1];
            std::copy(fuera.begin() + 2, fuera.end(), g.hist.begin());

            std::cout << "[verif] backend=" << cfg.backend << " procesos=" << procesos << " n_solicitado=" << cfg.n
                      << " nivel_hilos_mpi=" << nombre_nivel(provisto) << " nucleo=pp_core\n";
            if (cfg.backend == "hibrido")
                std::cout << "[verif] hibrido procesos=" << procesos << " hilos_por_proceso=" << res.hilos
                          << " nucleos_totales=" << static_cast<std::uint64_t>(procesos) * res.hilos
                          << " schedule=" << res.schedule << " OMP_PROC_BIND=" << entorno_o("OMP_PROC_BIND", "no_definida")
                          << " OMP_PLACES=" << entorno_o("OMP_PLACES", "no_definida") << '\n';
            std::uint64_t suma_local = 0;
            bool coherentes = true;
            for (int r = 0; r < procesos; ++r) {
                const std::uint64_t* t = &todos[6 * static_cast<size_t>(r)];
                std::cout << "[verif] rango=" << r;
                if (cfg.backend == "mpi_dinamico") std::cout << " bloques=" << t[2];
                else std::cout << " inicio=" << t[0] << " fin=" << t[1];
                if (cfg.backend == "hibrido") std::cout << " hilos=" << t[5];
                std::cout << " n_local=" << t[3] << '\n';
                suma_local += t[3];
                coherentes = coherentes && t[4] == 1;
            }
            if (cfg.backend != "mpi_dinamico") {  // intervalos contiguos, sin solape ni huecos
                std::uint64_t esperado = 0;
                for (int r = 0; r < procesos; ++r) {
                    const std::uint64_t* t = &todos[6 * static_cast<size_t>(r)];
                    if (t[0] != esperado || t[1] < t[0]) coherentes = false;
                    esperado = t[1];
                }
                if (esperado != cfg.n) coherentes = false;
            }
            std::uint64_t suma_hist = 0;
            for (std::uint64_t h : g.hist) suma_hist += h;
            const bool ok = coherentes && g.n == cfg.n && suma_local == cfg.n && suma_hist == g.n && g.k <= g.n;
            std::cout << "[verif] suma_n=" << g.n << " suma_n_rangos=" << suma_local << " suma_hist=" << suma_hist
                      << " k=" << g.k << " estado=" << (ok ? "OK" : "FALLO") << '\n';
            if (!ok) codigo = 3;

            if (cfg.verificar && ok) {  // V1: igual a la referencia secuencial, bit a bit
                pp::Acumulador ref;
                for (std::uint64_t j = 0; j < cfg.n; ++j) escenario(j, ref);
                const bool igual = ref == g;
                std::cout << "[verif] v1_referencia=" << (igual ? "OK" : "FALLO") << " k_ref=" << ref.k << '\n';
                if (!igual) codigo = 3;
            }
            std::cout << "[verif] tiempo_s=" << tiempo << '\n';

            if (codigo == 0) {
                pp::FilaResultado fila;
                fila.cfg = cfg;
                fila.acc = g;
                fila.meta = pp::capturar_metadatos();
                fila.meta.tiempo_s = tiempo;
                fila.meta.hilos_usados = static_cast<int>(res.hilos);
                fila.meta.schedule_usado = res.schedule;
                fila.meta.procesos = procesos;
                fila.meta.nodos = nodos;
                fila.meta.distribucion = distribucion;
                if (!cfg.silencioso) pp::imprimir_resumen(fila);
                if (!cfg.salida.empty()) pp::escribir_csv(cfg.salida, fila);
            }
        }
    } catch (const std::exception& e) {
        std::cerr << "error en el rango " << rango << ": " << e.what() << '\n';
        MPI_Abort(MPI_COMM_WORLD, 2);
    }
    MPI_Bcast(&codigo, 1, MPI_INT, 0, MPI_COMM_WORLD);
    MPI_Finalize();
    return codigo;
}

}  // namespace mpi_pi
