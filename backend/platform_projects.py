"""Proyectos y análisis de datasets (perfil, calidad, filas paginadas)."""

import uuid

from fastapi import HTTPException, Request

from backend.profiling import profile_dataset, quality_score


def register(ctx):
    app, store, current, body = ctx.app, ctx.store, ctx.current, ctx.body
    act = ctx.act
    get_dataset_rows = ctx.get_dataset_rows

    # ---------- proyectos ----------

    @app.get("/api/projects")
    def projects_list(
        request: Request,
        search: str = "",
        status: str = "",
        offset: int = 0,
        limit: int = 50,
    ):
        current(request)
        limit = max(1, min(100, limit if isinstance(limit, int) else 50))
        offset = max(0, offset if isinstance(offset, int) else 0)
        where, params = [], []
        if search:
            where.append("(p.name LIKE %s OR p.description LIKE %s)")
            params += [f"%{search[:60]}%", f"%{search[:60]}%"]
        if status in ("activo", "archivado"):
            where.append("p.status = %s")
            params.append(status)
        clause = ("WHERE " + " AND ".join(where)) if where else ""
        rows = store.all(
            "SELECT p.*, u.name AS owner_name,"
            " (SELECT COUNT(*) FROM datasets d WHERE d.project_id = p.id) AS datasets,"
            " (SELECT COUNT(*) FROM pipelines pl WHERE pl.project_id = p.id) AS pipelines"
            " FROM projects p LEFT JOIN users u ON u.id = p.owner_id"
            f" {clause} ORDER BY p.created_at DESC LIMIT %s OFFSET %s",
            tuple(params) + (limit, offset),
        )
        total = store.one(
            f"SELECT COUNT(*) AS n FROM projects p {clause}", tuple(params)
        )["n"]
        return {"items": rows, "total": total, "offset": offset, "limit": limit}

    @app.post("/api/projects")
    async def projects_create(request: Request):
        user = current(request, {"admin", "operator"})
        v = await body(request)
        name = str(v.get("name", "")).strip()
        desc = str(v.get("description", "")).strip()
        if not name or len(name) > 120:
            raise HTTPException(400, "Nombre de 1 a 120 caracteres.")
        if len(desc) > 1000:
            raise HTTPException(400, "Descripción hasta 1000.")
        pid = "prj_" + uuid.uuid4().hex[:10]
        ts = ctx.now()
        store.run(
            "INSERT INTO projects (id, name, description, status, owner_id,"
            " created_at, updated_at) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (pid, name, desc, "activo", user["id"], ts, ts),
        )
        store.run(
            "INSERT IGNORE INTO project_members (project_id, user_id, role)"
            " VALUES (%s, %s, 'admin')",
            (pid, user["id"]),
        )
        act(user, "proyecto_creado", "project", pid, pid, f"Proyecto '{name}'")
        return {"id": pid, "name": name}

    @app.get("/api/projects/{pid}")
    def projects_get(pid: str, request: Request):
        current(request)
        p = store.one(
            "SELECT p.*, u.name AS owner_name FROM projects p"
            " LEFT JOIN users u ON u.id = p.owner_id WHERE p.id = %s",
            (pid,),
        )
        if not p:
            raise HTTPException(404, "Proyecto no encontrado.")
        return p

    @app.put("/api/projects/{pid}")
    async def projects_update(pid: str, request: Request):
        user = current(request, {"admin", "operator"})
        v = await body(request)
        p = store.one("SELECT * FROM projects WHERE id = %s", (pid,))
        if not p:
            raise HTTPException(404, "Proyecto no encontrado.")
        name = str(v.get("name", p["name"])).strip()[:120] or p["name"]
        desc = str(v.get("description", p["description"] or ""))[:1000]
        status = v.get("status", p["status"])
        if status not in ("activo", "archivado"):
            raise HTTPException(400, "Estado: activo o archivado.")
        store.run(
            "UPDATE projects SET name = %s, description = %s, status = %s,"
            " updated_at = %s WHERE id = %s",
            (name, desc, status, ctx.now(), pid),
        )
        act(user, "proyecto_actualizado", "project", pid, pid, name)
        return {"message": "Proyecto actualizado."}

    @app.delete("/api/projects/{pid}")
    def projects_delete(pid: str, request: Request):
        user = current(request, {"admin"})
        p = store.one("SELECT * FROM projects WHERE id = %s", (pid,))
        if not p:
            raise HTTPException(404, "Proyecto no encontrado.")
        if pid == "p_default":
            raise HTTPException(400, "El proyecto general no se elimina.")
        # Los datasets y pipelines quedan en el proyecto general.
        store.run(
            "UPDATE datasets SET project_id = 'p_default' WHERE project_id = %s",
            (pid,),
        )
        store.run(
            "UPDATE pipelines SET project_id = 'p_default' WHERE project_id = %s",
            (pid,),
        )
        store.run("DELETE FROM project_members WHERE project_id = %s", (pid,))
        store.run("DELETE FROM quality_rules WHERE project_id = %s", (pid,))
        store.run("DELETE FROM projects WHERE id = %s", (pid,))
        act(user, "proyecto_eliminado", "project", pid, None, p["name"])
        return {"message": "Eliminado. Datasets movidos al general."}

    @app.get("/api/projects/{pid}/summary")
    def projects_summary(pid: str, request: Request):
        current(request)
        p = store.one("SELECT * FROM projects WHERE id = %s", (pid,))
        if not p:
            raise HTTPException(404, "Proyecto no encontrado.")
        datasets = store.all(
            "SELECT id, filename, row_count, quality_score, created_at"
            " FROM datasets WHERE project_id = %s"
            " ORDER BY created_at DESC LIMIT 20",
            (pid,),
        )
        pipelines = store.all(
            "SELECT id, name, status, run_count, last_run FROM pipelines"
            " WHERE project_id = %s ORDER BY created_at",
            (pid,),
        )
        runs = store.one(
            "SELECT COUNT(*) AS n,"
            " COALESCE(SUM(r.status = 'completed'), 0) AS ok,"
            " COALESCE(SUM(r.status = 'failed'), 0) AS fail"
            " FROM runs r JOIN datasets d ON d.id = r.dataset_id"
            " WHERE d.project_id = %s",
            (pid,),
        )
        anoms = store.one(
            "SELECT COUNT(*) AS n FROM anomalies"
            " WHERE project_id = %s AND status = 'pendiente'",
            (pid,),
        )["n"]
        issues = store.one(
            "SELECT COUNT(*) AS n FROM quality_results WHERE project_id = %s",
            (pid,),
        )["n"]
        avg_q = store.one(
            "SELECT COALESCE(AVG(quality_score), 0) AS q FROM datasets"
            " WHERE project_id = %s",
            (pid,),
        )["q"]
        recent = store.all(
            "SELECT r.*, d.filename FROM runs r"
            " JOIN datasets d ON d.id = r.dataset_id"
            " WHERE d.project_id = %s ORDER BY r.created_at DESC LIMIT 8",
            (pid,),
        )
        return {
            "project": p,
            "datasets": datasets,
            "pipelines": pipelines,
            "runs": runs,
            "anomalies_pending": anoms,
            "quality_issues": issues,
            "quality_avg": round(avg_q or 0, 2),
            "recent_runs": recent,
        }

    # ---------- datasets: perfil, calidad, filas ----------

    @app.get("/api/datasets/{dataset_id}/profile")
    def dataset_profile(dataset_id: str, request: Request):
        current(request)
        d, columns, rows = get_dataset_rows(dataset_id)
        if not d:
            raise HTTPException(404, "Archivo no encontrado.")
        if not rows:
            raise HTTPException(400, "No se pudo procesar el archivo.")
        return profile_dataset(columns, rows)

    @app.get("/api/datasets/{dataset_id}/quality")
    def dataset_quality(dataset_id: str, request: Request):
        current(request)
        d, columns, rows = get_dataset_rows(dataset_id)
        if not d:
            raise HTTPException(404, "Archivo no encontrado.")
        if not rows:
            raise HTTPException(400, "No se pudo procesar el archivo.")
        return quality_score(columns, rows)

    @app.get("/api/datasets/{dataset_id}/rows")
    def dataset_rows(
        dataset_id: str,
        request: Request,
        offset: int = 0,
        limit: int = 50,
        search: str = "",
        sort: str = "",
        order: str = "asc",
    ):
        current(request)
        d, columns, rows = get_dataset_rows(dataset_id)
        if not d:
            raise HTTPException(404, "Archivo no encontrado.")
        limit = max(1, min(200, limit if isinstance(limit, int) else 50))
        offset = max(0, offset if isinstance(offset, int) else 0)
        if search:
            s = search.lower()[:100]
            rows = [
                r for r in rows if any(s in str(r.get(c, "")).lower() for c in columns)
            ]
        if sort in columns:
            rows = sorted(
                rows,
                key=lambda r: str(r.get(sort, "")),
                reverse=(order == "desc"),
            )
        return {
            "items": rows[offset : offset + limit],
            "total": len(rows),
            "offset": offset,
            "limit": limit,
            "columns": columns,
        }
