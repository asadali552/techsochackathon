import "@fontsource-variable/inter";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { HomePage } from "./pages/HomePage";
import "./index.css";
import "./safety-map.css";
import "./journey-planner.css";
import "./incident-reporting.css";
import "./assistant.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <HomePage />
  </StrictMode>,
);
