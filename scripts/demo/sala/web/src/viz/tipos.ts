// Props contract between the app (W-UI) and the charts (W-VIZ). Colors come from CSS variables, never literals.
export type Backend = "serial" | "openmp" | "mpi_estatico" | "mpi_dinamico" | "hibrido";

/** CSS variable holding each backend's color, defined in the design tokens. */
export const colorBackend: Record<Backend, string> = {
  serial: "var(--backend-serial)",
  openmp: "var(--backend-openmp)",
  mpi_estatico: "var(--backend-mpi-estatico)",
  mpi_dinamico: "var(--backend-mpi-dinamico)",
  hibrido: "var(--backend-hibrido)",
};

export interface MapaNucleosProps {
  /** Utilisation 0–1 per logical CPU, in /proc/stat order. */
  nucleos: number[];
  /** Optional caption, e.g. the running backend. */
  etiqueta?: string;
}

export interface CurvaRiesgoProps {
  u: number[];
  p: number[];
  lo: number[];
  hi: number[];
  /** Selected threshold U, drawn as a marker. */
  umbral: number;
  alto?: number;
}

export interface BarraSpeedup {
  id: string;
  etiqueta: string;
  backend: Backend;
  speedup: number | null;
  segundos: number | null;
  /** True while the run is in progress. */
  enCurso: boolean;
}

export interface GraficoSpeedupProps {
  barras: BarraSpeedup[];
  /** Ideal speedup (cores used), drawn as a reference line. */
  ideal: number;
}

export interface Bloque {
  rango: number;
  i0: number;
  i1: number;
  /** Server timestamp (s) when the master assigned the block. */
  ts: number;
}

export interface LineaBloquesProps {
  /** Number of MPI ranks, including the master (rank 0, which never simulates). */
  rangos: number;
  bloques: Bloque[];
  /** Total scenarios N. */
  total: number;
  /** Time window [t0, t1] in server seconds; t1 grows while running. */
  t0: number;
  t1: number;
}

export interface PuntoConvergencia {
  n: number;
  p: number;
  lo: number;
  hi: number;
}

export interface GraficoConvergenciaProps {
  puntos: PuntoConvergencia[];
}
