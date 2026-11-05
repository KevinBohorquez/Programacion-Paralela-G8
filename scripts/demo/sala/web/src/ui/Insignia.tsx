import type { ComponentProps } from "react";
import s from "./Insignia.module.css";

export type Tono = "neutral" | "exito" | "aviso" | "peligro" | "info" | "contorno";

/** Tone is a second signal: the badge always carries its own text. */
export function Insignia({ tono = "neutral", className, ...props }: ComponentProps<"span"> & { tono?: Tono }) {
  return <span className={`${s.insignia} ${s[tono]} ${className ?? ""}`} {...props} />;
}
