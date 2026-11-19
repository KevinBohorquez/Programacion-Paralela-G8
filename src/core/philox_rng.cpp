// T11 | Responsable: Ashley | Generador de números aleatorios indexado (Philox4x32-10).
#include "nucleo_hd.hpp"
#include "simulacion.hpp"

namespace pp {

namespace {
inline uint64_t splitmix64(uint64_t x) {
    x += 0x9E3779B97F4A7C15ull;
    x = (x ^ (x >> 30)) * 0xBF58476D1CE4E5B9ull;
    x = (x ^ (x >> 27)) * 0x94D049BB133111EBull;
    return x ^ (x >> 31);
}
}  // namespace

// T38: Philox está en include/nucleo_hd.hpp, compartido con el kernel CUDA.
Bloque4 philox4x32_10(Bloque4 c, uint32_t k0, uint32_t k1) { return hd::philox4x32_10(c, k0, k1); }

uint64_t derivar_clave(uint64_t semilla, uint64_t config_id) {
    // Mezcla determinista de semilla global y configuración; no depende de hilos ni procesos.
    return splitmix64(splitmix64(semilla) ^ (config_id * 0xD6E8FEB86659FD93ull + 0x2545F4914F6CDD1Dull));
}

double uniforme32(uint32_t w) { return hd::uniforme32(w); }

}  // namespace pp
