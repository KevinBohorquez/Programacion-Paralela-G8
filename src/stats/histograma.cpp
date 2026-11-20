// T12 | Responsable: Ashley | Histograma de 512 clases de 1 mm y acumulador.
#include <cmath>

#include "nucleo_hd.hpp"
#include "resultados.hpp"

namespace pp {

int clase_histograma(double amax) {
    return hd::clase_histograma(amax);  // T38: compartida con el kernel CUDA (nucleo_hd.hpp)
}

void Acumulador::agregar(const Resultado& r) {
    k += r.inundacion ? 1u : 0u;
    n += 1u;
    hist[static_cast<size_t>(clase_histograma(r.amax))] += 1u;
}

void Acumulador::combinar(const Acumulador& o) {
    k += o.k;
    n += o.n;
    for (size_t i = 0; i < hist.size(); ++i) hist[i] += o.hist[i];
}

}  // namespace pp
