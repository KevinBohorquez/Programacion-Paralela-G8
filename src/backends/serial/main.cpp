// T11 | Responsable: Ashley | Ejecutable secuencial de referencia (línea base T1 y verdad para V1).
#include <algorithm>
#include <chrono>
#include <exception>
#include <iostream>

#include "progreso.hpp"
#include "resultados.hpp"
#include "simulacion.hpp"

int main(int argc, char** argv) {
    try {
        pp::Configuracion cfg;
        cfg.backend = "serial";
        if (!pp::parsear_argumentos(argc, argv, cfg)) return 0;
        cfg.backend = "serial";  // la etiqueta la fija el ejecutable, no el archivo de configuración

        const uint64_t clave = pp::derivar_clave(cfg.semilla, cfg.config_id);
        const uint64_t base = cfg.config_id * cfg.n;  // índice global i = c*N + j

        pp::Acumulador acc;
        const auto t0 = std::chrono::steady_clock::now();
        if (!pp::progreso_activo()) {
            for (uint64_t j = 0; j < cfg.n; ++j) acc.agregar(pp::simular_escenario(cfg.params, clave, base + j));
        } else {  // mismo recorrido por tramos de PASO_PROGRESO; el avance se informa entre tramos
            pp::Progreso prog(cfg.n, -1);
            for (uint64_t j0 = 0; j0 < cfg.n; j0 += pp::PASO_PROGRESO) {
                const uint64_t j1 = std::min(cfg.n, j0 + pp::PASO_PROGRESO);
                for (uint64_t j = j0; j < j1; ++j) acc.agregar(pp::simular_escenario(cfg.params, clave, base + j));
                prog.sumar(j1 - j0);
            }
            prog.terminar();
        }
        const auto t1 = std::chrono::steady_clock::now();

        pp::FilaResultado fila;
        fila.cfg = cfg;
        fila.acc = acc;
        fila.meta = pp::capturar_metadatos();
        fila.meta.tiempo_s = std::chrono::duration<double>(t1 - t0).count();
        fila.meta.hilos_usados = 1;
        if (!cfg.silencioso) pp::imprimir_resumen(fila);
        if (!cfg.salida.empty()) pp::escribir_csv(cfg.salida, fila);
        return 0;
    } catch (const std::exception& e) {
        std::cerr << "error: " << e.what() << "\n";
        return 2;
    }
}
