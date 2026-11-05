import { describe, expect, it } from "vitest";
import { disponerBloques, fusionarTramos } from "./bloques";
import { brilloCalor, dimensionesRejilla, mediaUtilizacion, nivelCalor, pesosCalor, rutasSparkline } from "./calor";
import { decimalesPaso, escalaLineal, escalaLog, extremos, idSeguro, interpolar, redondear, rutaPolilinea } from "./escalas";
import {
  ESPACIO_FINO,
  formatearCompacto,
  formatearNumero,
  formatearPorcentaje,
  formatearSegundos,
  formatearSpeedup,
  potenciaDiez,
} from "./formato";

const F = ESPACIO_FINO;

describe("escalaLineal", () => {
  it("rounds the top up to a nice step from zero", () => {
    expect(escalaLineal(0, 24)).toEqual({ min: 0, max: 25, paso: 5, ticks: [0, 5, 10, 15, 20, 25] });
  });
  it("auto-zooms around non-zero data", () => {
    const e = escalaLineal(0.172, 0.197, 5);
    expect(e.min).toBeCloseTo(0.17);
    expect(e.max).toBeCloseTo(0.2);
    expect(e.ticks.length).toBeLessThanOrEqual(6);
  });
  it("widens a flat range", () => {
    const e = escalaLineal(3, 3);
    expect(e.min).toBeLessThan(3);
    expect(e.max).toBeGreaterThan(3);
  });
  it("handles zero span at zero", () => {
    expect(escalaLineal(0, 0).max).toBe(1);
  });
});

describe("helpers de escala", () => {
  it("counts decimals of a step", () => {
    expect(decimalesPaso(0.25)).toBe(2);
    expect(decimalesPaso(5)).toBe(0);
    expect(decimalesPaso(0.005)).toBe(3);
  });
  it("covers decades with a minimum 1e3..1e7", () => {
    expect(escalaLog(5000, 2e6).decadas).toEqual([3, 4, 5, 6, 7]);
    expect(escalaLog(200, 3e7)).toMatchObject({ eMin: 2, eMax: 8 });
  });
  it("interpolates and clamps", () => {
    expect(interpolar([0, 10], [1, 0], 5)).toBeCloseTo(0.5);
    expect(interpolar([0, 10], [1, 0], 20)).toBe(0);
    expect(interpolar([], [], 1)).toBeNull();
  });
  it("rounds coordinates without negative zero", () => {
    expect(redondear(1.2345, 2)).toBe(1.23);
    expect(Object.is(redondear(-0.01), 0)).toBe(true);
    expect(rutaPolilinea([[0.123, 1], [2, 3.456]])).toBe("M0.1 1L2 3.5");
  });
  it("finds extremes ignoring NaN", () => {
    expect(extremos([3, Number.NaN, 1, 7])).toEqual([1, 7]);
    expect(extremos([])).toBeNull();
  });
  it("makes url-safe ids", () => {
    expect(idSeguro("«r1»")).toBe("vr1");
  });
});

describe("formato es", () => {
  it("uses a decimal comma and thin-space thousands", () => {
    expect(formatearNumero(1234567.891, 2)).toBe(`1${F}234${F}567,89`);
    expect(formatearNumero(0.1843, 4)).toBe("0,1843");
    expect(formatearNumero(-2.5, 1)).toBe("−2,5");
    expect(formatearNumero(-0.001, 1)).toBe("0,0");
  });
  it("formats percent, speedup, seconds and compact counts", () => {
    expect(formatearPorcentaje(0.724)).toBe(`72${F}%`);
    expect(formatearSpeedup(14.63)).toBe("14,6×");
    expect(formatearSegundos(3.421)).toBe(`3,42${F}s`);
    expect(formatearSegundos(128.4)).toBe(`128${F}s`);
    expect(formatearCompacto(1_250_000)).toBe(`1,25${F}M`);
    expect(formatearCompacto(31_250)).toBe(`31,3${F}k`);
    expect(formatearCompacto(950)).toBe("950");
  });
  it("writes powers of ten with superscripts", () => {
    expect(potenciaDiez(7)).toBe("10⁷");
    expect(potenciaDiez(-3)).toBe("10⁻³");
  });
});

