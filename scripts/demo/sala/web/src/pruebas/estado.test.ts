import { describe, expect, it } from "vitest";
import {
  estadoInicial,
  insertarCorrida,
  reducir,
  reducirLote,
  speedupDe,
  veredictoIdentidad,
  type EstadoSala,
} from "../dominio/estado";
import type { Evento, EventoFin } from "../dominio/eventos";
import type { Backend } from "../viz/tipos";

const inicio = (id: string, backend: Backend, afinidad = "-", ts = 1): Evento => ({
  t: "inicio",
  id,
  backend,
  procesos: backend === "serial" || backend === "openmp" ? 1 : 4,
  hilos: backend === "openmp" ? 24 : 1,
  n: 1000,
  afinidad,
  comando: `pp_${backend}`,
  ts,
});

const fin = (id: string, extra: Partial<EventoFin> = {}): Evento => ({
  t: "fin",
  id,
  segundos: 2,
  k: 42,
  n: 1000,
  p: 0.042,
  wilson: [0.03, 0.05],
  huella: "0123456789ab",
  trabajo_rangos: null,
  speedup: null,
  ts: 5,
  ...extra,
});

const correr = (s: EstadoSala, ...ev: Evento[]) => reducirLote(s, ev);
const ids = (s: EstadoSala) => s.corridas.map((c) => c.id);

describe("reducir", () => {
  it("applies estado, cpu and the run lifecycle", () => {
    let s = correr(
      estadoInicial,
      { t: "estado", modo: "replay", grabando: true, ocupado: true, ts: 0.5 },
      { t: "cpu", nucleos: [0.1, 0.9], ts: 0.6 },
      inicio("c1-serial", "serial"),
      { t: "avance", id: "c1-serial", hecho: 500, total: 1000, rango: null, escenarios_s: 250, ts: 3 },
    );
    expect(s).toMatchObject({ modo: "replay", grabando: true, ocupado: true, cpu: [0.1, 0.9], ahora: 3 });
    expect(s.corridas[0]).toMatchObject({ hecho: 500, total: 1000, tasa: 250, ts0: 1, comando: "pp_serial" });
    s = reducir(s, fin("c1-serial", { speedup: 1 }));
    expect(s.corridas[0].fin?.k).toBe(42);
  });

  it("tracks per-rank progress and E2 blocks", () => {
    const s = correr(
      estadoInicial,
      inicio("c1-mpi_dinamico", "mpi_dinamico"),
      { t: "bloque", id: "c1-mpi_dinamico", rango: 1, i0: 0, i1: 100, ts: 2 },
      { t: "bloque", id: "c1-mpi_dinamico", rango: 2, i0: 100, i1: 250, ts: 2.5 },
      inicio("c1-mpi_estatico", "mpi_estatico"),
      { t: "avance", id: "c1-mpi_estatico", hecho: 10, total: 250, rango: 3, ts: 3 },
    );
    expect(s.corridas[0].bloques).toEqual([
      { rango: 1, i0: 0, i1: 100, ts: 2 },
      { rango: 2, i0: 100, i1: 250, ts: 2.5 },
    ]);
    expect(s.corridas[0].asignado).toBe(250);
    expect(s.corridas[1].rangos).toEqual({ 3: { hecho: 10, total: 250 } });
  });

  it("marks an error on its run and ignores events of unknown runs", () => {
    let s = correr(estadoInicial, inicio("c1-serial", "serial"));
    const antes = s;
    s = reducir(s, { t: "avance", id: "otro", hecho: 1, total: 2, rango: null, ts: 0 });
    expect(s.corridas).toBe(antes.corridas);
    s = reducir(s, { t: "error", id: "c1-serial", mensaje: "corrida detenida", ts: 2 });
    expect(s.corridas[0].error).toBe("corrida detenida");
  });

  it("keeps the corridas reference on cpu-only events", () => {
    const s = correr(estadoInicial, inicio("c1-serial", "serial"));
    const t = reducir(s, { t: "cpu", nucleos: [1], ts: 9 });
    expect(t.corridas).toBe(s.corridas);
  });
});

