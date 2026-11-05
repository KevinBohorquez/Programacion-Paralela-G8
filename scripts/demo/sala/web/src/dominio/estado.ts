// Pure reducer: SSE events -> control-room state. Immutable, so selectors can compare by reference
// and a burst of cpu samples never touches the `corridas` array the race lanes read.
import type { Bloque } from "../viz/tipos";
import type { Evento, EventoFin, EventoInicio } from "./eventos";

export type Conexion = "conectando" | "abierta" | "caida";

export interface Corrida {
  id: string;
  backend: EventoInicio["backend"];
  procesos: number;
  hilos: number;
  n: number;
  afinidad: string;
  comando: string;
  /** Server time of `inicio` and of the latest event of this run. */
  ts0: number;
  ts: number;
  /** Progress of each rank (E1 and hybrid); single-emitter runs use `hecho`/`total`. */
  rangos: Record<number, { hecho: number; total: number }>;
  hecho: number;
  total: number;
  tasa: number | null;
  estimado: boolean;
  bloques: Bloque[];
  asignado: number;
  fin: EventoFin | null;
  error: string | null;
}

export interface EstadoSala {
  conexion: Conexion;
  modo: "vivo" | "replay";
  grabando: boolean;
  ocupado: boolean;
  cpu: number[];
  /** Latest server timestamp seen, used as "now" by running lanes. */
  ahora: number;
  corridas: Corrida[];
}

export const estadoInicial: EstadoSala = {
  conexion: "conectando",
  modo: "vivo",
  grabando: false,
  ocupado: false,
  cpu: [],
  ahora: 0,
  corridas: [],
};

/** Lanes are keyed by backend + affinity, so "híbrido con error" and "corregido" are separate lanes. */
export function claveCarril(c: { backend: string; afinidad: string }): string {
  return c.backend === "hibrido" ? `hibrido:${c.afinidad}` : c.backend;
}

/** Race ids are `c<n>-<backend>`; standalone hybrids are `h<n>-<afinidad>`. */
export function carreraDe(id: string): string | null {
  const m = /^(c\d+)-/.exec(id);
  return m ? m[1] : null;
}

export const terminada = (c: Corrida) => c.fin !== null || c.error !== null;

/**
 * Where a new run goes. A new race replaces the previous lanes; a standalone hybrid only replaces
 * its own finished lane (same affinity), so "con error" and "corregido" sit next to the race.
 */
export function insertarCorrida(corridas: Corrida[], nueva: Corrida): Corrida[] {
  const sinMisma = corridas.filter((c) => c.id !== nueva.id);
  const enCurso = sinMisma.some((c) => !terminada(c));
  const carrera = carreraDe(nueva.id);
  const clave = claveCarril(nueva);
  let base = sinMisma;
  if (!enCurso) {
    if (carrera !== null) {
      const mismaCarrera = sinMisma.some((c) => carreraDe(c.id) === carrera);
      if (!mismaCarrera && sinMisma.length) base = [];
    } else if (nueva.backend === "hibrido") {
      base = sinMisma.filter((c) => claveCarril(c) !== clave);
    } else if (sinMisma.some((c) => claveCarril(c) === clave)) {
      base = [];
    }
  }
  return [...base, nueva];
}

function nuevaCorrida(e: EventoInicio, ts: number): Corrida {
  return {
    id: e.id,
    backend: e.backend,
    procesos: e.procesos,
    hilos: e.hilos,
    n: e.n,
    afinidad: e.afinidad,
    comando: e.comando ?? "",
    ts0: ts,
    ts,
    rangos: {},
    hecho: 0,
    total: e.n,
    tasa: null,
    estimado: false,
    bloques: [],
    asignado: 0,
    fin: null,
    error: null,
  };
}

function actualizar(s: EstadoSala, id: string | null, f: (c: Corrida) => Corrida): EstadoSala {
  const i = id === null ? -1 : s.corridas.findIndex((c) => c.id === id);
  if (i < 0) return s;
  const corridas = s.corridas.slice();
  corridas[i] = f(corridas[i]);
  return { ...s, corridas };
}

