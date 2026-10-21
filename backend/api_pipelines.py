"""Endpoints de pipelines: configuracion, estado e historial."""

import json
import time
import uuid

from fastapi import HTTPException, Request

from backend.settings import now


def register(ctx):
    """Registra los endpoints de pipelines en la app."""
    app, store, current, body = ctx.app, ctx.store, ctx.current, ctx.body

    @app.get("/api/pipelines")
    def pipelines_list(request: Request, project_id: str = "", search: str = ""):
        current(request)
        where, params = [], []
        if project_id:
            where.append("p.project_id = %s")
            params.append(project_id)
        if search:
            where.append("p.name LIKE %s")
            params.append(f"%{search[:60]}%")
        clause = ("WHERE " + " AND ".join(where)) if where else ""
        return store.all(
            "SELECT p.*, d.filename, pr.name AS project FROM pipelines p"
            " LEFT JOIN datasets d ON d.id = p.dataset_id"
            " LEFT JOIN projects pr ON pr.id = p.project_id"
            f" {clause} ORDER BY p.created_at",
            tuple(params),
        )

    @app.post("/api/pipelines")
    async def pipelines_create(request: Request):
        user = current(request, {"admin", "operator"})
        value = await body(request)
        name = str(value.get("name", "")).strip()
        description = str(value.get("description", "")).strip()
        if not name or len(name) > 80:
            raise HTTPException(400, "Nombre de 1 a 80 caracteres.")
        if len(description) > 500:
            raise HTTPException(400, "Descripción hasta 500.")
        project_id = value.get("project_id") or "p_default"
        if not store.one("SELECT id FROM projects WHERE id = %s", (project_id,)):
            project_id = "p_default"
        dataset_id = value.get("dataset_id") or None
        if dataset_id and not store.one(
            "SELECT id FROM datasets WHERE id = %s", (dataset_id,)
        ):
            raise HTTPException(404, "Selecciona un archivo existente.")
        steps = value.get("steps") or [
            "validar_estructura",
            "eliminar_duplicados",
            "tratar_nulos",
            "convertir_tipos",
            "ejecutar_reglas",
            "detectar_anomalias",
            "guardar_resultado",
        ]
        if not isinstance(steps, list) or not 1 <= len(steps) <= 12:
            raise HTTPException(400, "De 1 a 12 pasos.")
        pid = "p_" + uuid.uuid4().hex[:8]
        store.run(
            "INSERT INTO pipelines (id, name, description, dataset_id,"
            " interval_minutes, enabled, created_at, created_by,"
            " project_id, steps_json, status, run_count)"
            " VALUES (%s, %s, %s, %s, 0, 0, %s, %s, %s, %s, 'activo', 0)",
            (
                pid,
                name,
                description,
                dataset_id,
                now(),
                user["id"],
                project_id,
                json.dumps([str(s)[:60] for s in steps]),
            ),
        )
        store.audit(user["id"], "pipeline_created", pid)
        store.activity(
            user["id"],
            user.get("name", ""),
            "pipeline_creado",
            "pipeline",
            pid,
            project_id,
            name,
        )
        return {"id": pid, "name": name}

    @app.get("/api/pipelines/{pid}")
    def pipelines_get(pid: str, request: Request):
        current(request)
        row = store.one("SELECT * FROM pipelines WHERE id = %s", (pid,))
        if not row:
            raise HTTPException(404, "Pipeline no encontrado.")
        return row

    @app.post("/api/pipelines/{pid}")
    async def pipelines_update(pid: str, request: Request):
        user = current(request, {"admin", "operator"})
        value = await body(request)
        row = store.one("SELECT * FROM pipelines WHERE id = %s", (pid,))
        if not row:
            raise HTTPException(404, "Pipeline no encontrado.")
        dataset_id = value.get("dataset_id", row["dataset_id"])
        if dataset_id and not store.one(
            "SELECT id FROM datasets WHERE id = %s", (dataset_id,)
        ):
            raise HTTPException(404, "Archivo no encontrado.")
        interval = value.get("interval_minutes", row["interval_minutes"])
        if not isinstance(interval, int) or interval not in (0, 15, 60, 1440):
            raise HTTPException(400, "Frecuencia: 0, 15, 60 o 1440.")
        if interval and not dataset_id:
            raise HTTPException(400, "Frecuencia necesita archivo.")
        name = str(value.get("name", row["name"])).strip()[:80] or row["name"]
        description = str(value.get("description", row["description"] or ""))[:500]
        project_id = value.get("project_id", row.get("project_id") or "p_default")
        if project_id and not store.one(
            "SELECT id FROM projects WHERE id = %s", (project_id,)
        ):
            project_id = row.get("project_id") or "p_default"
        steps = value.get("steps", None)
        try:
            cur_steps = json.loads(row.get("steps_json") or "[]")
        except (ValueError, TypeError):
            cur_steps = []
        if steps is not None:
            if not isinstance(steps, list) or not 1 <= len(steps) <= 12:
                raise HTTPException(400, "De 1 a 12 pasos.")
            cur_steps = [str(s)[:60] for s in steps]
        store.run(
            "UPDATE pipelines SET name = %s, description = %s, dataset_id = %s,"
            " interval_minutes = %s, enabled = %s, next_run = %s,"
            " project_id = %s, steps_json = %s WHERE id = %s",
            (
                name,
                description,
                dataset_id,
                interval,
                int(interval > 0),
                time.time() + interval * 60 if interval else None,
                project_id,
                json.dumps(cur_steps),
                pid,
            ),
        )
        store.audit(user["id"], "pipeline_configured", pid)
        return {"message": "Pipeline actualizado."}

    @app.delete("/api/pipelines/{pid}")
    def pipelines_delete(pid: str, request: Request):
        user = current(request, {"admin", "operator"})
        if pid == "p_ventas":
            raise HTTPException(400, "El pipeline inicial no se elimina.")
        if not store.one("SELECT id FROM pipelines WHERE id = %s", (pid,)):
            raise HTTPException(404, "Pipeline no encontrado.")
        store.run("DELETE FROM pipelines WHERE id = %s", (pid,))
        store.audit(user["id"], "pipeline_deleted", pid)
        return {"message": "Pipeline eliminado."}

    @app.get("/api/pipelines/{pid}/history")
    def pipelines_history(pid: str, request: Request):
        current(request)
        items = store.all(
            "SELECT r.*, d.filename FROM runs r"
            " JOIN datasets d ON d.id = r.dataset_id"
            " WHERE r.pipeline_id = %s ORDER BY r.created_at DESC LIMIT 50",
            (pid,),
        )
        return {"total": len(items), "items": items}
