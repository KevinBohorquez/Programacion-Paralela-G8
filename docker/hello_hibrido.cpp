// T05 | Responsable: Miguel | Prueba mínima de MPI + OpenMP dentro de la imagen.
// Cada rango abre una región paralela; los hilos solo escriben en su casilla y el
// rango 0 imprime todo ordenado por (rango, hilo), así la salida es determinista.
// Compilar: mpicxx -fopenmp -O2 -o hello_hibrido docker/hello_hibrido.cpp
// Ejecutar: OMP_NUM_THREADS=2 mpirun -np 2 ./hello_hibrido
#include <mpi.h>
#include <omp.h>
#include <unistd.h>

#include <cstdio>
#include <cstring>
#include <string>
#include <vector>

namespace {
constexpr int kLinea = 160;  // bytes por línea en el gather

const char* nombre_nivel(int nivel) {
  switch (nivel) {
    case MPI_THREAD_SINGLE: return "MPI_THREAD_SINGLE";
    case MPI_THREAD_FUNNELED: return "MPI_THREAD_FUNNELED";
    case MPI_THREAD_SERIALIZED: return "MPI_THREAD_SERIALIZED";
    case MPI_THREAD_MULTIPLE: return "MPI_THREAD_MULTIPLE";
    default: return "desconocido";
  }
}
}  // namespace

int main(int argc, char** argv) {
  // Mismo nivel que el backend híbrido (T24): solo el hilo maestro llama a MPI.
  int provisto = 0;
  MPI_Init_thread(&argc, &argv, MPI_THREAD_FUNNELED, &provisto);

  int rango = 0, tamano = 0;
  MPI_Comm_rank(MPI_COMM_WORLD, &rango);
  MPI_Comm_size(MPI_COMM_WORLD, &tamano);

  if (provisto < MPI_THREAD_FUNNELED) {
    if (rango == 0) {
      std::fprintf(stderr, "ERROR: se pidió MPI_THREAD_FUNNELED y se obtuvo %s\n",
                   nombre_nivel(provisto));
    }
    MPI_Abort(MPI_COMM_WORLD, 1);
  }

  char host[64] = {0};
  gethostname(host, sizeof(host) - 1);

  // Todos los rangos deben aportar el mismo número de líneas al gather.
  const int max_hilos = omp_get_max_threads();
  int hilos_global = 0;
  MPI_Allreduce(&max_hilos, &hilos_global, 1, MPI_INT, MPI_MAX, MPI_COMM_WORLD);

  std::vector<char> local(static_cast<size_t>(hilos_global) * kLinea, '\0');
#pragma omp parallel num_threads(max_hilos)
  {
    const int hilo = omp_get_thread_num();
    std::snprintf(&local[static_cast<size_t>(hilo) * kLinea], kLinea,
                  "rango %d/%d | hilo %d/%d | host %s", rango, tamano, hilo,
                  omp_get_num_threads(), host);
  }

  std::vector<char> todo;
  if (rango == 0) todo.resize(local.size() * static_cast<size_t>(tamano));
  MPI_Gather(local.data(), static_cast<int>(local.size()), MPI_CHAR, todo.data(),
             static_cast<int>(local.size()), MPI_CHAR, 0, MPI_COMM_WORLD);

  if (rango == 0) {
    char version[MPI_MAX_LIBRARY_VERSION_STRING] = {0};
    int largo = 0;
    MPI_Get_library_version(version, &largo);
    const std::string primera(version, std::strcspn(version, ",\n"));
    std::printf("MPI: %s\n", primera.c_str());
    std::printf("Nivel de hilos: pedido %s, provisto %s\n",
                nombre_nivel(MPI_THREAD_FUNNELED), nombre_nivel(provisto));
    std::printf("Procesos MPI: %d | hilos OpenMP máx. por proceso: %d\n", tamano,
                hilos_global);
    for (size_t i = 0; i < todo.size(); i += kLinea) {
      if (todo[i] != '\0') std::printf("%s\n", &todo[i]);
    }
  }

  MPI_Finalize();
  return 0;
}
