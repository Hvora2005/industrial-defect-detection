import { useEffect, useMemo, useRef, useState } from "react";
import {
  ChevronLeft,
  ChevronRight,
  Download,
  ImageOff,
  Search,
  X,
} from "lucide-react";
import {
  Badge,
  Empty,
  ErrorNotice,
  HistoryTable,
  Loading,
  Panel,
} from "../components/Common";
import {
  dateTime,
  defectName,
  filterHistory,
  num,
  severityName,
} from "../format";
import type { HistoryRow } from "../types";

export function HistoryDetail({
  row,
  onClose,
}: {
  row: HistoryRow;
  onClose: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    dialog.current?.showModal();
  }, []);
  return (
    <dialog
      className="detail-dialog"
      ref={dialog}
      onCancel={onClose}
      onClose={onClose}
      aria-labelledby="detail-title"
    >
      <header>
        <div>
          <p className="muted">Detalle de inspección</p>
          <h2 id="detail-title">
            Inspección #{String(row.id).padStart(4, "0")}
          </h2>
        </div>
        <button
          autoFocus
          className="icon-button"
          onClick={onClose}
          aria-label="Cerrar detalle"
        >
          <X size={20} />
        </button>
      </header>
      <Badge status={row.status} />
      <dl className="detail-grid">
        <div>
          <dt>Fecha y hora local</dt>
          <dd>{dateTime(row.timestamp)}</dd>
        </div>
        <div>
          <dt>Hallazgo principal</dt>
          <dd>{defectName(row.primary_defect)}</dd>
        </div>
        <div>
          <dt>Zonas señaladas</dt>
          <dd>{row.defects_found}</dd>
        </div>
        <div>
          <dt>Confianza principal</dt>
          <dd>
            {num(row.primary_confidence, 1)}
            {row.primary_confidence != null ? "%" : ""}
          </dd>
        </div>
        <div>
          <dt>Severidad orientativa</dt>
          <dd>{severityName(row.severity)}</dd>
        </div>
        <div>
          <dt>Fuente / modelo utilizado</dt>
          <dd>No disponibles en este registro</dd>
        </div>
      </dl>
      <div className="unavailable-media">
        <ImageOff size={26} />
        <h3>Imágenes no vinculadas al historial</h3>
        <p>
          El servidor devuelve un resumen de esta inspección. No expone sus
          imágenes ni el detalle de cada detección. Las capturas de la sesión
          actual se pueden descargar desde Inspección en vivo.
        </p>
      </div>
      <p className="microcopy">
        Sin detecciones no equivale a una pieza aprobada. Los registros
        históricos de aprobación permanecen sin verificar.
      </p>
    </dialog>
  );
}
export function History({
  rows,
  loading,
  error,
  limit,
  setLimit,
  reload,
  onSelect,
}: {
  rows: HistoryRow[];
  loading: boolean;
  error: string;
  limit: number;
  setLimit: (n: number) => void;
  reload: () => void;
  onSelect: (r: HistoryRow) => void;
}) {
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [page, setPage] = useState(0);
  const filtered = useMemo(
    () => filterHistory(rows, search, status, from, to),
    [rows, search, status, from, to],
  );
  useEffect(() => setPage(0), [search, status, from, to, limit]);
  const pages = Math.max(1, Math.ceil(filtered.length / 15));
  const current = Math.min(page, pages - 1);
  return (
    <Panel
      title="Registro de inspecciones"
      detail="Consulta resultados y revisa cada hallazgo"
      action={
        <div className="button-row">
          <a className="button secondary" href="/export/csv">
            <Download size={15} />
            CSV
          </a>
          <a className="button secondary" href="/export/pdf">
            <Download size={15} />
            PDF
          </a>
        </div>
      }
    >
      <div className="history-filters">
        <label className="search-field">
          <Search size={17} />
          <input
            aria-label="Buscar inspecciones"
            placeholder="Buscar por ID, defecto o resultado…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </label>
        <label>
          Resultado
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">Todos</option>
            <option value="FAIL">Con hallazgos</option>
            <option value="NO_DETECTIONS">Sin detecciones</option>
            <option value="PASS">Histórico sin verificar</option>
          </select>
        </label>
        <label>
          Desde
          <input
            type="date"
            value={from}
            onChange={(e) => setFrom(e.target.value)}
          />
        </label>
        <label>
          Hasta
          <input
            type="date"
            value={to}
            onChange={(e) => setTo(e.target.value)}
          />
        </label>
      </div>
      {from && to && from > to && (
        <ErrorNotice message="La fecha inicial debe ser anterior o igual a la fecha final." />
      )}
      <div className="history-scope">
        <span>
          Filtros sobre los <strong>{rows.length}</strong> registros cargados ·
          fechas locales
        </span>
        <label>
          Cargar últimos
          <select
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
          >
            <option value="50">50 registros</option>
            <option value="100">100 registros</option>
            <option value="250">250 registros</option>
            <option value="500">500 registros</option>
          </select>
        </label>
      </div>
      {error && <ErrorNotice message={error} retry={reload} />}
      {loading ? (
        <Loading />
      ) : filtered.length ? (
        <HistoryTable
          rows={filtered.slice(current * 15, current * 15 + 15)}
          onSelect={onSelect}
        />
      ) : (
        <Empty title="Sin coincidencias">
          Cambia los filtros o registra una nueva inspección.
        </Empty>
      )}
      <div className="pagination">
        <span>
          {filtered.length} coincidencias · página {current + 1} de {pages}
        </span>
        <div className="button-row">
          <button
            className="icon-button"
            aria-label="Página anterior"
            disabled={current === 0}
            onClick={() => setPage(current - 1)}
          >
            <ChevronLeft size={18} />
          </button>
          <button
            className="icon-button"
            aria-label="Página siguiente"
            disabled={current >= pages - 1}
            onClick={() => setPage(current + 1)}
          >
            <ChevronRight size={18} />
          </button>
        </div>
      </div>
    </Panel>
  );
}
