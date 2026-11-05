import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "@fontsource-variable/inter";
import "./estilos/tokens.css";
import "./estilos/themes.css";
import "./estilos/base.css";
import { App } from "./app/App";
import { MOCK } from "./sala/api";

if (MOCK) document.title = "MOCK · Sala de control";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
