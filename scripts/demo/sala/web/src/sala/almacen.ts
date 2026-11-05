// External store for the whole app: one event source, a buffer, and a ~8 Hz flush that applies
// every pending event in a single batch. React reads it through useSyncExternalStore + selectors.
import { estadoInicial, reducirLote, type Conexion, type EstadoSala } from "../dominio/estado";
import type { Evento, EventoError } from "../dominio/eventos";

/** Where events come from: the real EventSource or the dev mock. Returns a disconnect function. */
export interface Fuente {
  conectar(emitir: (e: Evento) => void, conexion: (c: Conexion) => void): () => void;
}

export interface OpcionesAlmacen {
  /** Flush period in ms (default 125, i.e. 8 Hz). */
  periodo?: number;
  /** Timer injection for tests. */
  programar?: (f: () => void, ms: number) => () => void;
}

export interface Almacen {
  obtener(): EstadoSala;
  suscribir(oyente: () => void): () => void;
  /** Called once per `error` event, after the batch that carries it is applied. */
  alError(oyente: (e: EventoError) => void): () => void;
  recibir(e: Evento): void;
  conexion(c: Conexion): void;
  vaciar(): void;
  iniciar(): () => void;
}

const intervalo = (f: () => void, ms: number) => {
  const h = setInterval(f, ms);
  return () => clearInterval(h);
};

export function crearAlmacen(fuente: Fuente, opciones: OpcionesAlmacen = {}): Almacen {
  const periodo = opciones.periodo ?? 125;
  const programar = opciones.programar ?? intervalo;
  let estado = estadoInicial;
  let pendientes: Evento[] = [];
  let conexionPendiente: Conexion | null = null;
  const oyentes = new Set<() => void>();
  const oyentesError = new Set<(e: EventoError) => void>();
  let activo: (() => void) | null = null;

  const almacen: Almacen = {
    obtener: () => estado,
    suscribir(oyente) {
      oyentes.add(oyente);
      return () => oyentes.delete(oyente);
    },
    alError(oyente) {
      oyentesError.add(oyente);
      return () => oyentesError.delete(oyente);
    },
    recibir(e) {
      pendientes.push(e);
    },
    conexion(c) {
      conexionPendiente = c;
    },
    vaciar() {
      if (!pendientes.length && conexionPendiente === null) return;
      const lote = pendientes;
      pendientes = [];
      let siguiente = reducirLote(estado, lote);
      if (conexionPendiente !== null && conexionPendiente !== siguiente.conexion) {
        siguiente = { ...siguiente, conexion: conexionPendiente };
      }
      conexionPendiente = null;
      if (siguiente !== estado) {
        estado = siguiente;
        oyentes.forEach((o) => o());
      }
      for (const e of lote) if (e.t === "error") oyentesError.forEach((o) => o(e));
    },
    iniciar() {
      if (activo) return activo;
      const desconectar = fuente.conectar(almacen.recibir, almacen.conexion);
      const parar = programar(almacen.vaciar, periodo);
      activo = () => {
        desconectar();
        parar();
        activo = null;
      };
      return activo;
    },
  };
  return almacen;
}

/** Real source: GET /api/stream with exponential back-off when the browser gives up retrying. */
export function fuenteSse(url = "/api/stream"): Fuente {
  return {
    conectar(emitir, conexion) {
      let es: EventSource | null = null;
      let espera = 1000;
      let temporizador = 0;
      let cerrado = false;
      const abrir = () => {
        es = new EventSource(url);
        es.onopen = () => {
          espera = 1000;
          conexion("abierta");
        };
        es.onmessage = (ev) => {
          try {
            emitir(JSON.parse(ev.data) as Evento);
          } catch {
            /* ignore malformed lines */
          }
        };
        es.onerror = () => {
          conexion("caida");
          if (es && es.readyState === EventSource.CLOSED && !cerrado) {
            temporizador = window.setTimeout(abrir, espera);
            espera = Math.min(espera * 2, 10_000);
          }
        };
      };
      abrir();
      return () => {
        cerrado = true;
        clearTimeout(temporizador);
        es?.close();
      };
    },
  };
}
