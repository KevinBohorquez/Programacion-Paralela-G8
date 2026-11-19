// T38 | Responsable: Lita | Ejecutable pp_cuda (EXT1): mismas opciones y mismo CSV que los demás backends,
// más --bloques y --hilos-por-bloque (columnas bloques e hilos_por_bloque del CSV).
#include <chrono>
#include <exception>
#include <iostream>

#include "cuda.hpp"
#include "progreso.hpp"
#include "resultados.hpp"
#include "simulacion.hpp"

int main(int argc, char** argv) {
    try {
        pp::Configuracion cfg;
        cfg.backend = "cuda";
        if (!pp::parsear_argumentos(argc, argv, cfg)) return 0;
        cfg.backend = "cuda";  // la etiqueta la fija el ejecutable, no el archivo de configuración

        const uint64_t clave = pp::derivar_clave(cfg.semilla, cfg.config_id);
        const uint64_t base = cfg.config_id * cfg.n;  // índice global i = c*N + j

        pp::inicializar_cuda();  // contexto CUDA fuera del tiempo medido
        pp::EjecucionCuda ej;
        const auto t0 = std::chrono::steady_clock::now();
        if (!pp::progreso_activo()) {
            ej = pp::simular_cuda(cfg.params, clave, base, cfg.n, cfg.bloques, cfg.hilos_por_bloque);
        } else {
            pp::Progreso prog(cfg.n, -1);
            ej = pp::simular_cuda(cfg.params, clave, base, cfg.n, cfg.bloques, cfg.hilos_por_bloque,
                                  [&prog](uint64_t hechos) { prog.sumar(hechos); });
            prog.terminar();
        }
        const auto t1 = std::chrono::steady_clock::now();

        // V3: el histograma debe sumar n (cada escenario cae en exactamente una clase).
        uint64_t suma = 0;
        for (uint64_t h : ej.acc.hist) suma += h;
        if (suma != cfg.n || ej.acc.k > cfg.n) {
            std::cerr << "error: verificación fallida: suma_hist=" << suma << " n=" << cfg.n << " k=" << ej.acc.k
                      << "\n";
            return 3;
        }

        pp::FilaResultado fila;
        fila.cfg = cfg;
        fila.acc = ej.acc;
        fila.meta = pp::capturar_metadatos();
        fila.meta.tiempo_s = std::chrono::duration<double>(t1 - t0).count();
        fila.meta.hilos_usados = 1;
        fila.meta.hardware += ";" + pp::descripcion_gpu();
        fila.meta.bloques = ej.bloques;
        fila.meta.hilos_por_bloque = ej.hilos_por_bloque;
        if (!cfg.silencioso) {
            pp::imprimir_resumen(fila);
            std::cout << "bloques=" << ej.bloques << " hilos_por_bloque=" << ej.hilos_por_bloque
                      << " lanzamientos=" << ej.lanzamientos << " " << pp::descripcion_gpu() << "\n";
        }
        if (!cfg.salida.empty()) pp::escribir_csv(cfg.salida, fila);
        return 0;
    } catch (const std::exception& e) {
        std::cerr << "error: " << e.what() << "\n";
        return 2;
    }
}
