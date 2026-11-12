import type { Bucket, Stats } from "../types";
import { Distribution, Trend } from "../components/Charts";
import { Panel } from "../components/Common";
import { Metrics } from "./Overview";
import { num, severityName } from "../format";
export function Statistics({
  stats,
  buckets,
  period,
  setPeriod,
}: {
  stats?: Stats;
  buckets: Bucket[];
  period: number;
  setPeriod: (n: number) => void;
}) {
  return (
    <>
      <Metrics stats={stats} />
      <Panel
        title="Inspecciones por periodo"
        detail="Conteos de capturas registradas, no de fotogramas"
        action={
          <label className="inline-label">
            Agrupar por
            <select
              value={period}
              onChange={(e) => setPeriod(Number(e.target.value))}
            >
              <option value="60">Minuto</option>
              <option value="3600">Hora</option>
              <option value="86400">Día</option>
            </select>
          </label>
        }
      >
        <Trend
          buckets={buckets}
          period={period === 60 ? "minuto" : period === 3600 ? "hora" : "día"}
        />
      </Panel>
      <div className="two-columns">
        <Panel
          title="Frecuencia por tipo"
          detail="Una inspección puede aportar varias detecciones"
        >
          <Distribution data={stats?.defect_distribution || {}} />
        </Panel>
        <Panel
          title="Severidad orientativa"
          detail="Inspecciones agrupadas por su severidad general"
        >
          <div className="severity-chart">
            {["MINOR", "MAJOR", "CRITICAL"].map((level) => {
              const count = stats?.severity_distribution[level] || 0;
              const max = Math.max(
                1,
                ...Object.values(stats?.severity_distribution || {}),
              );
              return (
                <div key={level}>
                  <div>
                    <span>{severityName(level)}</span>
                    <strong>{num(count)}</strong>
                  </div>
                  <div className={`severity-track ${level.toLowerCase()}`}>
                    <span style={{ width: `${(count / max) * 100}%` }} />
                  </div>
                </div>
              );
            })}
          </div>
          <p className="microcopy">
            Estimación por confianza y área detectada. No mide profundidad ni
            resistencia de la pieza.
          </p>
          <div className="stat-footnote">
            <strong>{num(stats?.defect_rate, 1)}%</strong>
            <p>
              de las inspecciones registradas tienen hallazgos. No representa la
              precisión del modelo.
            </p>
          </div>
        </Panel>
      </div>
    </>
  );
}
