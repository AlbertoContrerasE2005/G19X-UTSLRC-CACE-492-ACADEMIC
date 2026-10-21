"""Endpoints de ejecuciones: encolar, consultar, exportar y aprobar."""

import json
import uuid

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse, Response

from backend.data_io import csv_export
from backend.settings import COLUMNS, now


def register(ctx):
    """Registra los endpoints de runs en la app."""
    app, store, current, body = ctx.app, ctx.store, ctx.current, ctx.body

    @app.post("/api/runs")
    async def run(request: Request):
        user = current(request, {"admin", "operator"})
        value = await body(request)
        dataset_id = value.get("dataset_id")
        if not isinstance(dataset_id, str) or not store.one(
            "SELECT id FROM datasets WHERE id = %s", (dataset_id,)
        ):
            raise HTTPException(404, "Selecciona un archivo existente.")
        pipeline_id = value.get("pipeline_id") or "p_ventas"
        if not store.one("SELECT id FROM pipelines WHERE id = %s", (pipeline_id,)):
            raise HTTPException(404, "Pipeline no encontrado.")
        parent = value.get("parent_id")
        if parent:
            prev = store.one("SELECT * FROM runs WHERE id = %s", (parent,))
            if (
                not prev
                or prev["dataset_id"] != dataset_id
                or prev["status"] not in ("completed", "failed")
            ):
                raise HTTPException(400, "No se puede repetir ese run.")
        try:
            run_id = store.queue(
                dataset_id,
                user["id"],
                "retry" if parent else "manual",
                parent,
                pipeline_id,
            )
        except ValueError as exc:
            raise HTTPException(409, str(exc))
        return JSONResponse({"id": run_id, "status": "queued"}, status_code=202)

    @app.get("/api/runs")
    def runs(request: Request, status: str = "", offset: int = 0):
        current(request)
        if status and status not in ("queued", "running", "completed", "failed"):
            raise HTTPException(400, "Estado inválido.")
        offset = max(0, offset)
        where, params = ("WHERE r.status = %s", (status,)) if status else ("", ())
        items = store.all(
            f"SELECT r.*, d.filename FROM runs r"
            f" JOIN datasets d ON d.id = r.dataset_id {where}"
            f" ORDER BY r.created_at DESC LIMIT 50 OFFSET %s",
            params + (offset,),
        )
        total = store.one(f"SELECT COUNT(*) AS n FROM runs r {where}", params)["n"]
        return {"items": items, "total": total, "offset": offset}

    @app.get("/api/runs/{run_id}")
    def run_detail(run_id: str, request: Request, offset: int = 0, kind: str = "all"):
        current(request)
        record = store.one(
            "SELECT r.*, d.filename, d.columns_json FROM runs r"
            " JOIN datasets d ON d.id = r.dataset_id WHERE r.id = %s",
            (run_id,),
        )
        if not record:
            raise HTTPException(404, "Ejecución no encontrada.")
        try:
            record["columns"] = json.loads(record.pop("columns_json") or "[]")
        except (ValueError, TypeError):
            record["columns"] = COLUMNS
        if not record["columns"]:
            record["columns"] = COLUMNS
        record["logs"] = store.all(
            "SELECT created_at, stage, message FROM run_logs"
            " WHERE run_id = %s ORDER BY id",
            (run_id,),
        )
        record["approvals"] = store.all(
            "SELECT line, action, motivo, created_at FROM approvals"
            " WHERE run_id = %s ORDER BY id DESC LIMIT 50",
            (run_id,),
        )
        if kind == "issues":
            where = " AND status IN ('invalid', 'anomaly', 'rejected')"
        elif kind == "pending":
            where = " AND status = 'anomaly'"
        else:
            where = ""
        record["rows"] = store.all(
            "SELECT line, data_json, status, reason, score FROM run_rows"
            f" WHERE run_id = %s{where} ORDER BY line LIMIT 100 OFFSET %s",
            (run_id, max(0, offset)),
        )
        record["row_total"] = store.one(
            f"SELECT COUNT(*) AS n FROM run_rows WHERE run_id = %s{where}",
            (run_id,),
        )["n"]
        record["pending"] = store.one(
            "SELECT COUNT(*) AS n FROM run_rows"
            " WHERE run_id = %s AND status = 'anomaly'",
            (run_id,),
        )["n"]
        for item in record["rows"]:
            item["data"] = json.loads(item.pop("data_json"))
        return record

    @app.get("/api/runs/{run_id}/export")
    def export(run_id: str, request: Request, kind: str = "all"):
        current(request)
        record = store.one("SELECT status FROM runs WHERE id = %s", (run_id,))
        if not record:
            raise HTTPException(404, "Ejecución no encontrada.")
        if record["status"] != "completed":
            raise HTTPException(409, "Aún sin resultados.")
        if kind not in ("all", "issues", "accepted", "pending", "rejected"):
            raise HTTPException(400, "Tipo inválido.")
        where = {
            "all": "",
            "issues": " AND status IN ('invalid', 'anomaly', 'rejected')",
            "accepted": " AND status IN ('loaded', 'existing')",
            "pending": " AND status = 'anomaly'",
            "rejected": " AND status = 'rejected'",
        }[kind]
        rows = store.all(
            f"SELECT * FROM run_rows WHERE run_id = %s{where} ORDER BY line",
            (run_id,),
        )
        return Response(
            csv_export(rows),
            media_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="run_{run_id[:8]}_{kind}.csv"'
            },
        )

    @app.post("/api/runs/{run_id}/approve")
    async def approve(run_id: str, request: Request):
        user = current(request, {"admin", "operator"})
        value = await body(request)
        try:
            return store.review(
                run_id,
                value.get("lines", []),
                user["id"],
                user["name"],
                value.get("motivo", ""),
                "approved",
            )
        except ValueError as exc:
            raise HTTPException(400, str(exc))

    @app.post("/api/runs/{run_id}/reject")
    async def reject(run_id: str, request: Request):
        user = current(request, {"admin", "operator"})
        value = await body(request)
        try:
            return store.review(
                run_id,
                value.get("lines", []),
                user["id"],
                user["name"],
                value.get("motivo", ""),
                "rejected",
            )
        except ValueError as exc:
            raise HTTPException(400, str(exc))
