import { lazy, Suspense, useState } from "react";
import { accion, MOCK } from "../sala/api";
import { useSala } from "../sala/instancia";
import { Boton } from "../ui/Boton";
import { Dialogo } from "../ui/Dialogo";
import { Insignia } from "../ui/Insignia";
import { useAvisar } from "../ui/Avisos";
import { IconoGrabar, IconoGrafico, IconoHistorial, IconoLuna, IconoParar, IconoPlay, IconoSol } from "../ui/iconos";
import { useControles } from "./controles";
import { DialogoReplay } from "./DialogoReplay";
import s from "./BarraSuperior.module.css";

const ContenidoConvergencia = lazy(() => import("./ContenidoConvergencia"));

type Tema = "dark" | "light";

function temaActual(): Tema {
  return document.documentElement.dataset.theme === "light" ? "light" : "dark";
}

function aplicarTema(t: Tema) {
  document.documentElement.dataset.theme = t;
  document.querySelector('meta[name="theme-color"]')?.setAttribute("content", t === "dark" ? "#0e0e10" : "#f7f7f8");
  try {
    localStorage.setItem("sala-tema", t);
  } catch {
    /* private mode: the toggle still works for this visit */
  }
}

function Conexion() {
  const conexion = useSala((s) => s.conexion);
  const texto =
    conexion === "abierta" ? "Conectado al servidor" : conexion === "caida" ? "Sin conexión, reintentando…" : "Conectando…";
  return (
    <span className={s.conexion} data-estado={conexion} title={texto}>
      <i className={s.punto} aria-hidden="true" />
      <span className={conexion === "abierta" ? "sr-only" : s.conexionTexto}>{texto}</span>
    </span>
  );
}

function Distintivos() {
  const modo = useSala((s) => s.modo);
  const grabando = useSala((s) => s.grabando);
  return (
    <div className={s.distintivos}>
      {MOCK ? (
        <Insignia tono="aviso" title="Eventos simulados en el navegador; las cifras son ilustrativas">
          MOCK · datos ilustrativos
        </Insignia>
      ) : null}
      {modo === "replay" ? (
        <Insignia tono="info">REPLAY</Insignia>
      ) : MOCK ? null : (
        <Insignia tono="exito">VIVO</Insignia>
      )}
      {grabando ? (
        <Insignia tono="peligro">
          <i className={s.rec} aria-hidden="true" />
          Grabando
        </Insignia>
      ) : null}
      <Conexion />
    </div>
  );
}

export function BarraSuperior() {
  const avisar = useAvisar();
  const { controles } = useControles();
  const grabando = useSala((s) => s.grabando);
  const [tema, setTema] = useState<Tema>(temaActual);
  const [nombreGrabacion, setNombreGrabacion] = useState("ensayo");
  const [convAbierto, setConvAbierto] = useState(false);

  const carrera = () => {
    if (!controles.backends.length) {
      avisar("Elige al menos un backend en Parámetros", "peligro");
      return;
    }
    void accion(avisar, "POST", "/api/carrera", {
      backends: controles.backends,
      n: controles.n,
      nucleos: controles.nucleos,
      config: controles.configCarrera,
    });
  };
  const hibrido = (afinidad: "close" | "false") => {
    const procesos = 4;
    void accion(avisar, "POST", "/api/hibrido", {
      procesos,
      hilos: Math.max(1, Math.floor(controles.nucleos / procesos)),
      afinidad,
      n: controles.n,
      config: controles.configCarrera,
    });
  };
  const grabar = async () => {
    const r = await accion<{ grabando: boolean; archivo?: string }>(avisar, "POST", "/api/grabar", {
      activo: !grabando,
      nombre: nombreGrabacion.trim() || undefined,
    });
    if (r?.grabando && r.archivo) avisar(`Grabando en ${r.archivo}`, "exito");
    else if (r && !r.grabando) avisar("Grabación detenida", "neutral");
  };

  return (
    <header className={s.barra}>
      <h1 className={s.titulo}>Sala de control · Riesgo de inundación urbana</h1>
      <Distintivos />
      <nav className={s.acciones} aria-label="Acciones de la demo">
        <Boton variante="primario" onClick={carrera}>
          <IconoPlay />
          Carrera
        </Boton>
        <Boton onClick={() => hibrido("close")}>Híbrido con error</Boton>
        <Boton onClick={() => hibrido("false")}>Híbrido corregido</Boton>
        <Boton variante="fantasma" onClick={() => void accion(avisar, "POST", "/api/detener")}>
          <IconoParar />
          Detener
        </Boton>
        <span className={s.separador} aria-hidden="true" />
        <Boton
          variante="fantasma"
          aria-pressed={grabando}
          className={grabando ? s.grabando : undefined}
          onClick={() => void grabar()}
          title={grabando ? "Detener la grabación de eventos" : `Grabar eventos en «${nombreGrabacion}»`}
        >
          <IconoGrabar />
          {grabando ? "Parar" : "Grabar"}
        </Boton>
        <DialogoReplay nombreGrabacion={nombreGrabacion} alCambiarNombre={setNombreGrabacion}>
          <IconoHistorial />
          Replay
        </DialogoReplay>
        <Dialogo.Root abierto={convAbierto} alCambiar={setConvAbierto}>
          <Dialogo.Trigger variante="fantasma">
            <IconoGrafico />
            Convergencia
          </Dialogo.Trigger>
          <Dialogo.Content ancho="ancho">
            <Dialogo.Header>
              <Dialogo.Title>Convergencia de p̂ al crecer N</Dialogo.Title>
              <Dialogo.Close />
            </Dialogo.Header>
            <Suspense fallback={<p className={s.cargando}>Cargando…</p>}>
              <ContenidoConvergencia />
            </Suspense>
          </Dialogo.Content>
        </Dialogo.Root>
        <Boton
          variante="fantasma"
          soloIcono
          aria-label={tema === "dark" ? "Cambiar a tema claro" : "Cambiar a tema oscuro"}
          title={tema === "dark" ? "Tema claro" : "Tema oscuro"}
          onClick={() => {
            const t = tema === "dark" ? "light" : "dark";
            aplicarTema(t);
            setTema(t);
          }}
        >
          {tema === "dark" ? <IconoSol /> : <IconoLuna />}
        </Boton>
      </nav>
    </header>
  );
}
