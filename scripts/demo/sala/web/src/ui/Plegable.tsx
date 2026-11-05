// Compound disclosure: Plegable.Root / Trigger / Content. The trigger is a real button with
// aria-expanded + aria-controls; the content is hidden (not just invisible) while closed.
import { createContext, use, useId, useState, type ComponentProps, type ReactNode } from "react";
import { IconoChevron } from "./iconos";
import s from "./Plegable.module.css";

interface Ctx {
  abierto: boolean;
  alternar: () => void;
  id: string;
}

const PlegableCtx = createContext<Ctx | null>(null);

function usePlegable(): Ctx {
  const c = use(PlegableCtx);
  if (!c) throw new Error("Plegable.* debe usarse dentro de Plegable.Root");
  return c;
}

interface RootProps extends ComponentProps<"div"> {
  porDefecto?: boolean;
  abierto?: boolean;
  alCambiar?: (abierto: boolean) => void;
}

function Root({ porDefecto = false, abierto, alCambiar, children, ...props }: RootProps) {
  const [interno, setInterno] = useState(porDefecto);
  const valor = abierto ?? interno;
  const id = useId();
  const alternar = () => {
    if (abierto === undefined) setInterno(!valor);
    alCambiar?.(!valor);
  };
  return (
    <PlegableCtx value={{ abierto: valor, alternar, id }}>
      <div data-abierto={valor} {...props}>
        {children}
      </div>
    </PlegableCtx>
  );
}

interface TriggerProps extends Omit<ComponentProps<"button">, "children"> {
  children: ReactNode;
  /** Hide the chevron when the trigger draws its own affordance. */
  sinChevron?: boolean;
}

function Trigger({ children, className, sinChevron, onClick, ...props }: TriggerProps) {
  const { abierto, alternar, id } = usePlegable();
  return (
    <button
      type="button"
      aria-expanded={abierto}
      aria-controls={id}
      className={`${s.disparador} ${className ?? ""}`}
      onClick={(e) => {
        onClick?.(e);
        if (!e.defaultPrevented) alternar();
      }}
      {...props}
    >
      {children}
      {sinChevron ? null : <IconoChevron className={s.chevron} data-abierto={abierto} />}
    </button>
  );
}

function Content({ className, ...props }: ComponentProps<"div">) {
  const { abierto, id } = usePlegable();
  return <div id={id} hidden={!abierto} className={`${s.contenido} ${className ?? ""}`} {...props} />;
}

export const Plegable = { Root, Trigger, Content };