export function reducir(s: EstadoSala, e: Evento): EstadoSala {
  const ts = typeof e.ts === "number" ? e.ts : s.ahora;
  const base = ts > s.ahora ? { ...s, ahora: ts } : s;
  switch (e.t) {
    case "cpu":
      return { ...base, cpu: e.nucleos };
    case "estado":
      return { ...base, modo: e.modo, grabando: !!e.grabando, ocupado: !!e.ocupado };
    case "inicio":
      return { ...base, corridas: insertarCorrida(base.corridas, nuevaCorrida(e, ts)) };
    case "avance":
      return actualizar(base, e.id, (c) => ({
        ...c,
        ts,
        ...(e.rango === null || e.rango === undefined
          ? { hecho: e.hecho, total: e.total }
          : { rangos: { ...c.rangos, [e.rango]: { hecho: e.hecho, total: e.total } } }),
        tasa: typeof e.escenarios_s === "number" ? e.escenarios_s : c.tasa,
        estimado: e.estimado === true,
      }));
    case "bloque":
      return actualizar(base, e.id, (c) => ({
        ...c,
        ts,
        bloques: [...c.bloques, { rango: e.rango, i0: e.i0, i1: e.i1, ts }],
        asignado: c.asignado + Math.max(0, e.i1 - e.i0),
      }));
    case "fin":
      return actualizar(base, e.id, (c) => ({ ...c, ts, fin: e }));
    case "error":
      return actualizar(base, e.id, (c) => ({ ...c, ts, error: e.mensaje }));
    default:
      return s;
  }
}

export function reducirLote(s: EstadoSala, eventos: readonly Evento[]): EstadoSala {
  let r = s;
  for (const e of eventos) r = reducir(r, e);
  return r;
}

// ------------------------------------------------------------------ derived values (used in render)

export function progreso(c: Corrida): number {
  if (c.fin) return 1;
  const rangos = Object.values(c.rangos);
  if (rangos.length) {
    const hecho = rangos.reduce((a, r) => a + r.hecho, 0);
    return Math.min(1, hecho / Math.max(c.n, 1));
  }
  if (c.hecho && c.total) return Math.min(1, c.hecho / c.total);
  if (c.asignado && c.n) return Math.min(1, c.asignado / c.n);
  return 0;
}

export function tasa(c: Corrida): number | null {
  if (c.fin) return c.fin.segundos > 0 ? c.fin.n / c.fin.segundos : null;
  const rangos = Object.values(c.rangos);
  if (rangos.length && c.ts > c.ts0) return rangos.reduce((a, r) => a + r.hecho, 0) / (c.ts - c.ts0);
  if (c.tasa !== null) return c.tasa;
  if (c.asignado && c.ts > c.ts0) return c.asignado / (c.ts - c.ts0);
  return null;
}

export function nombreCorrida(c: { backend: string; afinidad: string }): string {
  if (c.backend === "hibrido" && c.afinidad === "close") return "Híbrido con error";
  if (c.backend === "hibrido" && c.afinidad === "false") return "Híbrido corregido";
  const nombres: Record<string, string> = {
    serial: "Serial",
    openmp: "OpenMP",
    mpi_estatico: "MPI E1 estático",
    mpi_dinamico: "MPI E2 dinámico",
    hibrido: "Híbrido",
  };
  return nombres[c.backend] ?? c.backend;
}

/**
 * Speedup reported by the server, or, for a standalone run (no serial in its own race), the ratio
 * against a finished serial lane with the same N. `derivado` tells the UI to say so.
 */
export function speedupDe(c: Corrida, corridas: readonly Corrida[]): { valor: number | null; derivado: boolean } {
  if (!c.fin) return { valor: null, derivado: false };
  if (typeof c.fin.speedup === "number") return { valor: c.fin.speedup, derivado: false };
  const serial = corridas.find((o) => o.backend === "serial" && o.fin && o.fin.n === c.fin!.n);
  if (!serial || c.fin.segundos <= 0) return { valor: null, derivado: false };
  return { valor: serial.fin!.segundos / c.fin.segundos, derivado: true };
}

export type Veredicto =
  | { tipo: "espera"; corridas: number }
  | { tipo: "identicos"; corridas: number }
  | { tipo: "distintos"; corridas: number; distintas: string[] };

/** V1: every finished run must report the same k, N and hist512 fingerprint. */
export function veredictoIdentidad(corridas: readonly Corrida[]): Veredicto {
  const fin = corridas.filter((c) => c.fin);
  if (fin.length < 2) return { tipo: "espera", corridas: fin.length };
  const ref = fin[0].fin!;
  const distintas = fin
    .filter((c) => c.fin!.k !== ref.k || c.fin!.huella !== ref.huella || c.fin!.n !== ref.n)
    .map((c) => c.id);
  return distintas.length
    ? { tipo: "distintos", corridas: fin.length, distintas }
    : { tipo: "identicos", corridas: fin.length };
}
