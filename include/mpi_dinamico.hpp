// T20 | Responsable: David | Interfaz de la cola MPI dinámica (E2).
#pragma once

#include "mpi_comun.hpp"

namespace mpi_pi {

// Etiquetas distintas por tipo de mensaje (docs/definicion-proyecto.docx §8.4).
constexpr int ETIQUETA_REQ = 101;   // trabajador -> maestro: solicitud de trabajo
constexpr int ETIQUETA_WORK = 102;  // maestro -> trabajador: rango [i0, i1)
constexpr int ETIQUETA_STOP = 103;  // maestro -> trabajador: fin, uno por trabajador

// Esquema E2: el rango 0 reparte bloques de `o.lote` índices; los demás los procesan hasta STOP.
// Con un solo proceso el rango 0 procesa todo localmente.
ResumenRango esquema_dinamico(MPI_Comm comm, const pp::Configuracion& cfg, const FuncionEscenario& escenario, pp::Acumulador& local);

// T41 (Lita): procesa un bloque WORK completo [i0, i1) de índices locales en el acumulador.
using FuncionBloque = std::function<void(std::uint64_t i0, std::uint64_t i1, pp::Acumulador&)>;

// El mismo E2 (mismo maestro y mismos mensajes REQ/WORK/STOP), pero cada rango procesa sus bloques con
// la función que recibe. esquema_dinamico es el caso en que la función recorre el bloque escenario por
// escenario; el trabajador GPU de EXT2 (src/backends/cuda/trabajador_mpi.cpp) lanza un kernel por bloque.
ResumenRango esquema_dinamico_bloques(MPI_Comm comm, const pp::Configuracion& cfg, const FuncionBloque& bloque,
                                      pp::Acumulador& local);

}  // namespace mpi_pi
