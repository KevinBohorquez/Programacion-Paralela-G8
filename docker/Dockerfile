# T05 | Responsable: Miguel | Imagen base reproducible del proyecto.
# Solo aporta la cadena de herramientas: el código se monta en /work al ejecutar
#   docker run --rm -v "<repo>:/work" -w /work pp-g8 <comando>
# Mismo sistema y paquetes que la CI (.github/workflows/ci.yml, ubuntu-24.04).
FROM ubuntu:24.04

ARG DEBIAN_FRONTEND=noninteractive

# - cmake, g++, clang, libomp-dev, python3-pytest: trabajo "construir-y-probar" de la CI (V5 usa clang + Archer).
# - openmpi-bin, libopenmpi-dev: trabajo "mpi" de la CI.
# - libclang-rt-18-dev: runtime de ThreadSanitizer para V5 (el runner de GitHub ya lo trae).
# - git: src/io/CMakeLists.txt registra el commit en los metadatos.
# - python3-matplotlib, python3-scipy: gráficos y análisis de scripts/bench.
# - openssh-client, openssh-server: lanzamiento de mpirun entre dos contenedores (compose-hello.yaml).
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      ca-certificates cmake make g++ clang libomp-dev libclang-rt-18-dev \
      openmpi-bin libopenmpi-dev \
      git python3 python3-pytest python3-matplotlib python3-scipy \
      openssh-client openssh-server iproute2 procps \
 && rm -rf /var/lib/apt/lists/*

# Open MPI rechaza ejecutarse como root salvo que se confirme explícitamente.
ENV OMPI_ALLOW_RUN_AS_ROOT=1 \
    OMPI_ALLOW_RUN_AS_ROOT_CONFIRM=1 \
    OMPI_MCA_btl_vader_single_copy_mechanism=none

# El repositorio llega desde Windows con CRLF (core.autocrlf=true). Con "input",
# git en Linux normaliza a LF al comparar y no marca el árbol como modificado
# (medir_openmp.py añade "+cambios_sin_commit" si `git status --porcelain` no está vacío).
# safe.directory: el montaje tiene otro propietario que root.
RUN git config --system core.autocrlf input \
 && git config --system --add safe.directory '*'

# SSH sin contraseña entre contenedores de la misma imagen (solo para la red interna de compose).
RUN mkdir -p /run/sshd /root/.ssh \
 && ssh-keygen -q -t ed25519 -N '' -f /root/.ssh/id_ed25519 \
 && cp /root/.ssh/id_ed25519.pub /root/.ssh/authorized_keys \
 && printf 'Host *\n  StrictHostKeyChecking no\n  UserKnownHostsFile /dev/null\n  LogLevel ERROR\n' > /root/.ssh/config \
 && chmod 700 /root/.ssh && chmod 600 /root/.ssh/*

WORKDIR /work
CMD ["bash"]
