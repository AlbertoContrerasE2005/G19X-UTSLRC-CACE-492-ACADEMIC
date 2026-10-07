"""Generación de reportes (JSON/CSV/PDF local)."""
from __future__ import annotations
import csv
import io


def report_payload(project, dataset, run, profile, quality, anomalies, recommendations, summary, rtype="analisis") -> dict:
    return {
        "type": rtype,
        "project": (project or {}).get("name", "—") if project else "—",
        "dataset": (dataset or {}).get("filename", "—") if dataset else "—",
        "fecha": __import__("backend.core", fromlist=["now"]).now() if False else None,
        "registros": profile.get("row_count", 0) if profile else 0,
        "columnas": profile.get("column_count", 0) if profile else 0,
        "calidad": quality or {},
        "anomalias": anomalies or [],
        "recomendaciones": recommendations or "",
        "resumen": summary or "",
        "run": {"id": (run or {}).get("id"), "status": (run or {}).get("status"),
                "total": (run or {}).get("total"), "loaded": (run or {}).get("loaded"),
                "invalid": (run or {}).get("invalid"), "anomalies": (run or {}).get("anomalies")} if run else None,
    }


def to_csv(payload: dict) -> str:
    out = io.StringIO(newline="")
    w = csv.writer(out)
    w.writerow(["Sección", "Detalle"])
    w.writerow(["Proyecto", payload.get("project")])
    w.writerow(["Dataset", payload.get("dataset")])
    w.writerow(["Registros", payload.get("registros")])
    w.writerow(["Columnas", payload.get("columnas")])
    q = payload.get("calidad", {})
    w.writerow(["Calidad general", q.get("general")])
    for k in ("completitud", "unicidad", "validez", "consistencia"):
        w.writerow([f"Calidad {k}", q.get(k)])
    w.writerow([])
    w.writerow(["Problemas de calidad"])
    for i in (q.get("issues") or []):
        w.writerow([i.get("column"), i.get("problem")])
    w.writerow([])
    w.writerow(["Anomalías"])
    for a in (payload.get("anomalias") or [])[:100]:
        w.writerow([a.get("column_name", a.get("column", "")), a.get("value", ""), a.get("reason", "")])
    w.writerow([])
    w.writerow(["Resumen"])
    w.writerow([payload.get("resumen", "")])
    w.writerow(["Recomendaciones"])
    w.writerow([payload.get("recomendaciones", "")])
    return "\ufeff" + out.getvalue()


def to_pdf(payload: dict) -> bytes:
    """PDF simple con reportlab si está disponible; si no, lanza ValueError."""
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.pdfgen import canvas
    except ImportError as exc:
        raise ValueError("PDF no disponible: instala reportlab (pip install reportlab).") from exc
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4
    y = h - 20 * mm
    c.setFont("Helvetica-Bold", 16)
    c.drawString(15 * mm, y, "Reporte DataOps — " + str(payload.get("type", "analisis")).title())
    y -= 8 * mm
    c.setFont("Helvetica", 10)
    lines = [
        f"Proyecto: {payload.get('project')}",
        f"Dataset: {payload.get('dataset')}",
        f"Registros: {payload.get('registros')}  |  Columnas: {payload.get('columnas')}",
        f"Calidad general: {(payload.get('calidad') or {}).get('general', '—')}%",
    ]
    for ln in lines:
        c.drawString(15 * mm, y, ln[:110])
        y -= 5 * mm
    def block(title, text):
        nonlocal y
        y -= 3 * mm
        c.setFont("Helvetica-Bold", 11)
        c.drawString(15 * mm, y, title)
        y -= 5 * mm
        c.setFont("Helvetica", 9)
        for para in (text or "").split("\n"):
            while para:
                if y < 20 * mm:
                    c.showPage()
                    y = h - 20 * mm
                    c.setFont("Helvetica", 9)
                c.drawString(15 * mm, y, para[:115])
                para = para[115:]
                y -= 4 * mm
    q = payload.get("calidad", {})
    probs = "\n".join(f"- {i.get('column')}: {i.get('problem')}" for i in (q.get("issues") or [])[:20]) or "Sin problemas relevantes."
    anoms = "\n".join(f"- {a.get('column_name', a.get('column',''))}: {a.get('value','')} — {a.get('reason','')}" for a in (payload.get("anomalias") or [])[:20]) or "Sin anomalías."
    block("Resumen", payload.get("resumen", ""))
    block("Problemas de calidad", probs)
    block("Anomalías", anoms)
    block("Recomendaciones", payload.get("recomendaciones", ""))
    c.showPage()
    c.save()
    return buf.getvalue()
