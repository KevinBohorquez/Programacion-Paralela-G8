// Sala de control | Líneas de avance en stderr con --progreso (docs/contrato-sala-control.md §1).
#include "progreso.hpp"

#include <cstdio>

namespace pp {

namespace {
bool g_activo = false;
int g_rango = -1;
}  // namespace

void activar_progreso(bool activo) { g_activo = activo; }
bool progreso_activo() { return g_activo; }
void fijar_rango_progreso(int rango) { g_rango = rango; }
int rango_progreso() { return g_rango; }

Progreso::Progreso(std::uint64_t total, int rango) : total_(total), rango_(rango) {}

void Progreso::sumar(std::uint64_t cuantos) {
    const std::uint64_t hecho = hecho_.fetch_add(cuantos, std::memory_order_relaxed) + cuantos;
    const std::uint64_t pct = total_ == 0 ? 100 : hecho * 100 / total_;
    if (static_cast<std::int64_t>(pct) <= ultimo_pct_.load(std::memory_order_relaxed)) return;  // vía rápida
    imprimir(hecho, pct);
}

void Progreso::terminar() { imprimir(hecho_.load(), 100); }

void Progreso::imprimir(std::uint64_t hecho, std::uint64_t pct) {
    // Bajo el cerrojo: una sola impresión por umbral y valores de hecho crecientes.
    std::lock_guard<std::mutex> l(mutex_);
    if (static_cast<std::int64_t>(pct) <= ultimo_pct_.load(std::memory_order_relaxed)) return;
    if (pct >= 100) {
        if (hecho < total_) return;  // la final solo sale con hecho = total
        hecho = total_;
    }
    ultimo_pct_.store(static_cast<std::int64_t>(pct), std::memory_order_relaxed);
    if (rango_ >= 0)
        std::fprintf(stderr, "[prog] rango=%d hecho=%llu total=%llu\n", rango_, static_cast<unsigned long long>(hecho),
                     static_cast<unsigned long long>(total_));
    else
        std::fprintf(stderr, "[prog] hecho=%llu total=%llu\n", static_cast<unsigned long long>(hecho),
                     static_cast<unsigned long long>(total_));
    std::fflush(stderr);
}

void reportar_bloque(int rango, std::uint64_t i0, std::uint64_t i1) {
    std::fprintf(stderr, "[prog] rango=%d bloque=%llu,%llu\n", rango, static_cast<unsigned long long>(i0),
                 static_cast<unsigned long long>(i1));
    std::fflush(stderr);
}

}  // namespace pp
