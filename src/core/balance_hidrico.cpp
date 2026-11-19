// T11 | Responsable: Ashley | Balance hídrico (Lindley) y criterio de inundación.
// T38: la implementación está en include/nucleo_hd.hpp, compartida con el kernel CUDA.
#include "nucleo_hd.hpp"
#include "simulacion.hpp"

namespace pp {

double actualizar_acumulado(double acumulado, double lluvia, double capacidad) {
    return hd::actualizar_acumulado(acumulado, lluvia, capacidad);
}

Resultado simular_escenario(const Parametros& p, uint64_t clave, uint64_t idx) {
    return hd::simular_escenario(p, clave, idx);
}

}  // namespace pp
