import type { ComponentProps } from "react";
import s from "./Boton.module.css";

export type Variante = "primario" | "secundario" | "fantasma" | "peligro";

export interface BotonProps extends ComponentProps<"button"> {
  variante?: Variante;
  /** Icon-only buttons must still carry an aria-label. */
  soloIcono?: boolean;
}

/** React 19: `ref` arrives as a regular prop and is spread onto the button. */
export function Boton({ variante = "secundario", soloIcono, className, type = "button", ...props }: BotonProps) {
  const clases = [s.boton, s[variante], soloIcono ? s.soloIcono : "", className ?? ""].join(" ");
  return <button type={type} className={clases} {...props} />;
}

export const clasesBoton = s;
