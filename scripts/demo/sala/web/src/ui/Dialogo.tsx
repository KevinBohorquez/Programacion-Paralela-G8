// Compound dialog: Dialogo.Root / Trigger / Content / Title / Close.
// aria-modal, focus trap, focus restore, Escape through the layer stack, scrim click to close.
import {
  createContext,
  use,
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
  type ComponentProps,
  type ReactNode,
  type RefObject,
} from "react";
import { createPortal } from "react-dom";
import { Boton, type BotonProps } from "./Boton";
import { apilarCapaEscape } from "./capasEscape";
import { IconoCerrar } from "./iconos";
import s from "./Dialogo.module.css";

interface Ctx {
  abierto: boolean;
  fijar: (v: boolean) => void;
  idTitulo: string;
  disparador: RefObject<HTMLButtonElement | null>;
}

const DialogoCtx = createContext<Ctx | null>(null);

function useDialogo(): Ctx {
  const c = use(DialogoCtx);
  if (!c) throw new Error("Dialogo.* debe usarse dentro de Dialogo.Root");
  return c;
}

interface RootProps {
  children: ReactNode;
  abierto?: boolean;
  porDefecto?: boolean;
  alCambiar?: (abierto: boolean) => void;
}

function Root({ children, abierto, porDefecto = false, alCambiar }: RootProps) {
  const [interno, setInterno] = useState(porDefecto);
  const controlado = abierto !== undefined;
  const valor = controlado ? abierto : interno;
  const disparador = useRef<HTMLButtonElement | null>(null);
  const idTitulo = useId();
  // Keep `fijar` stable even when the parent passes an inline `alCambiar`, so Content's effect
  // (focus in, Escape layer) runs once per opening and not on every parent render.
  const ultimo = useRef({ controlado, alCambiar });
  ultimo.current = { controlado, alCambiar };
  const fijar = useCallback((v: boolean) => {
    if (!ultimo.current.controlado) setInterno(v);
    ultimo.current.alCambiar?.(v);
  }, []);
  return <DialogoCtx value={{ abierto: valor, fijar, idTitulo, disparador }}>{children}</DialogoCtx>;
}

function Trigger({ onClick, ...props }: BotonProps) {
  const { abierto, fijar, disparador } = useDialogo();
  return (
    <Boton
      ref={disparador}
      aria-haspopup="dialog"
      aria-expanded={abierto}
      onClick={(e) => {
        onClick?.(e);
        if (!e.defaultPrevented) fijar(true);
      }}
      {...props}
    />
  );
}

const ENFOCABLES =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

function enfocables(raiz: HTMLElement): HTMLElement[] {
  return Array.from(raiz.querySelectorAll<HTMLElement>(ENFOCABLES)).filter((el) => !el.hasAttribute("hidden"));
}

interface ContentProps extends Omit<ComponentProps<"div">, "title"> {
  /** Width preset; the content scrolls inside the box. */
  ancho?: "medio" | "ancho";
  descripcion?: ReactNode;
}

function Content({ children, ancho = "medio", className, descripcion, ...props }: ContentProps) {
  const { abierto, fijar, idTitulo, disparador } = useDialogo();
  const caja = useRef<HTMLDivElement>(null);
  const idDesc = useId();

  // Focus in on open, restore to the trigger (or the previous element) on close, Escape on the stack.
  useEffect(() => {
    if (!abierto) return;
    const previo = document.activeElement as HTMLElement | null;
    const raiz = caja.current;
    if (raiz) (enfocables(raiz)[0] ?? raiz).focus();
    const quitar = apilarCapaEscape(() => fijar(false));
    return () => {
      quitar();
      const destino = disparador.current ?? previo;
      if (destino && document.contains(destino)) destino.focus();
    };
  }, [abierto, fijar, disparador]);

  if (!abierto) return null;

  const atrapar = (e: React.KeyboardEvent) => {
    if (e.key !== "Tab" || !caja.current) return;
    const lista = enfocables(caja.current);
    if (!lista.length) {
      e.preventDefault();
      return;
    }
    const primero = lista[0];
    const ultimo = lista[lista.length - 1];
    if (e.shiftKey && document.activeElement === primero) {
      e.preventDefault();
      ultimo.focus();
    } else if (!e.shiftKey && document.activeElement === ultimo) {
      e.preventDefault();
      primero.focus();
    }
  };

  return createPortal(
    <div
      className={s.velo}
      data-testid="velo"
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) fijar(false);
      }}
    >
      <div
        ref={caja}
        role="dialog"
        aria-modal="true"
        aria-labelledby={idTitulo}
        aria-describedby={descripcion ? idDesc : undefined}
        tabIndex={-1}
        className={`${s.caja} ${s[ancho]} ${className ?? ""}`}
        onKeyDown={atrapar}
        {...props}
      >
        {descripcion ? (
          <p id={idDesc} className="sr-only">
            {descripcion}
          </p>
        ) : null}
        {children}
      </div>
    </div>,
    document.body,
  );
}

function Title({ className, ...props }: ComponentProps<"h2">) {
  const { idTitulo } = useDialogo();
  return <h2 id={idTitulo} className={`${s.titulo} ${className ?? ""}`} {...props} />;
}

function Close({ children, ...props }: BotonProps) {
  const { fijar } = useDialogo();
  return (
    <Boton
      variante="fantasma"
      soloIcono={!children}
      aria-label={children ? undefined : "Cerrar"}
      onClick={() => fijar(false)}
      {...props}
    >
      {children ?? <IconoCerrar />}
    </Boton>
  );
}

function Header({ className, ...props }: ComponentProps<"header">) {
  return <header className={`${s.cabecera} ${className ?? ""}`} {...props} />;
}

export const Dialogo = { Root, Trigger, Content, Title, Close, Header };
