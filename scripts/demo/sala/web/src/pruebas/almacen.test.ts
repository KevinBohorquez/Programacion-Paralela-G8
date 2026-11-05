import { describe, expect, it, vi } from "vitest";
import { crearAlmacen, type Fuente } from "../sala/almacen";
import type { Conexion } from "../dominio/estado";
import type { Evento } from "../dominio/eventos";

function preparar() {
  let emitir: (e: Evento) => void = () => {};
  let conexion: (c: Conexion) => void = () => {};
  let tic: () => void = () => {};
  const desconectar = vi.fn();
  const fuente: Fuente = {
    conectar(e, c) {
      emitir = e;
      conexion = c;
      return desconectar;
    },
  };
  const almacen = crearAlmacen(fuente, {
    programar: (f) => {
      tic = f;
      return () => {};
    },
  });
  const parar = almacen.iniciar();
  return { almacen, emitir: (e: Evento) => emitir(e), conexion: (c: Conexion) => conexion(c), tic: () => tic(), parar, desconectar };
}

describe("crearAlmacen", () => {
  it("buffers events and notifies once per flush", () => {
    const { almacen, emitir, tic } = preparar();
    const oyente = vi.fn();
    almacen.suscribir(oyente);
    for (let i = 0; i < 5; i++) emitir({ t: "cpu", nucleos: [i / 10], ts: i });
    emitir({ t: "estado", modo: "vivo", grabando: false, ocupado: true, ts: 5 });
    expect(oyente).not.toHaveBeenCalled();
    expect(almacen.obtener().cpu).toEqual([]);
    tic();
    expect(oyente).toHaveBeenCalledTimes(1);
    expect(almacen.obtener()).toMatchObject({ cpu: [0.4], ocupado: true, ahora: 5 });
    tic();
    expect(oyente).toHaveBeenCalledTimes(1);
  });

  it("applies the connection state in the same batch", () => {
    const { almacen, conexion, tic } = preparar();
    expect(almacen.obtener().conexion).toBe("conectando");
    conexion("abierta");
    tic();
    expect(almacen.obtener().conexion).toBe("abierta");
  });

  it("reports error events after the batch is applied", () => {
    const { almacen, emitir, tic } = preparar();
    const errores = vi.fn();
    almacen.alError((e) => errores(e.mensaje, almacen.obtener().corridas[0]?.error));
    emitir({ t: "inicio", id: "c1-serial", backend: "serial", procesos: 1, hilos: 1, n: 10, afinidad: "-", ts: 0 });
    emitir({ t: "error", id: "c1-serial", mensaje: "falló", ts: 1 });
    tic();
    expect(errores).toHaveBeenCalledWith("falló", "falló");
  });

  it("disconnects the source when stopped and opens it only once", () => {
    const { almacen, parar, desconectar } = preparar();
    expect(almacen.iniciar()).toBe(parar);
    parar();
    expect(desconectar).toHaveBeenCalledTimes(1);
  });
});