describe("lane keying", () => {
  const carrera = (n: number) =>
    (["serial", "openmp", "hibrido"] as Backend[]).flatMap((b) => [
      inicio(`c${n}-${b}`, b, b === "hibrido" ? "false" : "-"),
      fin(`c${n}-${b}`),
    ]);

  it("keeps con error and corregido as separate lanes next to the race", () => {
    let s = correr(estadoInicial, ...carrera(1));
    s = correr(s, inicio("h2-close", "hibrido", "close"), fin("h2-close"));
    expect(ids(s)).toEqual(["c1-serial", "c1-openmp", "c1-hibrido", "h2-close"]);
    // Corregido replaces the lane with the same key (the race's hybrid uses afinidad false)...
    s = correr(s, inicio("h3-false", "hibrido", "false"), fin("h3-false"));
    expect(ids(s)).toEqual(["c1-serial", "c1-openmp", "h2-close", "h3-false"]);
    // ...and a second "con error" only replaces the previous "con error".
    s = correr(s, inicio("h4-close", "hibrido", "close"));
    expect(ids(s)).toEqual(["c1-serial", "c1-openmp", "h3-false", "h4-close"]);
  });

  it("a new race replaces the previous lanes, its own lanes accumulate", () => {
    let s = correr(estadoInicial, ...carrera(1), inicio("h2-close", "hibrido", "close"), fin("h2-close"));
    s = correr(s, inicio("c3-serial", "serial"));
    expect(ids(s)).toEqual(["c3-serial"]);
    s = correr(s, fin("c3-serial"), inicio("c3-openmp", "openmp"));
    expect(ids(s)).toEqual(["c3-serial", "c3-openmp"]);
  });

  it("never drops lanes while a run is in progress", () => {
    const base = correr(estadoInicial, inicio("c1-serial", "serial"));
    const r = insertarCorrida(base.corridas, { ...base.corridas[0], id: "c2-serial" });
    expect(r.map((c) => c.id)).toEqual(["c1-serial", "c2-serial"]);
  });

  it("derives a standalone hybrid's speedup from the race's serial lane", () => {
    const s = correr(
      estadoInicial,
      inicio("c1-serial", "serial"),
      fin("c1-serial", { segundos: 8, speedup: 1 }),
      inicio("h2-false", "hibrido", "false"),
      fin("h2-false", { segundos: 2 }),
    );
    expect(speedupDe(s.corridas[1], s.corridas)).toEqual({ valor: 4, derivado: true });
    expect(speedupDe(s.corridas[0], s.corridas)).toEqual({ valor: 1, derivado: false });
  });
});

describe("veredictoIdentidad", () => {
  it("waits for two finished runs", () => {
    const s = correr(estadoInicial, inicio("c1-serial", "serial"), fin("c1-serial"));
    expect(veredictoIdentidad(s.corridas)).toEqual({ tipo: "espera", corridas: 1 });
  });

  it("accepts identical k and huella", () => {
    const s = correr(estadoInicial, inicio("c1-serial", "serial"), fin("c1-serial"), inicio("c1-openmp", "openmp"), fin("c1-openmp"));
    expect(veredictoIdentidad(s.corridas)).toEqual({ tipo: "identicos", corridas: 2 });
  });

  it("flags a different huella or k", () => {
    const s = correr(
      estadoInicial,
      inicio("c1-serial", "serial"),
      fin("c1-serial"),
      inicio("c1-openmp", "openmp"),
      fin("c1-openmp", { huella: "ffffffffffff" }),
      inicio("c1-hibrido", "hibrido", "false"),
      fin("c1-hibrido", { k: 43 }),
    );
    expect(veredictoIdentidad(s.corridas)).toEqual({
      tipo: "distintos",
      corridas: 3,
      distintas: ["c1-openmp", "c1-hibrido"],
    });
  });
});
