// T11 | Responsable: Ashley | Balance hídrico (Lindley) y criterio de inundación.
#include <algorithm>

#include "simulacion.hpp"

namespace pp {

double actualizar_acumulado(double acumulado, double lluvia, double capacidad) {
    return std::max(0.0, acumulado + lluvia - capacidad);
}

Resultado simular_escenario(const Parametros& p, uint64_t clave, uint64_t idx) {
    double a = 0.0;
    double amax = 0.0;
    bool lluvioso = false;  // el día previo a la temporada se toma como seco
    // H5: intensidad de la temporada, sorteada una vez. Vale exactamente 1.0 con kappa infinito, y
    // x * 1.0 == x en punto flotante, así que el modelo sin H5 no cambia ni un bit.
    const double m = factor_temporada(p, clave, idx);
    for (int d = 0; d < p.dias; ++d) {
        const uint32_t dia = static_cast<uint32_t>(d);
        lluvioso = ocurre_lluvia(p, clave, idx, dia, lluvioso);
        const double r = lluvioso ? monto_gamma(p, clave, idx, dia) * m : 0.0;
        a = actualizar_acumulado(a, r, p.capacidad);
        amax = std::max(amax, a);
    }
    return Resultado{amax > p.umbral, amax};
}

}  // namespace pp
