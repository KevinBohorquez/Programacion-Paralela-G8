// Illustrative sample data for the viz harness only. These numbers are synthetic, not simulator output.
import type { Bloque, BarraSpeedup, PuntoConvergencia } from "../tipos";

/** Deterministic pseudo-random generator (mulberry32) so screenshots are reproducible. */
export function aleatorio(semilla: number): () => number {
  let a = semilla >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Wilson score interval for k successes in n trials at 95 %. */
export function wilson(p: number, n: number): [number, number] {
  const z = 1.96;
  const z2 = z * z;
  const centro = (p + z2 / (2 * n)) / (1 + z2 / n);
  const media = (z * Math.sqrt((p * (1 - p)) / n + z2 / (4 * n * n))) / (1 + z2 / n);
  return [Math.max(0, centro - media), Math.min(1, centro + media)];
}

/** 24 cores whose load drifts with time `t` (s). */
export function nucleosMuestra(t: number): number[] {
  return Array.from({ length: 24 }, (_, i) => {
    const base = i < 20 ? 0.86 : 0.35;
    const onda = 0.12 * Math.sin(t * 1.3 + i * 0.9) + 0.05 * Math.sin(t * 3.1 + i * 2.3);
    return Math.max(0.02, Math.min(1, base + onda - (i % 7 === 3 ? 0.4 : 0)));
  });
}

/** Exceedance curve with a deliberately small sample (n = 600) so the Wilson band is visible. */
export function curvaMuestra() {
  const u: number[] = [];
  const p: number[] = [];
  const lo: number[] = [];
  const hi: number[] = [];
  for (let x = 0; x <= 200; x += 5) {
    const v = Math.exp(-((x / 70) ** 1.4));
    const [a, b] = wilson(v, 600);
    u.push(x);
    p.push(v);
    lo.push(a);
    hi.push(b);
  }
  return { u, p, lo, hi };
}

export const barrasMuestra: BarraSpeedup[] = [
  { id: "s", etiqueta: "Serial", backend: "serial", speedup: 1, segundos: 62.4, enCurso: false },
  { id: "o", etiqueta: "OpenMP · 24 hilos", backend: "openmp", speedup: 14.6, segundos: 4.27, enCurso: false },
  { id: "e", etiqueta: "MPI estático · 24", backend: "mpi_estatico", speedup: 16.9, segundos: 3.69, enCurso: false },
  { id: "d", etiqueta: "MPI dinámico · 24", backend: "mpi_dinamico", speedup: 19.8, segundos: 3.15, enCurso: false },
  { id: "h", etiqueta: "Híbrido 4×6", backend: "hibrido", speedup: null, segundos: null, enCurso: true },
];

/**
 * Master–worker schedule: 320 blocks of N/320 handed to the first free worker; workers differ in speed.
 * Returns every block with its assignment time.
 */
export function bloquesMuestra(rangos: number, total: number, cantidad: number): Bloque[] {
  const azar = aleatorio(7);
  const tamano = Math.floor(total / cantidad);
  const libre = Array.from({ length: rangos }, () => 0);
  const velocidad = Array.from({ length: rangos }, (_, r) => 0.85 + 0.3 * ((r * 37) % 11) / 10);
  const bloques: Bloque[] = [];
  for (let k = 0; k < cantidad; k += 1) {
    let r = 1;
    for (let j = 2; j < rangos; j += 1) if (libre[j]! < libre[r]!) r = j;
    const ts = libre[r]!;
    bloques.push({ rango: r, i0: k * tamano, i1: (k + 1) * tamano, ts: 100 + ts });
    libre[r] = ts + (0.18 / velocidad[r]!) * (0.8 + 0.4 * azar());
  }
  return bloques;
}

export function convergenciaMuestra(): PuntoConvergencia[] {
  const azar = aleatorio(3);
  const verdadero = 0.1843;
  const ns = [1e3, 3e3, 1e4, 3e4, 1e5, 3e5, 1e6, 3e6, 1e7];
  return ns.map((n) => {
    const sigma = Math.sqrt((verdadero * (1 - verdadero)) / n);
    const p = verdadero + sigma * (azar() * 2 - 1) * 1.4;
    const [lo, hi] = wilson(p, n);
    return { n, p, lo, hi };
  });
}
