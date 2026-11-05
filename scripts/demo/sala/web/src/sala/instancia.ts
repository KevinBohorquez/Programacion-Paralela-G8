// The single store of the app (one EventSource) and the hook that reads it through selectors.
import { useSyncExternalStore } from "react";
import type { EstadoSala } from "../dominio/estado";
import type { EventoEstado } from "../dominio/eventos";
import { crearAlmacen, fuenteSse, type Fuente } from "./almacen";
import { MOCK, llamar } from "./api";

const fuenteMock: Fuente = {
  conectar(emitir, conexion) {
    let vivo = true;
    let desconectar = () => {};
    void import("../mock/reproductor").then((m) => {
      if (vivo) desconectar = m.fuenteMock.conectar(emitir, conexion);
    });
    return () => {
      vivo = false;
      desconectar();
    };
  },
};

export const almacen = crearAlmacen(MOCK ? fuenteMock : fuenteSse());

let arrancado = false;

/** Opens the stream once and, for a late join, asks GET /api/estado for the current mode. */
export function arrancar(): void {
  if (arrancado) return;
  arrancado = true;
  almacen.iniciar();
  void llamar<Omit<EventoEstado, "t">>("GET", "/api/estado")
    .then((r) => {
      if (r.status === 200 && r.data) almacen.recibir({ ...r.data, t: "estado" });
    })
    .catch(() => {
      /* the stream's own `estado` event covers it */
    });
}

export function useSala<T>(selector: (s: EstadoSala) => T): T {
  return useSyncExternalStore(
    almacen.suscribir,
    () => selector(almacen.obtener()),
    () => selector(almacen.obtener()),
  );
}
