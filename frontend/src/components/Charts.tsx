import type { Bucket } from "../types";
import { defectName, num } from "../format";
import { Empty } from "./Common";
export function Distribution({ data }: { data: Record<string, number> }) {
  const entries = Object.entries(data).sort((a, b) => b[1] - a[1]);
  if (!entries.length)
    return (
      <Empty title="Aún no hay detecciones">
        La distribución aparecerá después de registrar hallazgos.
      </Empty>
    );
  const total = entries.reduce((sum, [, v]) => sum + v, 0);
  return (
    <div className="distribution">
      {entries.map(([key, value], i) => (
        <div className="distribution-row" key={key}>
          <div>
            <span>
              <i style={{ opacity: 1 - i * 0.1 }} />
              {defectName(key)}
            </span>
            <strong>
              {num(value)}
              <small>{num((value / total) * 100, 1)}%</small>
            </strong>
          </div>
          <div className="bar-track">
            <div
              style={{
                width: `${(value / entries[0][1]) * 100}%`,
                opacity: 1 - i * 0.1,
              }}
            />
          </div>
        </div>
      ))}
      <p className="microcopy">
        {num(total)} detecciones registradas. Una inspección puede contener
        varias.
      </p>
    </div>
  );
}
export function Trend({
  buckets,
  period,
}: {
  buckets: Bucket[];
  period: string;
}) {
  if (buckets.length < 2)
    return (
      <Empty title="Faltan datos para la tendencia">
        Se necesitan inspecciones en al menos dos intervalos.
      </Empty>
    );
  const max = Math.max(
    1,
    ...buckets.map((b) => Math.max(b.fail, b.no_detections, b.pass)),
  );
  const x = (i: number) => 45 + (i * 585) / (buckets.length - 1);
  const y = (n: number) => 180 - (n / max) * 145;
  const path = (key: "fail" | "no_detections" | "pass") =>
    buckets.map((b, i) => `${i ? "L" : "M"}${x(i)},${y(b[key])}`).join(" ");
  return (
    <div className="trend-chart">
      <div className="chart-legend">
        <span>
          <i className="dot warn" />
          Con hallazgos
        </span>
        <span>
          <i className="dot teal" />
          Sin detecciones
        </span>
        {buckets.some((b) => b.pass > 0) && (
          <span>
            <i className="dot muted-dot" />
            Histórico sin verificar
          </span>
        )}
      </div>
      <svg
        viewBox="0 0 660 220"
        role="img"
        aria-label={`Inspecciones por ${period}. Horarios UTC.`}
      >
        {Array.from(
          new Set([0, 0.25, 0.5, 0.75, 1].map((r) => Math.round(max * r))),
        ).map((value) => (
          <g key={value}>
            <line
              x1="45"
              x2="630"
              y1={y(value)}
              y2={y(value)}
              className="chart-grid"
            />
            <text x="28" y={y(value) + 4} textAnchor="end">
              {num(value)}
            </text>
          </g>
        ))}
        <path d={path("fail")} className="line-warn" />
        <path d={path("no_detections")} className="line-teal" />
        {buckets.some((b) => b.pass > 0) && (
          <path d={path("pass")} className="line-muted" />
        )}
        {buckets.map((b, i) => (
          <g key={i}>
            <circle cx={x(i)} cy={y(b.fail)} r="3" className="point-warn">
              <title>
                {b.time} UTC: {b.fail} con hallazgos
              </title>
            </circle>
            <circle
              cx={x(i)}
              cy={y(b.no_detections)}
              r="3"
              className="point-teal"
            >
              <title>
                {b.time} UTC: {b.no_detections} sin detecciones
              </title>
            </circle>
            {(i === 0 ||
              i === buckets.length - 1 ||
              i === Math.floor(buckets.length / 2)) && (
              <text x={x(i)} y="207" textAnchor="middle">
                {b.time}
              </text>
            )}
          </g>
        ))}
      </svg>
      <p className="microcopy">
        Inspecciones por {period}. Últimos intervalos con actividad; horario UTC
        del servidor. Los huecos temporales no se representan a escala.
      </p>
    </div>
  );
}
