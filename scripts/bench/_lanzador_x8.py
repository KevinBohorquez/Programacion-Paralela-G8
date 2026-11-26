#!/usr/bin/env python3
"""Metadatos observados en cada rango, antes de MPI_Init y del tiempo del simulador."""
import hashlib
import json
import os
from pathlib import Path
import socket
import sys

import _comun_bench as cb


def sha256(ruta):
    h = hashlib.sha256()
    with Path(ruta).open("rb") as f:
        for bloque in iter(lambda: f.read(1024 * 1024), b""):
            h.update(bloque)
    return h.hexdigest()


def main():
    argv = sys.argv[1:]
    rango = int(os.environ["OMPI_COMM_WORLD_RANK"])
    config = argv[argv.index("--config") + 1]
    cpu, fisicos, logicos = cb.info_cpu()
    datos = dict(rango=rango, host=socket.gethostname(), cpu=cpu,
                 nucleos_fisicos=fisicos, nucleos_logicos=logicos, ram_gb=cb.ram_gb(), gpu=cb.info_gpu(),
                 binario_sha256=sha256(argv[0]), config_sha256=sha256(config))
    print(f"[x8-host] rango={rango} host={datos['host']}", file=sys.stderr, flush=True)
    print("[x8-hardware] " + json.dumps(datos, ensure_ascii=True), file=sys.stderr, flush=True)
    os.execv(argv[0], argv)


if __name__ == "__main__":
    main()
