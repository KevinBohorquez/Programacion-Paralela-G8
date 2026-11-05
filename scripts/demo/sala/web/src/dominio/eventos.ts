// SSE events of docs/contrato-sala-control.md §2, with the server's accepted deviations
// (fin carries backend and segundos_pared, avance.estimado is optional, replay adds replay/ts_original).
import type { Backend } from "../viz/tipos";

interface Base {
  ts?: number;
  replay?: boolean;
  ts_original?: number;
}

export interface EventoCpu extends Base {
  t: "cpu";
  nucleos: number[];
}

export interface EventoEstado extends Base {
  t: "estado";
  modo: "vivo" | "replay";
  grabando: boolean;
  ocupado: boolean;
}

export interface EventoInicio extends Base {
  t: "inicio";
  id: string;
  backend: Backend;
  procesos: number;
  hilos: number;
  n: number;
  afinidad: string;
  comando?: string;
}

export interface EventoAvance extends Base {
  t: "avance";
  id: string;
  hecho: number;
  total: number;
  rango: number | null;
  escenarios_s?: number;
  estimado?: boolean;
}

export interface EventoBloque extends Base {
  t: "bloque";
  id: string;
  rango: number;
  i0: number;
  i1: number;
}

export interface EventoFin extends Base {
  t: "fin";
  id: string;
  backend?: Backend;
  segundos: number;
  segundos_pared?: number;
  k: number;
  n: number;
  p: number;
  wilson: [number, number];
  huella: string;
  trabajo_rangos: number[] | null;
  speedup: number | null;
}

export interface EventoError extends Base {
  t: "error";
  id: string | null;
  mensaje: string;
}

export type Evento =
  | EventoCpu
  | EventoEstado
  | EventoInicio
  | EventoAvance
  | EventoBloque
  | EventoFin
  | EventoError;

export const NOMBRES: Record<Backend, string> = {
  serial: "Serial",
  openmp: "OpenMP",
  mpi_estatico: "MPI E1 estático",
  mpi_dinamico: "MPI E2 dinámico",
  hibrido: "Híbrido MPI+OpenMP",
};

export const BACKENDS: Backend[] = ["serial", "openmp", "mpi_estatico", "mpi_dinamico", "hibrido"];
