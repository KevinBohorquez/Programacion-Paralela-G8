// Sala de control | Líneas de avance en stderr con --progreso (docs/contrato-sala-control.md §1).
#pragma once

#include <atomic>
#include <cstdint>
#include <mutex>

namespace pp {

// Estado del proceso: lo fija parsear_argumentos (--progreso) y, en MPI, ejecutar_mpi (rango).
// Sin --progreso no se imprime nada y los bucles no cambian.
void activar_progreso(bool activo);
bool progreso_activo();
void fijar_rango_progreso(int rango);  // < 0: el emisor no lleva "rango=" (serial, OpenMP)
int rango_progreso();

// Escenarios entre consultas del contador: mantiene el costo del bucle despreciable.
constexpr std::uint64_t PASO_PROGRESO = 4096;

// Contador de avance de un emisor ("[prog] [rango=<r> ]hecho=<h> total=<t>").
// sumar() es seguro entre hilos (contador atómico); se imprime a lo sumo una línea por cada 1 %
// de total, una sola vez por umbral, y la línea final con hecho=total.
class Progreso {
public:
    Progreso(std::uint64_t total, int rango);
    void sumar(std::uint64_t cuantos);
    void terminar();  // imprime la línea final si aún no salió (p. ej. total = 0)

private:
    void imprimir(std::uint64_t hecho, std::uint64_t pct);

    const std::uint64_t total_;
    const int rango_;
    std::atomic<std::uint64_t> hecho_{0};
    std::atomic<std::int64_t> ultimo_pct_{-1};  // último porcentaje impreso
    std::mutex mutex_;
};

// E2: el maestro anuncia que asignó [i0, i1) al trabajador `rango`.
void reportar_bloque(int rango, std::uint64_t i0, std::uint64_t i1);

}  // namespace pp
