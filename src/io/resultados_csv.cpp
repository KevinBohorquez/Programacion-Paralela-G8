// T12 | Responsable: Ashley | Escritura y lectura de CSV de resultados (contrato T02, ver nota en configuracion.cpp).
#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <set>
#include <sstream>
#include <stdexcept>
#include <thread>
#include <utility>
#include <vector>

#if defined(__unix__) || defined(__APPLE__)
#include <unistd.h>  // gethostname
#endif

#include "resultados.hpp"

#ifndef PP_COMMIT_GIT
#define PP_COMMIT_GIT "desconocido"
#endif

namespace pp {

namespace {

const char* COLUMNAS[] = {"backend", "estacion", "regimen", "config_id", "semilla", "n", "k", "p_hat",
                          "wilson_inf", "wilson_sup", "dias", "capacidad", "umbral", "p01", "p11", "alfa",
                          "theta", "hilos", "procesos", "repeticion", "calentamiento", "schedule", "afinidad", "tiempo_s", "commit", "cpu",
                          "nucleos_fisicos", "nucleos_logicos", "hist512",
                          // S15: agregadas al final para no mover las columnas anteriores.
                          "hardware", "nodos", "distribucion", "bloques", "hilos_por_bloque"};
constexpr size_t NCOL = sizeof(COLUMNAS) / sizeof(COLUMNAS[0]);

std::string limpiar(std::string s) {  // sin comas ni saltos: el CSV no usa comillas
    for (char& c : s) if (c == ',' || c == '\n' || c == '\r') c = ' ';
    return s;
}

std::string num(double x) {
    char buf[40];
    std::snprintf(buf, sizeof buf, "%.17g", x);
    return buf;
}

std::vector<std::string> separar(const std::string& linea, char sep) {
    std::vector<std::string> r;
    std::string campo;
    std::stringstream ss(linea);
    while (std::getline(ss, campo, sep)) r.push_back(campo);
    if (!linea.empty() && linea.back() == sep) r.emplace_back();
    return r;
}

std::string leer_cpu_modelo() {
    std::ifstream in("/proc/cpuinfo");
    std::string l;
    while (std::getline(in, l))
        if (l.rfind("model name", 0) == 0) {
            const size_t dp = l.find(':');
            if (dp != std::string::npos) return l.substr(dp + 2);
        }
    return "desconocido";
}

int contar_nucleos_fisicos() {
    std::ifstream in("/proc/cpuinfo");
    std::string l, fis = "0";
    std::set<std::pair<std::string, std::string>> unicos;
    while (std::getline(in, l)) {
        const size_t dp = l.find(':');
        if (dp == std::string::npos) continue;
        if (l.rfind("physical id", 0) == 0) fis = l.substr(dp + 2);
        else if (l.rfind("core id", 0) == 0) unicos.insert({fis, l.substr(dp + 2)});
    }
    return unicos.empty() ? 0 : static_cast<int>(unicos.size());
}

std::string leer_ram_gb() {  // MemTotal de /proc/meminfo en GiB con un decimal
    std::ifstream in("/proc/meminfo");
    std::string l;
    while (std::getline(in, l))
        if (l.rfind("MemTotal:", 0) == 0) {
            std::istringstream ss(l.substr(9));
            double kib = 0.0;
            if (ss >> kib) {
                char buf[32];
                std::snprintf(buf, sizeof buf, "%.1f", kib / (1024.0 * 1024.0));
                return buf;
            }
        }
    return "desconocida";
}

std::string opcional(int x) { return x > 0 ? std::to_string(x) : std::string(); }

}  // namespace

std::string nombre_nodo() {
#if defined(__unix__) || defined(__APPLE__)
    char buf[256] = {};
    if (gethostname(buf, sizeof buf - 1) == 0 && buf[0]) return buf;
#endif
    const char* h = std::getenv("HOSTNAME");
    return (h && *h) ? h : "desconocido";
}

MetadatosEjecucion capturar_metadatos() {
    MetadatosEjecucion m;
    const char* c = std::getenv("PP_COMMIT");
    m.commit = (c && *c) ? c : PP_COMMIT_GIT;
    m.cpu = leer_cpu_modelo();
    m.nucleos_logicos = static_cast<int>(std::thread::hardware_concurrency());
    m.nucleos_fisicos = contar_nucleos_fisicos();
    if (m.nucleos_fisicos == 0) m.nucleos_fisicos = m.nucleos_logicos;  // sin /proc/cpuinfo: mejor estimación
    const char* bind = std::getenv("OMP_PROC_BIND");
    const char* places = std::getenv("OMP_PLACES");
    m.afinidad = std::string("OMP_PROC_BIND=") + (bind ? bind : "no_definida") + ";OMP_PLACES=" + (places ? places : "no_definida");
    const std::string host = nombre_nodo();
    m.hardware = "host=" + host + ";ram_gb=" + leer_ram_gb();
    m.nodos = 1;
    m.distribucion = host + ":1";  // los ejecutables MPI la reemplazan con los procesos por nodo
    return m;
}

std::string encabezado_csv() {
    std::string s;
    for (size_t i = 0; i < NCOL; ++i) s += (i ? "," : "") + std::string(COLUMNAS[i]);
    return s;
}

std::string fila_csv(const FilaResultado& f) {
    const Intervalo ic = wilson(f.acc.k, f.acc.n);
    const double p_hat = f.acc.n ? static_cast<double>(f.acc.k) / static_cast<double>(f.acc.n) : 0.0;
    std::string h;
    for (int i = 0; i < NBINS; ++i) h += (i ? ";" : "") + std::to_string(f.acc.hist[static_cast<size_t>(i)]);
    const Parametros& p = f.cfg.params;
    const std::vector<std::string> v = {
        limpiar(f.cfg.backend), limpiar(f.cfg.estacion), limpiar(f.cfg.regimen), std::to_string(f.cfg.config_id),
        std::to_string(f.cfg.semilla), std::to_string(f.acc.n), std::to_string(f.acc.k), num(p_hat), num(ic.inf),
        num(ic.sup), std::to_string(p.dias), num(p.capacidad), num(p.umbral), num(p.p01), num(p.p11), num(p.alfa),
        num(p.theta), std::to_string(f.meta.hilos_usados), std::to_string(f.meta.procesos),
        std::to_string(f.cfg.repeticion), f.cfg.calentamiento ? "1" : "0", limpiar(f.meta.schedule_usado), limpiar(f.meta.afinidad),
        num(f.meta.tiempo_s), limpiar(f.meta.commit), limpiar(f.meta.cpu), std::to_string(f.meta.nucleos_fisicos),
        std::to_string(f.meta.nucleos_logicos), h, limpiar(f.meta.hardware), std::to_string(f.meta.nodos),
        limpiar(f.meta.distribucion), opcional(f.meta.bloques), opcional(f.meta.hilos_por_bloque)};
    std::string s;
    for (size_t i = 0; i < v.size(); ++i) s += (i ? "," : "") + v[i];
    return s;
}

void escribir_csv(const std::string& ruta, const FilaResultado& f) {
    bool nuevo = true;
    {
        std::ifstream in(ruta, std::ios::binary | std::ios::ate);
        if (in && in.tellg() > 0) nuevo = false;
    }
    if (!nuevo) {  // no mezclar filas de dos versiones del contrato en un mismo archivo
        std::ifstream in(ruta);
        std::string cab;
        std::getline(in, cab);
        if (!cab.empty() && cab.back() == '\r') cab.pop_back();
        if (cab != encabezado_csv())
            throw std::runtime_error("el CSV " + ruta + " tiene otra cabecera (versión anterior del contrato); use otro archivo");
    }
    std::ofstream out(ruta, std::ios::app);
    if (!out) throw std::runtime_error("no se puede escribir el CSV: " + ruta);
    if (nuevo) out << encabezado_csv() << "\n";
    out << fila_csv(f) << "\n";
    if (!out) throw std::runtime_error("error al escribir el CSV: " + ruta);
}

FilaResultado leer_primera_fila_csv(const std::string& ruta) {
    std::ifstream in(ruta);
    if (!in) throw std::runtime_error("no se puede leer el CSV: " + ruta);
    std::string cab, fila;
    if (!std::getline(in, cab) || cab != encabezado_csv()) throw std::runtime_error("encabezado CSV inesperado");
    if (!std::getline(in, fila)) throw std::runtime_error("CSV sin filas de datos");
    const std::vector<std::string> v = separar(fila, ',');
    if (v.size() != NCOL) throw std::runtime_error("número de columnas inesperado");
    FilaResultado f;
    f.cfg.backend = v[0]; f.cfg.estacion = v[1]; f.cfg.regimen = v[2];
    f.cfg.config_id = std::stoull(v[3]); f.cfg.semilla = std::stoull(v[4]);
    f.acc.n = std::stoull(v[5]); f.acc.k = std::stoull(v[6]);
    f.cfg.n = f.acc.n;
    Parametros& p = f.cfg.params;
    p.dias = std::stoi(v[10]); p.capacidad = std::stod(v[11]); p.umbral = std::stod(v[12]);
    p.p01 = std::stod(v[13]); p.p11 = std::stod(v[14]); p.alfa = std::stod(v[15]); p.theta = std::stod(v[16]);
    f.meta.hilos_usados = std::stoi(v[17]); f.meta.procesos = std::stoi(v[18]);
    f.cfg.repeticion = std::stoi(v[19]); f.cfg.calentamiento = v[20] == "1";
    f.meta.schedule_usado = v[21]; f.meta.afinidad = v[22];
    f.meta.tiempo_s = std::stod(v[23]); f.meta.commit = v[24]; f.meta.cpu = v[25];
    f.meta.nucleos_fisicos = std::stoi(v[26]); f.meta.nucleos_logicos = std::stoi(v[27]);
    const std::vector<std::string> h = separar(v[28], ';');
    if (h.size() != static_cast<size_t>(NBINS)) throw std::runtime_error("histograma con tamaño inesperado");
    for (size_t i = 0; i < h.size(); ++i) f.acc.hist[i] = std::stoull(h[i]);
    f.meta.hardware = v[29]; f.meta.nodos = std::stoi(v[30]); f.meta.distribucion = v[31];
    f.meta.bloques = v[32].empty() ? 0 : std::stoi(v[32]);
    f.meta.hilos_por_bloque = v[33].empty() ? 0 : std::stoi(v[33]);
    return f;
}

void imprimir_resumen(const FilaResultado& f) {
    const Intervalo ic = wilson(f.acc.k, f.acc.n);
    const double p_hat = f.acc.n ? static_cast<double>(f.acc.k) / static_cast<double>(f.acc.n) : 0.0;
    std::cout << "backend=" << f.cfg.backend << " hilos=" << f.meta.hilos_usados;
    if (!f.meta.schedule_usado.empty()) std::cout << " schedule=" << f.meta.schedule_usado;
    std::cout << " semilla=" << f.cfg.semilla << " config_id=" << f.cfg.config_id << "\n"
              << "n=" << f.acc.n << " k=" << f.acc.k << " p_hat=" << num(p_hat) << " wilson=[" << num(ic.inf) << ", "
              << num(ic.sup) << "]\n"
              << "tiempo_s=" << num(f.meta.tiempo_s) << " cpu=\"" << f.meta.cpu << "\" fisicos=" << f.meta.nucleos_fisicos
              << " logicos=" << f.meta.nucleos_logicos << " " << f.meta.afinidad << "\n";
}

}  // namespace pp