describe("calor", () => {
  it("buckets utilisation onto five stops", () => {
    expect(nivelCalor(0)).toBe(0);
    expect(nivelCalor(0.49)).toBe(2);
    expect(nivelCalor(1.3)).toBe(4);
  });
  it("stacks opaque layers up to the nearest stop", () => {
    expect(pesosCalor(0)).toEqual([1, 0, 0, 0, 0]);
    expect(pesosCalor(0.5)).toEqual([1, 1, 1, 0, 0]);
    expect(pesosCalor(0.7)).toEqual([1, 1, 1, 1, 0]);
    expect(pesosCalor(1)).toEqual([1, 1, 1, 1, 1]);
  });
  it("glows only above 75 %", () => {
    expect(brilloCalor(0.7)).toBe(0);
    expect(brilloCalor(0.875)).toBe(0.5);
  });
  it("shapes the grid", () => {
    expect(dimensionesRejilla(24)).toEqual({ columnas: 6, filas: 4 });
    expect(dimensionesRejilla(16)).toEqual({ columnas: 4, filas: 4 });
    expect(dimensionesRejilla(8)).toEqual({ columnas: 4, filas: 2 });
    expect(dimensionesRejilla(0)).toEqual({ columnas: 1, filas: 1 });
  });
  it("averages clamped utilisation", () => {
    expect(mediaUtilizacion([0.5, 1.5])).toBe(0.75);
    expect(mediaUtilizacion([])).toBe(0);
  });
  it("anchors the sparkline to the right edge", () => {
    const { linea, area } = rutasSparkline([0, 1], 100, 10, 11);
    expect(linea).toBe("M90 10L100 0");
    expect(area).toBe("M90 10L100 0L100 10L90 10Z");
    expect(rutasSparkline([], 100, 10, 11).linea).toBe("");
  });
});

describe("disponerBloques", () => {
  const bloques = [
    { rango: 1, i0: 0, i1: 100, ts: 10 },
    { rango: 2, i0: 100, i1: 200, ts: 10.5 },
    { rango: 1, i0: 200, i1: 300, ts: 12 },
    { rango: 9, i0: 300, i1: 400, ts: 13 },
  ];
  it("estimates widths up to the next block of the rank, or t1", () => {
    const d = disponerBloques(bloques, 3, 1000, 10, 15);
    const r1 = d.bloques.filter((b) => b.rango === 1);
    expect(r1.map((b) => [b.inicio, b.fin, b.sombra])).toEqual([[0, 2, 0], [2, 5, 1]]);
    expect(d.bloques.find((b) => b.rango === 2)).toMatchObject({ inicio: 0.5, fin: 5 });
  });
  it("totals blocks and scenarios per rank, ignoring unknown ranks", () => {
    const d = disponerBloques(bloques, 3, 1000, 10, 15);
    expect(d.porRango).toEqual([
      { bloques: 0, escenarios: 0 },
      { bloques: 2, escenarios: 200 },
      { bloques: 1, escenarios: 100 },
    ]);
  });
  it("measures coverage of [0, N) from merged intervals", () => {
    const d = disponerBloques(bloques, 3, 1000, 10, 15);
    expect(d.cubierto).toEqual([{ i0: 0, i1: 400 }]);
    expect(d.cobertura).toBeCloseTo(0.4);
  });
  it("merges overlaps and clamps to N", () => {
    expect(fusionarTramos([{ i0: 50, i1: 120 }, { i0: 0, i1: 60 }, { i0: 900, i1: 2000 }], 1000)).toEqual([
      { i0: 0, i1: 120 },
      { i0: 900, i1: 1000 },
    ]);
  });
  it("never yields a negative width when t1 lags", () => {
    const d = disponerBloques([{ rango: 1, i0: 0, i1: 1, ts: 20 }], 2, 10, 10, 15);
    expect(d.bloques[0]).toMatchObject({ inicio: 10, fin: 10 });
  });
});
