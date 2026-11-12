import {
  ArrowUpRight,
  CircleCheck,
  ScanLine,
  ScanSearch,
  Layers,
} from "lucide-react";
import type { Bucket, HistoryRow, Runtime, Stats } from "../types";
import { Distribution, Trend } from "../components/Charts";
import { HistoryTable, Panel } from "../components/Common";
import { num } from "../format";
export function Metrics({ stats }: { stats?: Stats }) {
  const items = [
    {
      label: "Inspecciones registradas",
      value: stats?.total_inspected,
      icon: Layers,
      note: "Eventos de captura manual",
    },
    {
      label: "Con hallazgos",
      value: stats?.fail_count,
      icon: ScanSearch,
      note: "Inspecciones con detecciones",
      tone: "amber",
    },
    {
      label: "Sin detecciones",
      value: stats?.no_detections_count,
      icon: CircleCheck,
      note: "Calidad no verificada",
      tone: "teal",
    },
    {
      label: "Confianza promedio",
      value: stats?.avg_confidence,
      icon: ScanLine,
      note: "Sobre todas las detecciones",
      suffix: "%",
      digits: 1,
    },
  ];
  return (
    <div className="metrics-grid">
      {items.map((item) => (
        <section className={`metric ${item.tone || ""}`} key={item.label}>
          <div>
            <p>{item.label}</p>
            <item.icon size={19} />
          </div>
          <strong>
            {num(item.value, item.digits || 0)}
            {item.value != null ? item.suffix : ""}
          </strong>
          <small>{item.note}</small>
        </section>
      ))}
    </div>
  );
}
export function Overview({
  stats,
  rows,
  buckets,
  runtime,
  onSelect,
}: {
  stats?: Stats;
  rows: HistoryRow[];
  buckets: Bucket[];
  runtime?: Runtime;
  onSelect: (r: HistoryRow) => void;
}) {
  return (
    <>
      <div className="overview-lead">
        <div>
          <span className="signal-ring">
            <ScanLine size={26} />
          </span>
          <div>
            <h2>Visión de tu operación</h2>
            <p>Resultados registrados y estado de tu estación de inspección.</p>
          </div>
        </div>
        <a className="button primary" href="#inspeccion">
          Abrir estación <ArrowUpRight size={16} />
        </a>
      </div>
      <Metrics stats={stats} />
      <div className="two-columns wide-left">
        <Panel
          title="Actividad de inspección"
          detail="Evolución de las capturas registradas"
        >
          <Trend buckets={buckets} period="minuto" />
        </Panel>
        <Panel
          title="Distribución de defectos"
          detail="Frecuencia de detecciones por tipo"
        >
          <Distribution data={stats?.defect_distribution || {}} />
        </Panel>
      </div>
      <Panel
        title="Actividad reciente"
        detail="Las últimas 5 inspecciones registradas"
        action={
          <a className="text-link" href="#historial">
            Ver historial <ArrowUpRight size={15} />
          </a>
        }
      >
        <HistoryTable rows={rows.slice(0, 5)} onSelect={onSelect} />
      </Panel>
      <div className="system-strip">
        <span>
          <i className={`dot ${runtime?.model_loaded ? "teal" : "warn"}`} />
          {runtime?.model_loaded ? "Modelo cargado" : "Modelo no disponible"}
        </span>
        <span>
          {runtime?.cuda_available
            ? runtime.gpus[0]?.name
            : "Inferencia por CPU"}
        </span>
        <span>
          Registros históricos sin verificar: {num(stats?.pass_count)}
        </span>
      </div>
    </>
  );
}
