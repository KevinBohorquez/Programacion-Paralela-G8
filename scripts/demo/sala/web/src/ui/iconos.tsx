// Inline Lucide-style icons: 24px viewBox, 1.5px stroke, currentColor. Decorative unless labelled.
import type { ReactNode, SVGProps } from "react";

function Icono({ children, ...props }: SVGProps<SVGSVGElement> & { children: ReactNode }) {
  return (
    <svg
      viewBox="0 0 24 24"
      width="1em"
      height="1em"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      {...props}
    >
      {children}
    </svg>
  );
}

type P = SVGProps<SVGSVGElement>;

export const IconoPlay = (p: P) => (
  <Icono {...p}>
    <path d="M7 4.5v15l12-7.5z" />
  </Icono>
);
export const IconoParar = (p: P) => (
  <Icono {...p}>
    <rect x="6" y="6" width="12" height="12" rx="1.5" />
  </Icono>
);
export const IconoGrabar = (p: P) => (
  <Icono {...p}>
    <circle cx="12" cy="12" r="8" />
    <circle cx="12" cy="12" r="3.5" fill="currentColor" />
  </Icono>
);
export const IconoHistorial = (p: P) => (
  <Icono {...p}>
    <path d="M3 12a9 9 0 1 0 3-6.7L3 8" />
    <path d="M3 3v5h5" />
    <path d="M12 7v5l3 2" />
  </Icono>
);
export const IconoGrafico = (p: P) => (
  <Icono {...p}>
    <path d="M3 3v18h18" />
    <path d="m7 15 4-5 3 3 5-7" />
  </Icono>
);
export const IconoSol = (p: P) => (
  <Icono {...p}>
    <circle cx="12" cy="12" r="4" />
    <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
  </Icono>
);
export const IconoLuna = (p: P) => (
  <Icono {...p}>
    <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" />
  </Icono>
);
export const IconoChevron = (p: P) => (
  <Icono {...p}>
    <path d="m6 9 6 6 6-6" />
  </Icono>
);
export const IconoCerrar = (p: P) => (
  <Icono {...p}>
    <path d="M18 6 6 18M6 6l12 12" />
  </Icono>
);
export const IconoCheck = (p: P) => (
  <Icono {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="m8 12 3 3 5-6" />
  </Icono>
);
export const IconoAlerta = (p: P) => (
  <Icono {...p}>
    <path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" />
    <path d="M12 9v4M12 17h.01" />
  </Icono>
);
export const IconoInfo = (p: P) => (
  <Icono {...p}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 16v-4M12 8h.01" />
  </Icono>
);
export const IconoMaximizar = (p: P) => (
  <Icono {...p}>
    <path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7" />
  </Icono>
);
