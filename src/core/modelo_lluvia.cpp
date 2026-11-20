// T11 | Responsable: Ashley | Ocurrencia Markov y monto gamma (Marsaglia–Tsang). · H5: factor de intensidad por temporada (Lita).
// T38: la implementación está en include/nucleo_hd.hpp, compartida con el kernel CUDA.
#include "nucleo_hd.hpp"
#include "simulacion.hpp"

namespace pp {

bool ocurre_lluvia(const Parametros& p, uint64_t clave, uint64_t idx, uint32_t dia, bool llovio_ayer) {
    return hd::ocurre_lluvia(p, clave, idx, dia, llovio_ayer);
}

double monto_gamma(const Parametros& p, uint64_t clave, uint64_t idx, uint32_t dia) {
    return hd::monto_gamma(p, clave, idx, dia);
}

double factor_temporada(const Parametros& p, uint64_t clave, uint64_t idx) {
    return hd::factor_temporada(p, clave, idx);
}

}  // namespace pp
