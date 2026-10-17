"""Reportes en JSON, CSV y PDF."""

import uuid

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse, Response

from backend.reports import report_payload, to_csv, to_pdf

TYPES = ("analisis", "calidad", "anomalias", "ejecucion")
FORMATS = ("json", "csv", "pdf")


def register(ctx):
    app, store, current, body = ctx.app, ctx.store, ctx.current, ctx.body
    act = ctx.act
    ai_context_for = ctx.ai_context_for
    ai = ctx.ai

    @app.get("/api/reports")
    def reports_list(
        request: Request,
        project_id: str = "",
        dataset_id: str = "",
        type: str = "",
    ):
        current(request)
        where, params = [], []
        if project_id:
            where.append("project_id = %s")
            params.append(project_id)
        if dataset_id:
            where.append("dataset_id = %s")
            params.append(dataset_id)
        if type in TYPES:
            where.append("type = %s")
            params.append(type)
        clause = ("WHERE " + " AND ".join(where)) if where else ""
        return store.all(
            "SELECT r.*, u.name AS author FROM reports r"
            " LEFT JOIN users u ON u.id = r.created_by"
            f" {clause} ORDER BY r.created_at DESC LIMIT 100",
            tuple(params),
        )

    @app.post("/api/reports")
    async def reports_create(request: Request):
        user = current(request)
        v = await body(request)
        dataset_id = v.get("dataset_id")
        project_id = v.get("project_id")
        run_id = v.get("run_id")
        rtype = str(v.get("type", "analisis"))
        fmt = str(v.get("format", "json"))
        if rtype not in TYPES:
            raise HTTPException(400, "Tipo inválido.")
        if fmt not in FORMATS:
            raise HTTPException(400, "Formato: json, csv o pdf.")
        if not dataset_id or not store.one(
            "SELECT id FROM datasets WHERE id = %s", (dataset_id,)
        ):
            raise HTTPException(404, "Selecciona un dataset existente.")

        d, ai_ctx, prof, qual, anoms, rows = ai_context_for(dataset_id, project_id)
        if run_id:
            run = store.one("SELECT * FROM runs WHERE id = %s", (run_id,))
        else:
            run = store.one(
                "SELECT * FROM runs WHERE dataset_id = %s"
                " AND status = 'completed' ORDER BY finished_at DESC LIMIT 1",
                (dataset_id,),
            )
        if rtype == "ejecucion" and not run:
            raise HTTPException(404, "Sin ejecuciones. Ejecuta primero.")

        payload = report_payload(
            {"name": _project_name(store, d.get("project_id") or project_id)},
            d,
            run,
            prof,
            qual,
            anoms,
            ai.recommendations(ai_ctx),
            ai.summary_text(ai_ctx),
            rtype,
        )
        payload["fecha"] = ctx.now()
        payload["usuario"] = user.get("name", user.get("username"))

        rid = "rep_" + uuid.uuid4().hex[:10]
        store.run(
            "INSERT INTO reports (id, project_id, dataset_id, run_id, type,"
            " format, title, content_json, created_by, created_at)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                rid,
                d.get("project_id") or project_id,
                dataset_id,
                (run or {}).get("id"),
                rtype,
                fmt,
                f"Reporte {rtype} — {d['filename']}",
                _json(payload),
                user["id"],
                ctx.now(),
            ),
        )
        act(
            user,
            "reporte_generado",
            "report",
            rid,
            d.get("project_id"),
            f"{rtype}/{fmt}",
        )
        return {"id": rid, "payload": payload}

    @app.get("/api/reports/{rid}")
    def reports_get(rid: str, request: Request):
        current(request)
        r = store.one("SELECT * FROM reports WHERE id = %s", (rid,))
        if not r:
            raise HTTPException(404, "Reporte no encontrado.")
        r["payload"] = _load_payload(r)
        return r

    @app.get("/api/reports/{rid}/download")
    def reports_download(rid: str, request: Request):
        current(request)
        r = store.one("SELECT * FROM reports WHERE id = %s", (rid,))
        if not r:
            raise HTTPException(404, "Reporte no encontrado.")
        payload = _load_payload(r)
        fmt = (r.get("format") or "json").lower()
        fname = f"reporte_{rid[:8]}"
        if fmt == "csv":
            return Response(
                to_csv(payload),
                media_type="text/csv; charset=utf-8",
                headers={"Content-Disposition": f'attachment; filename="{fname}.csv"'},
            )
        if fmt == "pdf":
            try:
                data = to_pdf(payload)
            except ValueError as exc:
                raise HTTPException(500, str(exc))
            return Response(
                data,
                media_type="application/pdf",
                headers={"Content-Disposition": f'attachment; filename="{fname}.pdf"'},
            )
        return JSONResponse(payload)


def _project_name(store, project_id):
    row = store.one(
        "SELECT name FROM projects WHERE id = %s", (project_id or "p_default",)
    )
    return (row or {}).get("name", "Proyecto")


def _load_payload(row):
    import json

    try:
        return json.loads(row.get("content_json") or "{}")
    except (ValueError, TypeError):
        return {}


def _json(payload):
    import json

    return json.dumps(payload, ensure_ascii=False)
