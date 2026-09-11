"""SQLite-backed inspection history, using SQLAlchemy."""

import datetime
import json
from pathlib import Path

from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker

DB_PATH = Path(__file__).resolve().parent.parent / "outputs" / "inspections.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class Inspection(Base):
    __tablename__ = "inspections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=lambda: datetime.datetime.now(datetime.timezone.utc))
    status = Column(String, nullable=False)          # "PASS" or "FAIL"
    defects_found = Column(Integer, nullable=False, default=0)
    primary_defect = Column(String, nullable=True)     # highest-confidence defect class, if any
    primary_confidence = Column(Float, nullable=True)  # its confidence, percentage
    severity = Column(String, nullable=True)            # overall worst severity: MINOR/MAJOR/CRITICAL
    all_defects_json = Column(String, nullable=False, default="[]")  # full defect list, JSON


Base.metadata.create_all(engine)


def save_inspection(result: dict) -> None:
    session = SessionLocal()
    try:
        defects = result.get("defects", [])
        top = defects[0] if defects else None
        record = Inspection(
            status=result["status"],
            defects_found=result["defects_found"],
            primary_defect=top["class_name"] if top else None,
            primary_confidence=top["confidence"] if top else None,
            severity=result.get("severity"),
            all_defects_json=json.dumps(defects),
        )
        session.add(record)
        session.commit()
    finally:
        session.close()


def get_recent_inspections(limit: int = 50) -> list[dict]:
    session = SessionLocal()
    try:
        rows = (
            session.query(Inspection)
            .order_by(Inspection.id.desc())
            .limit(limit)
            .all()
        )
        return [
            {
                "id": r.id,
                "timestamp": r.timestamp.isoformat() + "Z",
                "status": r.status,
                "defects_found": r.defects_found,
                "primary_defect": r.primary_defect,
                "primary_confidence": r.primary_confidence,
                "severity": r.severity,
            }
            for r in rows
        ]
    finally:
        session.close()


def get_stats() -> dict:
    session = SessionLocal()
    try:
        rows = session.query(Inspection).all()
        total = len(rows)
        pass_count = sum(1 for r in rows if r.status == "PASS")
        fail_count = total - pass_count

        defect_counts: dict[str, int] = {}
        for r in rows:
            if r.all_defects_json:
                for d in json.loads(r.all_defects_json):
                    name = d["class_name"]
                    defect_counts[name] = defect_counts.get(name, 0) + 1

        most_common = max(defect_counts, key=defect_counts.get) if defect_counts else None

        severity_counts = {"MINOR": 0, "MAJOR": 0, "CRITICAL": 0}
        for r in rows:
            if r.severity in severity_counts:
                severity_counts[r.severity] += 1

        # Average confidence across every individual defect detection (not
        # just the primary one per inspection) - the more complete picture
        # of how confident the model typically is.
        all_confidences = []
        for r in rows:
            if r.all_defects_json:
                for d in json.loads(r.all_defects_json):
                    all_confidences.append(d["confidence"])
        avg_confidence = round(sum(all_confidences) / len(all_confidences), 1) if all_confidences else None

        return {
            "total_inspected": total,
            "pass_count": pass_count,
            "fail_count": fail_count,
            "defect_rate": round((fail_count / total) * 100, 1) if total > 0 else 0.0,
            "most_common_defect": most_common,
            "defect_distribution": defect_counts,
            "severity_distribution": severity_counts,
            "avg_confidence": avg_confidence,
        }
    finally:
        session.close()


def get_trend(bucket_seconds: int = 60, limit_buckets: int = 15) -> list[dict]:
    """Buckets inspections into fixed time windows and counts PASS/FAIL per
    bucket, for the dashboard's inspection-trend-over-time chart."""
    session = SessionLocal()
    try:
        rows = session.query(Inspection).order_by(Inspection.timestamp.asc()).all()
        buckets: dict[int, dict] = {}
        for r in rows:
            ts = r.timestamp.replace(tzinfo=datetime.timezone.utc).timestamp()
            bucket_key = int(ts // bucket_seconds) * bucket_seconds
            bucket = buckets.setdefault(bucket_key, {"pass": 0, "fail": 0})
            if r.status == "PASS":
                bucket["pass"] += 1
            else:
                bucket["fail"] += 1

        sorted_keys = sorted(buckets.keys())[-limit_buckets:]
        return [
            {
                "time": datetime.datetime.fromtimestamp(k, tz=datetime.timezone.utc).strftime("%H:%M"),
                "pass": buckets[k]["pass"],
                "fail": buckets[k]["fail"],
            }
            for k in sorted_keys
        ]
    finally:
        session.close()
