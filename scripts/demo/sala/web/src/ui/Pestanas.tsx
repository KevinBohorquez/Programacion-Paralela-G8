// Compound tabs: Pestanas.Root / List / Trigger / Panel, with roving focus on the arrow keys.
import { createContext, use, useId, useState, type ComponentProps } from "react";
import s from "./Pestanas.module.css";

interface Ctx {
  valor: string;
  fijar: (v: string) => void;
  base: string;
}

const PestanasCtx = createContext<Ctx | null>(null);

function usePestanas(): Ctx {
  const c = use(PestanasCtx);
  if (!c) throw new Error("Pestanas.* debe usarse dentro de Pestanas.Root");
  return c;
}

function Root({ porDefecto, children, ...props }: ComponentProps<"div"> & { porDefecto: string }) {
  const [valor, fijar] = useState(porDefecto);
  const base = useId();
  return (
    <PestanasCtx value={{ valor, fijar, base }}>
      <div {...props}>{children}</div>
    </PestanasCtx>
  );
}

function List({ className, ...props }: ComponentProps<"div">) {
  const mover = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
    const tabs = Array.from(e.currentTarget.querySelectorAll<HTMLButtonElement>('[role="tab"]'));
    const i = tabs.indexOf(document.activeElement as HTMLButtonElement);
    const j = (i + (e.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length;
    tabs[j]?.focus();
    tabs[j]?.click();
  };
  return <div role="tablist" className={`${s.lista} ${className ?? ""}`} onKeyDown={mover} {...props} />;
}

function Trigger({ valor, className, ...props }: ComponentProps<"button"> & { valor: string }) {
  const c = usePestanas();
  const activo = c.valor === valor;
  return (
    <button
      type="button"
      role="tab"
      id={`${c.base}-t-${valor}`}
      aria-selected={activo}
      aria-controls={`${c.base}-p-${valor}`}
      tabIndex={activo ? 0 : -1}
      className={`${s.pestana} ${className ?? ""}`}
      onClick={() => c.fijar(valor)}
      {...props}
    />
  );
}

function Panel({ valor, ...props }: ComponentProps<"div"> & { valor: string }) {
  const c = usePestanas();
  return (
    <div
      role="tabpanel"
      id={`${c.base}-p-${valor}`}
      aria-labelledby={`${c.base}-t-${valor}`}
      hidden={c.valor !== valor}
      tabIndex={0}
      {...props}
    />
  );
}

export const Pestanas = { Root, List, Trigger, Panel };
