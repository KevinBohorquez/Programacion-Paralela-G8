import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { CurvaRiesgo } from "./CurvaRiesgo";
import { GraficoConvergencia, semiancho } from "./GraficoConvergencia";
import { GraficoSpeedup } from "./GraficoSpeedup";
import { LineaBloques } from "./LineaBloques";
import { MapaNucleos } from "./MapaNucleos";
import { bloquesMuestra, convergenciaMuestra, curvaMuestra } from "./demo/datosMuestra";

afterEach(cleanup);

describe("render smoke", () => {
  it("MapaNucleos draws one cell per core and summarises them", () => {
    const { container, rerender } = render(<MapaNucleos nucleos={Array.from({ length: 24 }, (_, i) => i / 23)} etiqueta="OpenMP" />);
    expect(container.querySelectorAll("[data-nivel]")).toHaveLength(24);
    expect(screen.getByRole("img").getAttribute("aria-label")).toMatch(/OpenMP.*24 CPU.*máxima 100\s%/);
    expect(screen.getByText("CPU 23")).toBeTruthy();
    rerender(<MapaNucleos nucleos={Array.from({ length: 24 }, () => 0.5)} />);
    expect(container.querySelector("path:last-of-type")?.getAttribute("d")).toMatch(/^M/);
  });

  it("CurvaRiesgo marks the threshold with its probability", () => {
    const c = curvaMuestra();
    render(<CurvaRiesgo {...c} umbral={70} />);
    expect(screen.getByRole("img").getAttribute("aria-label")).toMatch(/U = 70 mm, P = 0,36/);
    expect(screen.getByText("U = 70 mm")).toBeTruthy();
  });

  it("CurvaRiesgo survives empty data", () => {
    render(<CurvaRiesgo u={[]} p={[]} lo={[]} hi={[]} umbral={50} alto={200} />);
    expect(screen.getByText("sin datos todavía")).toBeTruthy();
  });

  it("GraficoSpeedup labels bars, seconds, ideal and running runs", () => {
    render(
      <GraficoSpeedup
        ideal={24}
        barras={[
          { id: "a", etiqueta: "OpenMP", backend: "openmp", speedup: 14.63, segundos: 4.27, enCurso: false },
          { id: "b", etiqueta: "Híbrido", backend: "hibrido", speedup: null, segundos: null, enCurso: true },
        ]}
      />,
    );
    expect(screen.getByText("14,6×")).toBeTruthy();
    expect(screen.getByText("4,27 s")).toBeTruthy();
    expect(screen.getByText("ideal 24×")).toBeTruthy();
    expect(screen.getByText("en curso…")).toBeTruthy();
  });

  it("LineaBloques renders ~320 blocks, the master row and coverage", () => {
    const bloques = bloquesMuestra(8, 10_000_000, 320);
    const { container } = render(<LineaBloques rangos={8} bloques={bloques} total={10_000_000} t0={100} t1={bloques[319]!.ts + 0.2} />);
    expect(screen.getByText("maestro (no simula)")).toBeTruthy();
    expect(screen.getByRole("img").getAttribute("aria-label")).toMatch(/320 bloques.*7 procesos.*100\s%/);
    const rects = container.querySelectorAll("svg > g:last-of-type > rect");
    expect(rects).toHaveLength(320);
  });

  it("GraficoConvergencia shows decades, the latest p̂ and the 1/√N guide", () => {
    render(<GraficoConvergencia puntos={convergenciaMuestra()} />);
    expect(screen.getByText("10³")).toBeTruthy();
    expect(screen.getByText("10⁷")).toBeTruthy();
    expect(screen.getByText("∝ 1/√N")).toBeTruthy();
    expect(screen.getByText(/^p̂ = 0,18/)).toBeTruthy();
  });

  it("GraficoConvergencia survives no points", () => {
    render(<GraficoConvergencia puntos={[]} />);
    expect(screen.getByText("sin puntos todavía")).toBeTruthy();
  });

  it("the guide envelope shrinks as 1/√N", () => {
    expect(semiancho(0.2, 1e4) / semiancho(0.2, 1e6)).toBeCloseTo(10);
  });
});
