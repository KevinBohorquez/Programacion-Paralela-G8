// Operator inputs shared by the topbar (Carrera, hybrids, Convergencia) and the left panels.
import { createContext, use, useCallback, useMemo, useState, type ReactNode } from "react";
import { BACKENDS } from "../dominio/eventos";
import type { Backend } from "../viz/tipos";

export interface Config {
  id: string;
  estacion: string;
  regimen: string;
  c: number;
  u: number;
}

export interface Controles {
  n: number;
  nucleos: number;
  backends: Backend[];
  configCarrera: string;
  configRiesgo: string;
  c: number;
  u: number;
  configs: Config[];
}

interface Ctx {
  controles: Controles;
  fijar: (cambio: Partial<Controles>) => void;
}

const ControlesCtx = createContext<Ctx | null>(null);

export const inicialControles: Controles = {
  n: 20_000_000,
  nucleos: 24,
  backends: [...BACKENDS],
  configCarrera: "sintetico",
  configRiesgo: "",
  c: 0,
  u: 0,
  configs: [],
};

export function ProveedorControles({ children }: { children: ReactNode }) {
  const [controles, setControles] = useState(inicialControles);
  const fijar = useCallback((cambio: Partial<Controles>) => setControles((c) => ({ ...c, ...cambio })), []);
  const valor = useMemo(() => ({ controles, fijar }), [controles, fijar]);
  return <ControlesCtx value={valor}>{children}</ControlesCtx>;
}

export function useControles(): Ctx {
  const c = use(ControlesCtx);
  if (!c) throw new Error("useControles requiere ProveedorControles");
  return c;
}

/** A real El Niño station by default (Piura Bernal if present), never the synthetic config. */
export function configPreferida(configs: Config[]): Config | undefined {
  return (
    configs.find((c) => c.id === "piura_bernal_el_nino") ??
    configs.find((c) => c.id.endsWith("_el_nino")) ??
    configs.find((c) => c.id !== "sintetico" && c.id !== "ejemplo") ??
    configs[0]
  );
}
