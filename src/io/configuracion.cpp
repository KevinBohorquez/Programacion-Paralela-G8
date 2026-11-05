// T12 | Responsable: Ashley | Lectura de configuración y argumentos según contrato T02.
//
// NOTA: docs/contratos.md (T02) no está en el repositorio. Este formato (YAML plano
// "clave: valor") y estas banderas son la interpretación provisional del plan S08 y
// deben contrastarse con el contrato de David antes de congelarse.
#include <cstdlib>
#include <fstream>
#include <iostream>
#include <sstream>
#include <stdexcept>

#include "progreso.hpp"
#include "resultados.hpp"

namespace pp {

namespace {

std::string recortar(const std::string& s) {
    const char* esp = " \t\r\n\"'";
    const size_t a = s.find_first_not_of(esp);
    if (a == std::string::npos) return "";
    const size_t b = s.find_last_not_of(esp);
    return s.substr(a, b - a + 1);
}

double a_double(const std::string& clave, const std::string& v) {
    try {
        size_t pos = 0;
        const double x = std::stod(v, &pos);
        if (pos != v.size()) throw std::invalid_argument("resto");
        return x;
    } catch (const std::exception&) {
        throw std::runtime_error("valor numérico inválido para '" + clave + "': '" + v + "'");
    }
}

uint64_t a_uint64(const std::string& clave, const std::string& v) {
    if (v.empty() || v[0] == '-') throw std::runtime_error("entero sin signo inválido para '" + clave + "': '" + v + "'");
    try {
        size_t pos = 0;
        const unsigned long long x = std::stoull(v, &pos, 10);
        if (pos != v.size()) throw std::invalid_argument("resto");
        return static_cast<uint64_t>(x);
    } catch (const std::exception&) {
        throw std::runtime_error("entero inválido para '" + clave + "': '" + v + "'");
    }
}

// Asigna un par clave/valor; devuelve false si la clave no existe.
bool asignar(Configuracion& c, const std::string& k, const std::string& v) {
    if (k == "backend") c.backend = v;
    else if (k == "estacion") c.estacion = v;
    else if (k == "regimen") c.regimen = v;
    else if (k == "config_id") c.config_id = a_uint64(k, v);
    else if (k == "semilla") c.semilla = a_uint64(k, v);
    else if (k == "n") c.n = a_uint64(k, v);
    else if (k == "hilos") c.hilos = static_cast<int>(a_uint64(k, v));
    else if (k == "schedule") c.schedule = v;
    else if (k == "salida") c.salida = v;
    else if (k == "lote") c.lote = a_uint64(k, v);
    else if (k == "repeticion") c.repeticion = static_cast<int>(a_uint64(k, v));
    else if (k == "p01") c.params.p01 = a_double(k, v);
    else if (k == "p11") c.params.p11 = a_double(k, v);
    else if (k == "alfa") c.params.alfa = a_double(k, v);
    else if (k == "theta") c.params.theta = a_double(k, v);
    else if (k == "capacidad") c.params.capacidad = a_double(k, v);
    else if (k == "umbral") c.params.umbral = a_double(k, v);
    else if (k == "dias") c.params.dias = static_cast<int>(a_uint64(k, v));
    else return false;
    return true;
}

void ayuda() {
    std::cout <<
        "Uso: pp_<backend> [--config archivo.yaml] [opciones]\n"
        "  --n N               escenarios de la configuración (por defecto 1000000)\n"
        "  --semilla S         semilla global de 64 bits (alias: --seed)\n"
        "  --config-id c       identificador de configuración; índice global = c*N + j\n"
        "  --p01 --p11 --alfa --theta --capacidad --umbral --dias   parámetros del modelo\n"
        "  --estacion X --regimen Y   etiquetas de la configuración (van al CSV)\n"
        "  --hilos T           hilos OpenMP (solo pp_openmp)\n"
        "  --schedule S        static|dynamic|guided[:chunk]; vacío usa OMP_SCHEDULE\n"
        "  --salida ruta.csv   agrega una fila al CSV de resultados\n"
        "  --lote B            tamaño de bloque de la cola (solo mpi_dinamico; por defecto 62500)\n"
        "  --repeticion R      etiqueta de la fila del CSV (0 = calentamiento)\n"
        "  --calentamiento     marca la fila como calentamiento (repeticion 0)\n"
        "  --verificar         MPI: compara k e histograma con la referencia secuencial (V1)\n"
        "  --silencioso        no imprime el resumen\n"
        "  --progreso          imprime líneas de avance [prog] en stderr (sala de control)\n"
        "  --ayuda            esta ayuda\n";
}

}  // namespace

void cargar_archivo_configuracion(const std::string& ruta, Configuracion& cfg) {
    std::ifstream in(ruta);
    if (!in) throw std::runtime_error("no se puede abrir la configuración: " + ruta);
    std::string linea;
    int num = 0;
    while (std::getline(in, linea)) {
        ++num;
        const size_t hash = linea.find('#');
        if (hash != std::string::npos) linea.erase(hash);
        linea = recortar(linea);
        if (linea.empty()) continue;
        const size_t dp = linea.find(':');
        if (dp == std::string::npos)
            throw std::runtime_error(ruta + ":" + std::to_string(num) + ": se esperaba 'clave: valor'");
        const std::string k = recortar(linea.substr(0, dp));
        const std::string v = recortar(linea.substr(dp + 1));
        if (!asignar(cfg, k, v))
            throw std::runtime_error(ruta + ":" + std::to_string(num) + ": clave desconocida '" + k + "'");
    }
}

bool parsear_argumentos(int argc, char** argv, Configuracion& cfg) {
    // 1.º el archivo (si existe), 2.º las banderas, para que éstas lo sobrescriban.
    for (int i = 1; i < argc; ++i)
        if (std::string(argv[i]) == "--config") {
            if (i + 1 >= argc) throw std::runtime_error("--config requiere una ruta");
            cargar_archivo_configuracion(argv[i + 1], cfg);
        }
    for (int i = 1; i < argc; ++i) {
        const std::string a = argv[i];
        if (a == "--ayuda" || a == "--help" || a == "-h") { ayuda(); return false; }
        if (a == "--silencioso") { cfg.silencioso = true; continue; }
        if (a == "--verificar") { cfg.verificar = true; continue; }
        if (a == "--progreso") { activar_progreso(true); continue; }
        if (a == "--calentamiento") { cfg.calentamiento = true; cfg.repeticion = 0; continue; }
        if (a == "--config") { ++i; continue; }
        if (a.rfind("--", 0) != 0) throw std::runtime_error("argumento inesperado: " + a);
        if (i + 1 >= argc) throw std::runtime_error("falta el valor de " + a);
        std::string k = a.substr(2);
        for (char& ch : k) if (ch == '-') ch = '_';
        if (k == "seed") k = "semilla";
        if (!asignar(cfg, k, argv[++i])) throw std::runtime_error("opción desconocida: " + a);
    }
    validar(cfg);
    return true;
}

void validar(const Configuracion& c) {
    const Parametros& p = c.params;
    auto prob = [](double x) { return x >= 0.0 && x <= 1.0; };
    if (c.n == 0) throw std::runtime_error("n debe ser > 0");
    if (p.dias <= 0) throw std::runtime_error("dias debe ser > 0");
    if (!prob(p.p01) || !prob(p.p11)) throw std::runtime_error("p01 y p11 deben estar en [0,1]");
    if (!(p.alfa > 0.0) || !(p.theta > 0.0)) throw std::runtime_error("alfa y theta deben ser > 0");
    if (p.capacidad < 0.0 || p.umbral < 0.0) throw std::runtime_error("capacidad y umbral deben ser >= 0");
    if (c.lote == 0) throw std::runtime_error("lote debe ser > 0");
    if (c.hilos < 0) throw std::runtime_error("hilos debe ser >= 0");
    // c*N + j debe caber en 64 bits para que el índice global sea único.
    if (c.config_id != 0 && c.n > UINT64_MAX / (c.config_id + 1))
        throw std::runtime_error("config_id*n + n desborda uint64");
}

}  // namespace pp
