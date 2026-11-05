// Measures a box's width with ResizeObserver so the SVG draws 1 unit = 1 px and text keeps its size.
import { useEffect, useRef, useState } from "react";

export function useAncho<T extends HTMLElement>(defecto: number, minimo = 280) {
  const ref = useRef<T>(null);
  const [ancho, setAncho] = useState(defecto);
  useEffect(() => {
    const elemento = ref.current;
    if (elemento === null || typeof ResizeObserver === "undefined") return undefined;
    const observador = new ResizeObserver((entradas) => {
      const medido = entradas[0]?.contentRect.width;
      if (medido !== undefined && medido > 0) setAncho(Math.max(minimo, Math.round(medido)));
    });
    observador.observe(elemento);
    return () => observador.disconnect();
  }, [minimo]);
  return { ref, ancho };
}
