// Pure layout of the E2 dynamic-scheduling timeline: block spans in time, per-rank totals and N coverage.
import type { Bloque } from "./tipos";

export interface BloqueDispuesto {
  readonly rango: number;
  /** Start and estimated end, in seconds relative to t0. */
  readonly inicio: number;
  readonly fin: number;
  readonly i0: number;
  readonly i1: number;
  /** Alternating shade (0/1) within its rank, so neighbouring blocks stay distinct. */
  readonly sombra: 0 | 1;
}

export interface ResumenRango {
  readonly bloques: number;
  readonly escenarios: number;
}

export interface Tramo {
  readonly i0: number;
  readonly i1: number;
}

export interface DisposicionBloques {
  readonly bloques: BloqueDispuesto[];
  readonly porRango: ResumenRango[];
  /** Merged [i0, i1) intervals assigned so far, clamped to [0, total). */
  readonly cubierto: Tramo[];
  /** Fraction of [0, total) assigned, 0–1. */
  readonly cobertura: number;
}

/**
 * Lays the blocks out on a time axis. A block starts at its `ts`; its width is estimated up to the next
 * block assigned to the same rank, or up to `t1` for that rank's latest block. Ranks outside
 * [0, rangos) are ignored.
 */
export function disponerBloques(
  bloques: readonly Bloque[],
  rangos: number,
  total: number,
  t0: number,
  t1: number,
): DisposicionBloques {
  const filas: Bloque[][] = Array.from({ length: Math.max(0, rangos) }, () => []);
  for (const b of bloques) {
    if (Number.isInteger(b.rango) && b.rango >= 0 && b.rango < rangos) filas[b.rango]!.push(b);
  }
  const dispuestos: BloqueDispuesto[] = [];
  const porRango: ResumenRango[] = [];
  for (const fila of filas) {
    fila.sort((a, b) => a.ts - b.ts);
    let escenarios = 0;
    for (let k = 0; k < fila.length; k += 1) {
      const b = fila[k]!;
      const siguiente = fila[k + 1];
      const inicio = b.ts - t0;
      const fin = Math.max(inicio, (siguiente ? siguiente.ts : Math.max(t1, b.ts)) - t0);
      escenarios += Math.max(0, b.i1 - b.i0);
      dispuestos.push({ rango: b.rango, inicio, fin, i0: b.i0, i1: b.i1, sombra: k % 2 === 0 ? 0 : 1 });
    }
    porRango.push({ bloques: fila.length, escenarios });
  }
  const cubierto = fusionarTramos(bloques, total);
  let suma = 0;
  for (const t of cubierto) suma += t.i1 - t.i0;
  return { bloques: dispuestos, porRango, cubierto, cobertura: total > 0 ? Math.min(1, suma / total) : 0 };
}

/** Union of the blocks' [i0, i1) ranges clamped to [0, total), sorted and merged. */
export function fusionarTramos(bloques: readonly Tramo[], total: number): Tramo[] {
  const tramos = bloques
    .map((b) => ({ i0: Math.max(0, b.i0), i1: Math.min(total, b.i1) }))
    .filter((t) => t.i1 > t.i0)
    .sort((a, b) => a.i0 - b.i0);
  const fusion: Tramo[] = [];
  for (const t of tramos) {
    const ultimo = fusion[fusion.length - 1];
    if (ultimo && t.i0 <= ultimo.i1) fusion[fusion.length - 1] = { i0: ultimo.i0, i1: Math.max(ultimo.i1, t.i1) };
    else fusion.push(t);
  }
  return fusion;
}
