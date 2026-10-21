"""Endpoints de archivos: carga, listado, perfil y ejemplo."""

import base64
import json
import uuid

from fastapi import HTTPException, Request
from fastapi.responses import FileResponse

from backend.data_io import (
    parse_csv_dynamic,
    parse_excel_dynamic,
    parse_sql_dynamic,
    rows_to_csv,
)
from backend.settings import COLUMNS, now


def register(ctx):
    """Registra los endpoints de datasets en la app."""
    app, store, current, body = ctx.app, ctx.store, ctx.current, ctx.body

    def add_dataset(filename, content, user, content_b64=None, project_id=None):
        if not isinstance(filename, str) or len(filename) > 150:
            raise HTTPException(400, "Nombre hasta 150 caracteres.")
        low = filename.lower()
        if low.endswith(".xlsx"):
            if not isinstance(content_b64, str) or not content_b64:
                raise HTTPException(400, "Excel inválido.")
            try:
                raw = base64.b64decode(content_b64, validate=True)
            except Exception:
                raise HTTPException(400, "Excel no decodificable.")
            try:
                columns, rows = parse_excel_dynamic(raw)
                content = rows_to_csv(columns, rows)
            except ValueError as exc:
                raise HTTPException(400, str(exc))
        elif low.endswith(".csv"):
            if not isinstance(content, str):
                raise HTTPException(400, "CSV inválido.")
            try:
                columns, rows = parse_csv_dynamic(content)
                content = rows_to_csv(columns, rows)
            except ValueError as exc:
                raise HTTPException(400, str(exc))
        elif low.endswith(".sql"):
            if not isinstance(content, str):
                raise HTTPException(400, "SQL inválido.")
            try:
                from backend.core import parse_sql_dynamic

                columns, rows = parse_sql_dynamic(content)
                content = rows_to_csv(columns, rows)
            except ValueError as exc:
                raise HTTPException(400, str(exc))
        else:
            raise HTTPException(400, "Solo .csv, .xlsx y .sql.")
        dataset_id = uuid.uuid4().hex
        filename = filename.replace("\\", "/").split("/")[-1]
        pid = (
            project_id
            if isinstance(project_id, str)
            and store.one("SELECT id FROM projects WHERE id = %s", (project_id,))
            else "p_default"
        )
        ftype = (
            "xlsx"
            if low.endswith(".xlsx")
            else ("sql" if low.endswith(".sql") else "csv")
        )
        try:
            from backend.profiling import quality_score as _qual

            _qs = (_qual(columns, rows) or {}).get("general", 0)
        except Exception:
            _qs = 0
        store.run(
            "INSERT INTO datasets"
            " (id, filename, content, columns_json, row_count,"
            " created_at, created_by, project_id, file_type, quality_score)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                dataset_id,
                filename,
                content,
                json.dumps(columns),
                len(rows),
                now(),
                user["id"],
                pid,
                ftype,
                _qs,
            ),
        )
        store.audit(user["id"], "dataset_uploaded", dataset_id)
        store.activity(
            user["id"],
            user.get("name", user.get("username", "")),
            "dataset_cargado",
            "dataset",
            dataset_id,
            pid,
            f"{filename} ({len(rows)} registros)",
        )
        return {
            "id": dataset_id,
            "filename": filename,
            "row_count": len(rows),
            "columns": columns,
            "preview": rows[:8],
            "project_id": pid,
            "quality_score": _qs,
        }

    @app.get("/api/datasets")
    def datasets(
        request: Request,
        search: str = "",
        project_id: str = "",
        offset: int = 0,
        limit: int = 100,
    ):
        current(request)
        where, params = [], []
        if search:
            where.append("(d.filename LIKE %s)")
            params.append(f"%{search[:80]}%")
        if project_id:
            where.append("d.project_id = %s")
            params.append(project_id)
        clause = ("WHERE " + " AND ".join(where)) if where else ""
        limit = max(1, min(200, limit if isinstance(limit, int) else 100))
        offset = max(0, offset if isinstance(offset, int) else 0)
        rows = store.all(
            "SELECT d.id, d.filename, d.row_count, d.created_at,"
            " d.columns_json, d.project_id, d.quality_score, d.file_type,"
            " p.name AS project FROM datasets d"
            " LEFT JOIN projects p ON p.id = d.project_id"
            f" {clause} ORDER BY d.created_at DESC LIMIT %s OFFSET %s",
            tuple(params) + (limit, offset),
        )
        for r in rows:
            try:
                r["columns"] = json.loads(r.pop("columns_json") or "[]")
            except (ValueError, TypeError):
                r["columns"] = []
        return rows

    @app.post("/api/datasets")
    async def upload(request: Request):
        user = current(request, {"admin", "operator"})
        value = await body(request)
        return add_dataset(
            value.get("filename"),
            value.get("content"),
            user,
            value.get("content_b64"),
            value.get("project_id"),
        )

    @app.delete("/api/datasets/{dataset_id}")
    def dataset_delete(dataset_id: str, request: Request):
        user = current(request, {"admin", "operator"})
        d = store.one("SELECT * FROM datasets WHERE id = %s", (dataset_id,))
        if not d:
            raise HTTPException(404, "Archivo no encontrado.")
        if store.one(
            "SELECT COUNT(*) AS n FROM runs"
            " WHERE dataset_id = %s AND status IN ('queued', 'running')",
            (dataset_id,),
        )["n"]:
            raise HTTPException(409, "Tiene ejecuciones en curso.")
        for r in store.all("SELECT id FROM runs WHERE dataset_id = %s", (dataset_id,)):
            rid = r["id"]
            store.run("DELETE FROM run_rows WHERE run_id = %s", (rid,))
            store.run("DELETE FROM run_logs WHERE run_id = %s", (rid,))
            store.run("DELETE FROM approvals WHERE run_id = %s", (rid,))
            store.run("DELETE FROM quality_results WHERE run_id = %s", (rid,))
            store.run("DELETE FROM anomalies WHERE run_id = %s", (rid,))
            store.run("DELETE FROM sales WHERE source_run = %s", (rid,))
            store.run("DELETE FROM records WHERE run_id = %s", (rid,))
            store.run("UPDATE reports SET run_id = NULL WHERE run_id = %s", (rid,))
            store.run("DELETE FROM runs WHERE id = %s", (rid,))
        store.run(
            "UPDATE reports SET dataset_id = NULL WHERE dataset_id = %s", (dataset_id,)
        )
        store.run("DELETE FROM quality_results WHERE dataset_id = %s", (dataset_id,))
        store.run("DELETE FROM anomalies WHERE dataset_id = %s", (dataset_id,))
        store.run("DELETE FROM quality_rules WHERE dataset_id = %s", (dataset_id,))
        store.run("DELETE FROM datasets WHERE id = %s", (dataset_id,))
        store.audit(user["id"], "dataset_deleted", dataset_id)
        return {"message": "Archivo eliminado."}

    @app.get("/api/datasets/{dataset_id}")
    def dataset_detail(dataset_id: str, request: Request):
        current(request)
        d = store.one("SELECT * FROM datasets WHERE id = %s", (dataset_id,))
        if not d:
            raise HTTPException(404, "Archivo no encontrado.")
        content = d.pop("content")
        try:
            columns = json.loads(d.get("columns_json") or "[]") or COLUMNS
        except (ValueError, TypeError):
            columns = COLUMNS
        d["columns"] = columns
        _, rows = parse_csv_dynamic(content)
        d["preview"] = rows[:8]
        return d

    @app.post("/api/demo")
    def demo(request: Request):
        from pathlib import Path as _P

        user = current(request, {"admin", "operator"})
        base = _P(__file__).resolve().parents[1]
        text = (base / "examples" / "ventas_ejemplo.csv").read_text(encoding="utf-8")
        return add_dataset("ventas_ejemplo.csv", text, user)

    @app.get("/api/template")
    def template(request: Request):
        """Descarga la plantilla CSV de ejemplo."""
        current(request)
        from pathlib import Path as _P

        path = _P(__file__).resolve().parents[1] / "examples" / "plantilla.csv"
        return FileResponse(path, filename="plantilla.csv", media_type="text/csv")
