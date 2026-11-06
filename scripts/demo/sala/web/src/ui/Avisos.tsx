// Toasts in a permanently mounted aria-live="polite" region; `useAvisar()` pushes one.
import { createContext, use, useCallback, useRef, useState, type ReactNode } from "react";
import type { Avisar } from "../sala/api";
import { IconoAlerta, IconoCheck, IconoInfo } from "./iconos";
import s from "./Avisos.module.css";

interface Aviso {
  id: number;
  texto: string;
  tono: "neutral" | "peligro" | "exito";
}

const AvisosCtx = createContext<Avisar | null>(null);

export function useAvisar(): Avisar {
  const c = use(AvisosCtx);
  if (!c) throw new Error("useAvisar requiere ProveedorAvisos");
  return c;
}

export function ProveedorAvisos({ children, duracion = 4000 }: { children: ReactNode; duracion?: number }) {
  const [avisos, setAvisos] = useState<Aviso[]>([]);
  const siguiente = useRef(0);
  const avisar = useCallback<Avisar>(
    (texto, tono = "neutral") => {
      const id = ++siguiente.current;
      // Collapse repeats of the same text (e.g. several 409s) into one visible toast.
      setAvisos((a) => [...a.filter((x) => x.texto !== texto), { id, texto, tono }].slice(-4));
      window.setTimeout(() => setAvisos((a) => a.filter((x) => x.id !== id)), duracion);
    },
    [duracion],
  );
  return (
    <AvisosCtx value={avisar}>
      {children}
      <div className={s.region} aria-live="polite" aria-atomic="false" role="status">
        {avisos.map((a) => (
          <div key={a.id} className={`${s.aviso} ${s[a.tono]}`}>
            {a.tono === "peligro" ? <IconoAlerta /> : a.tono === "exito" ? <IconoCheck /> : <IconoInfo />}
            <span>{a.texto}</span>
          </div>
        ))}
      </div>
    </AvisosCtx>
  );
}
