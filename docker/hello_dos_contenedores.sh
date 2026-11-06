#!/usr/bin/env bash
# T05 | Responsable: Miguel | Se ejecuta dentro de nodo1 (docker/compose-hello.yaml).
# Compila el hola híbrido en el volumen compartido y lanza un rango MPI por contenedor.
set -euo pipefail

BIN=/opt/hello/hello_hibrido
mpicxx -fopenmp -O2 -o "$BIN" docker/hello_hibrido.cpp

# Espera a que sshd de nodo2 acepte conexiones (máx. ~30 s).
for _ in $(seq 1 30); do
  ssh -o ConnectTimeout=1 nodo2 true 2>/dev/null && break
  sleep 1
done

# Un rango por nodo; sin enlazado para que los hilos OpenMP no compartan un único núcleo.
# btl tcp/self: entre contenedores no hay memoria compartida.
exec mpirun -np 2 --host nodo1:1,nodo2:1 --bind-to none \
  -x OMP_NUM_THREADS \
  --mca btl tcp,self --mca btl_tcp_if_include eth0 --mca oob_tcp_if_include eth0 \
  "$BIN"
