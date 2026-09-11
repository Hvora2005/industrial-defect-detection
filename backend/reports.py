"""CSV and PDF export of inspection history/stats (Phase 11)."""

import csv
import datetime
import io

from fpdf import FPDF

from database import get_recent_inspections, get_stats


def build_csv() -> str:
    inspections = get_recent_inspections(limit=100000)  # effectively "all"

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Timestamp (UTC)", "Status", "Severity", "Defects Found", "Primary Defect", "Confidence (%)"])
    for insp in inspections:
        writer.writerow([
            insp["id"],
            insp["timestamp"],
            insp["status"],
            insp.get("severity") or "",
            insp["defects_found"],
            insp["primary_defect"] or "",
            insp["primary_confidence"] if insp["primary_confidence"] is not None else "",
        ])
    return output.getvalue()


def build_pdf() -> bytes:
    stats = get_stats()
    inspections = get_recent_inspections(limit=30)

    pdf = FPDF()
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, "AI Industrial Inspection Report", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 9)
    generated_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    pdf.cell(0, 6, f"Generated: {generated_at}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # --- Summary ---
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Summary", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 6, f"Total Inspected: {stats['total_inspected']}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Pass: {stats['pass_count']}    Fail: {stats['fail_count']}", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Defect Rate: {stats['defect_rate']}%", new_x="LMARGIN", new_y="NEXT")
    pdf.cell(0, 6, f"Most Common Defect: {stats['most_common_defect'] or 'None'}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # --- Defect distribution ---
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Defect Distribution", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    distribution = sorted(stats["defect_distribution"].items(), key=lambda item: -item[1])
    if distribution:
        for name, count in distribution:
            pdf.cell(0, 6, f"{name}: {count}", new_x="LMARGIN", new_y="NEXT")
    else:
        pdf.cell(0, 6, "No defects logged yet.", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # --- Recent inspections table ---
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Recent Inspections", new_x="LMARGIN", new_y="NEXT")

    col_widths = [38, 18, 24, 45, 25]
    headers = ["Timestamp (UTC)", "Status", "Severity", "Defect", "Confidence"]

    pdf.set_font("Helvetica", "B", 9)
    for width, header in zip(col_widths, headers):
        pdf.cell(width, 7, header, border=1)
    pdf.ln()

    pdf.set_font("Helvetica", "", 9)
    for insp in inspections:
        confidence = f"{insp['primary_confidence']:.1f}%" if insp["primary_confidence"] is not None else "-"
        row = [
            insp["timestamp"][:19].replace("T", " "),
            insp["status"],
            insp.get("severity") or "-",
            insp["primary_defect"] or "-",
            confidence,
        ]
        for width, value in zip(col_widths, row):
            pdf.cell(width, 6, str(value), border=1)
        pdf.ln()

    return bytes(pdf.output())
