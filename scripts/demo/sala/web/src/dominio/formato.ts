// Spanish number formatting for the room (decimal comma, thin grouping).
const compacto = new Intl.NumberFormat("es", { notation: "compact", maximumFractionDigits: 1 });
const entero = new Intl.NumberFormat("es", { maximumFractionDigits: 0, useGrouping: true });
const dos = new Intl.NumberFormat("es", { maximumFractionDigits: 2, minimumFractionDigits: 2 });

export const fmtCompacto = (x: number | null | undefined) => (x == null || !isFinite(x) ? "—" : compacto.format(x));
export const fmtEntero = (x: number | null | undefined) => (x == null || !isFinite(x) ? "—" : entero.format(x));
export const fmtSegundos = (x: number | null | undefined) => (x == null || !isFinite(x) ? "—" : `${dos.format(x)} s`);
export const fmtSpeedup = (x: number | null | undefined) => (x == null || !isFinite(x) ? "—" : `${dos.format(x)}×`);

/** Probability as a percentage with 3 significant digits (0,0123 → "1,23 %"). */
export function fmtP(p: number | null | undefined): string {
  if (p == null || !isFinite(p)) return "—";
  if (p === 0) return "0 %";
  const pct = p * 100;
  const digitos = pct >= 10 ? 1 : pct >= 1 ? 2 : Math.min(6, 2 - Math.floor(Math.log10(pct)));
  return `${pct.toLocaleString("es", { maximumFractionDigits: digitos, minimumFractionDigits: Math.min(digitos, 2) })} %`;
}

export const fmtDecimal = (x: number, max = 2) => x.toLocaleString("es", { maximumFractionDigits: max });
