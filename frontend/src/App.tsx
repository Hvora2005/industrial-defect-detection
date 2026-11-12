import { useCallback, useEffect, useRef, useState } from "react";
import {
  Activity,
  Aperture,
  ArrowUpRight,
  ChartNoAxesCombined,
  ChevronRight,
  Circle,
  Cpu,
  History as HistoryIcon,
  LayoutDashboard,
  Menu,
  Monitor,
  Moon,
  Settings2,
  Sun,
  X,
} from "lucide-react";
import { api } from "./services/api";
import { useResource } from "./hooks/useResource";
import { useCamera } from "./hooks/useCamera";
import { useMonitor } from "./hooks/useMonitor";
import { useTheme } from "./hooks/useTheme";
import { Inspection } from "./views/Inspection";
import { Overview } from "./views/Overview";
import { History, HistoryDetail } from "./views/History";
import { Statistics } from "./views/Statistics";
import { Settings } from "./views/Settings";
import { ErrorNotice, Loading, Panel, ResultPanel } from "./components/Common";
import type { Detection, HistoryRow, View } from "./types";
import "./styles.css";
import "./themes.css";

const navigation = [
  {
    id: "inspeccion",
    label: "Inspección en vivo",
    icon: Aperture,
    detail: "Captura, analiza y revisa cada pieza.",
  },
  {
    id: "resumen",
    label: "Panel general",
    icon: LayoutDashboard,
    detail: "El estado de tu operación, en un solo lugar.",
  },
  {
    id: "historial",
    label: "Historial",
    icon: HistoryIcon,
    detail: "Consulta y revisa las inspecciones registradas.",
  },
  {
    id: "estadisticas",
    label: "Estadísticas",
    icon: ChartNoAxesCombined,
    detail: "Comprende los hallazgos y su evolución.",
  },
  {
    id: "configuracion",
    label: "Configuración",
    icon: Settings2,
    detail: "Prepara tu estación para la siguiente inspección.",
  },
  {
    id: "monitor",
    label: "Monitor remoto",
    icon: Monitor,
    detail: "Recibe las inspecciones enviadas desde otros dispositivos.",
  },
] as const;
function selectedView(): View {
  const hash = location.hash.slice(1);
  return navigation.some((n) => n.id === hash)
    ? (hash as View)
    : location.pathname === "/dashboard"
      ? "resumen"
      : location.pathname === "/monitor"
        ? "monitor"
        : "inspeccion";
}
export default function App() {
  const { theme, toggleTheme } = useTheme();
  const [view, setView] = useState<View>(selectedView);
  const [menu, setMenu] = useState(false);
  const [limit, setLimit] = useState(100);
  const [period, setPeriod] = useState(60);
  const [detail, setDetail] = useState<HistoryRow>();
  const [last, setLast] = useState<Detection>();
  const [original, setOriginal] = useState<string>();
  const originalRef = useRef<string | undefined>(undefined);
  const stats = useResource(api.stats);
  const health = useResource(api.health);
  const runtime = useResource(api.runtime);
  const loadHistory = useCallback(() => api.history(limit), [limit]);
  const history = useResource(loadHistory);
  const loadTrend = useCallback(
    () => api.trend(view === "estadisticas" ? period : 60),
    [view, period],
  );
  const trend = useResource(loadTrend);
  const onResult = useCallback(
    (result: Detection, blob?: Blob) => {
      setLast(result);
      if (originalRef.current) URL.revokeObjectURL(originalRef.current);
      originalRef.current = blob ? URL.createObjectURL(blob) : undefined;
      setOriginal(originalRef.current);
      void stats.reload();
      void history.reload();
      void trend.reload();
    },
    [stats.reload, history.reload, trend.reload],
  );
  const camera = useCamera(onResult);
  const connected = useMonitor(onResult);
  useEffect(() => {
    const change = () => {
      setView(selectedView());
      setMenu(false);
      window.scrollTo(0, 0);
    };
    window.addEventListener("hashchange", change);
    return () => window.removeEventListener("hashchange", change);
  }, []);
  useEffect(
    () => () => {
      if (originalRef.current) URL.revokeObjectURL(originalRef.current);
    },
    [],
  );
  const current = navigation.find((n) => n.id === view)!;
  const online = !!health.data && !health.error;
  const resourceError =
    view === "historial"
      ? ""
      : view === "resumen" || view === "estadisticas"
        ? stats.error || trend.error || history.error
        : "";
  return (
    <div className="application">
      <a
        className="skip-link"
        href="#main-content"
        onClick={(event) => {
          event.preventDefault();
          document.getElementById("main-content")?.focus();
        }}
      >
        Ir al contenido
      </a>
      {menu && (
        <button
          className="nav-backdrop"
          aria-label="Cerrar navegación"
          onClick={() => setMenu(false)}
        />
      )}
      <aside className={`sidebar ${menu ? "is-open" : ""}`}>
        <a className="brand" href="/#inspeccion">
          <span className="brand-mark">
            <Aperture size={28} strokeWidth={1.6} />
          </span>
          <span>
            Acero Cifrado<small>Visión industrial</small>
          </span>
        </a>
        <div className="workspace-label">
          <span className="dot teal" />
          Estación de inspección
        </div>
        <nav aria-label="Navegación principal">
          {navigation.map((n) => (
            <a
              href={`#${n.id}`}
              key={n.id}
              className={view === n.id ? "selected" : ""}
              aria-current={view === n.id ? "page" : undefined}
            >
              <n.icon size={19} />
              <span>{n.label}</span>
              {view === n.id && <ChevronRight size={14} />}
            </a>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="local-label">
            <i className={`dot ${online ? "teal" : "warn"}`} />
            {health.loading
              ? "Conectando…"
              : online
                ? "Servidor conectado"
                : "Servidor sin conexión"}
          </div>
          <p>Procesamiento en tu servidor local</p>
          <a href="/docs" target="_blank" rel="noreferrer">
            Documentación de API
            <ArrowUpRight size={13} />
          </a>
          <div className="sidebar-version">
            Acero Cifrado <span>Estación local</span>
          </div>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumb">
            <button
              className="icon-button menu-toggle"
              aria-label="Abrir navegación"
              aria-expanded={menu}
              onClick={() => setMenu(!menu)}
            >
              {menu ? <X size={20} /> : <Menu size={20} />}
            </button>
            <span>Estación local</span>
            <ChevronRight size={13} />
            <strong>{current.label}</strong>
          </div>
          <div className="topbar-status">
            <button
              className="icon-button theme-toggle"
              onClick={toggleTheme}
              aria-label={
                theme === "dark" ? "Activar tema claro" : "Activar tema oscuro"
              }
              title={
                theme === "dark" ? "Activar tema claro" : "Activar tema oscuro"
              }
            >
              {theme === "dark" ? <Sun size={17} /> : <Moon size={17} />}
            </button>
            <span className={`status-chip ${online ? "" : "offline"}`}>
              <i className="dot" />
              {health.loading
                ? "Conectando…"
                : online
                  ? "Sistema conectado"
                  : "Sin conexión"}
            </span>
            <span className="device-chip">
              <Cpu size={14} />
              {runtime.data?.active_device?.startsWith("cuda")
                ? "GPU activa"
                : runtime.data?.active_device === "cpu"
                  ? "CPU activa"
                  : runtime.data?.cuda_available
                    ? "CUDA disponible"
                    : runtime.data
                      ? "CPU disponible"
                      : "Consultando dispositivo"}
            </span>
          </div>
        </header>
        <main id="main-content" tabIndex={-1}>
          <div className="page-heading">
            <div>
              <h1>{current.label}</h1>
              <p>{current.detail}</p>
            </div>
            <div className="session-label">
              <Circle size={8} fill="currentColor" />
              {camera.data?.running ? "Cámara en captura" : "Registro manual"}
            </div>
          </div>
          {runtime.error && (
            <ErrorNotice
              message={runtime.error}
              retry={() => void runtime.reload()}
            />
          )}
          {health.error && (
            <ErrorNotice
              message={health.error}
              retry={() => void health.reload()}
            />
          )}
          {health.data && !health.data.model_loaded && (
            <div className="notice warning">
              <Activity size={18} />
              <span>
                El servidor está disponible, pero no tiene un modelo cargado.
                Puedes consultar el historial; configura los pesos y reinicia
                FastAPI para inspeccionar.
              </span>
            </div>
          )}
          {resourceError && (
            <ErrorNotice
              message={`Los datos podrían estar desactualizados. ${resourceError}`}
              retry={() => {
                void stats.reload();
                void history.reload();
                void trend.reload();
              }}
            />
          )}
          {view === "inspeccion" && (
            <Inspection
              camera={camera}
              runtime={runtime.data}
              result={last}
              originalUrl={original}
              onResult={onResult}
            />
          )}
          {view === "resumen" &&
            (stats.loading ? (
              <Loading />
            ) : (
              <Overview
                stats={stats.data}
                rows={history.data?.inspections || []}
                buckets={trend.data?.buckets || []}
                runtime={runtime.data}
                onSelect={setDetail}
              />
            ))}
          {view === "historial" && (
            <History
              rows={history.data?.inspections || []}
              loading={history.loading}
              error={history.error}
              limit={limit}
              setLimit={setLimit}
              reload={() => void history.reload()}
              onSelect={setDetail}
            />
          )}
          {view === "estadisticas" &&
            (stats.loading ? (
              <Loading />
            ) : (
              <Statistics
                stats={stats.data}
                buckets={trend.data?.buckets || []}
                period={period}
                setPeriod={setPeriod}
              />
            ))}
          {view === "configuracion" && (
            <Settings
              camera={camera}
              runtime={runtime.data}
              health={health.data}
            />
          )}
          {view === "monitor" && (
            <div className="remote-monitor">
              <Panel
                title="Conexión con la estación"
                detail="Las capturas registradas se reciben por WebSocket"
              >
                <span className={`status-chip ${connected ? "" : "offline"}`}>
                  <i className="dot" />
                  {connected ? "Escuchando inspecciones" : "Reconectando…"}
                </span>
                <p className="muted">
                  Abre Inspección en vivo en tu teléfono. Cada captura
                  registrada se mostrará aquí; las vistas previas no se
                  transmiten como inspecciones.
                </p>
              </Panel>
              <ResultPanel result={last} originalUrl={original} />
            </div>
          )}
          <footer className="page-footer">
            <span>
              <span className="dot teal" />
              Acero Cifrado
            </span>
            <span>Sin detecciones no certifica la calidad de una pieza.</span>
          </footer>
        </main>
      </div>
      {detail && (
        <HistoryDetail row={detail} onClose={() => setDetail(undefined)} />
      )}
    </div>
  );
}
