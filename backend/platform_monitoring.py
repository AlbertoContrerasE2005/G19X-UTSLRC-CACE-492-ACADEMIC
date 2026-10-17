"""Alertas, actividad, dashboard y monitoreo de pipelines."""

from fastapi import Request


def register(ctx):
    app, store, current = ctx.app, ctx.store, ctx.current

    # ---------- alertas ----------

    @app.get("/api/alerts")
    def alerts_list(
        request: Request,
        level: str = "",
        unread: str = "",
        offset: int = 0,
        limit: int = 50,
    ):
        current(request)
        where, params = [], []
        if level in ("info", "advertencia", "error", "critico"):
            where.append("level = %s")
            params.append(level)
        if unread in ("1", "true"):
            where.append("`read` = 0")
        clause = ("WHERE " + " AND ".join(where)) if where else ""
        limit = max(1, min(200, limit if isinstance(limit, int) else 50))
        offset = max(0, offset if isinstance(offset, int) else 0)
        items = store.all(
            f"SELECT * FROM alerts {clause}"
            " ORDER BY created_at DESC LIMIT %s OFFSET %s",
            tuple(params) + (limit, offset),
        )
        total = store.one(f"SELECT COUNT(*) AS n FROM alerts {clause}", tuple(params))[
            "n"
        ]
        unread_n = store.one("SELECT COUNT(*) AS n FROM alerts WHERE `read` = 0")["n"]
        return {
            "items": items,
            "total": total,
            "unread": unread_n,
            "offset": offset,
        }

    @app.post("/api/alerts/{aid}/read")
    def alerts_read(aid: int, request: Request):
        current(request)
        store.run("UPDATE alerts SET `read` = 1 WHERE id = %s", (aid,))
        return {"message": "Leída."}

    @app.post("/api/alerts/read-all")
    def alerts_read_all(request: Request):
        current(request)
        store.run("UPDATE alerts SET `read` = 1 WHERE `read` = 0")
        return {"message": "Todas leídas."}

    @app.delete("/api/alerts/{aid}")
    def alerts_delete(aid: int, request: Request):
        current(request, {"admin"})
        store.run("DELETE FROM alerts WHERE id = %s", (aid,))
        return {"message": "Alerta eliminada."}

    # ---------- actividad ----------

    @app.get("/api/activity")
    def activity_list(
        request: Request,
        search: str = "",
        action: str = "",
        project_id: str = "",
        offset: int = 0,
        limit: int = 50,
    ):
        current(request)
        where, params = [], []
        if search:
            where.append(
                "(username LIKE %s OR action LIKE %s OR detail LIKE %s"
                " OR entity_id LIKE %s)"
            )
            params += [f"%{search[:60]}%"] * 4
        if action:
            where.append("action = %s")
            params.append(action[:80])
        if project_id:
            where.append("project_id = %s")
            params.append(project_id)
        clause = ("WHERE " + " AND ".join(where)) if where else ""
        limit = max(1, min(200, limit if isinstance(limit, int) else 50))
        offset = max(0, offset if isinstance(offset, int) else 0)
        items = store.all(
            f"SELECT * FROM activity_logs {clause}"
            " ORDER BY created_at DESC LIMIT %s OFFSET %s",
            tuple(params) + (limit, offset),
        )
        total = store.one(
            f"SELECT COUNT(*) AS n FROM activity_logs {clause}", tuple(params)
        )["n"]
        return {
            "items": items,
            "total": total,
            "offset": offset,
            "limit": limit,
        }

    # ---------- dashboard ----------

    @app.get("/api/dashboard")
    def dashboard(request: Request, project_id: str = ""):
        current(request)
        wf = "WHERE d.project_id = %s" if project_id else ""
        pp = (project_id,) if project_id else ()

        projects = store.one("SELECT COUNT(*) AS n FROM projects")["n"]
        datasets = store.one(f"SELECT COUNT(*) AS n FROM datasets d {wf}", pp)["n"]
        records = store.one(
            f"SELECT COALESCE(SUM(row_count), 0) AS n FROM datasets d {wf}", pp
        )["n"]
        runs = store.one(
            "SELECT COUNT(*) AS n,"
            " COALESCE(SUM(CASE WHEN r.status = 'completed' THEN 1 ELSE 0 END), 0) AS ok,"
            " COALESCE(SUM(CASE WHEN r.status = 'failed' THEN 1 ELSE 0 END), 0) AS fail"
            f" FROM runs r JOIN datasets d ON d.id = r.dataset_id {wf}",
            pp,
        )
        issues = store.one(
            "SELECT COUNT(*) AS n FROM quality_results q"
            + (" WHERE q.project_id = %s" if project_id else ""),
            pp,
        )["n"]
        anoms = store.one(
            "SELECT COUNT(*) AS n FROM anomalies WHERE status = 'pendiente'"
            + (" AND project_id = %s" if project_id else ""),
            pp,
        )["n"]
        avg_q = store.one(
            f"SELECT COALESCE(AVG(quality_score), 0) AS q FROM datasets d {wf}", pp
        )["q"]
        recent_alerts = store.all(
            "SELECT * FROM alerts ORDER BY created_at DESC LIMIT 6"
        )
        latest_files = store.all(
            "SELECT d.id, d.filename, d.row_count, d.quality_score,"
            " d.created_at, p.name AS project FROM datasets d"
            " LEFT JOIN projects p ON p.id = d.project_id"
            f" {wf} ORDER BY d.created_at DESC LIMIT 8",
            pp,
        )
        by_status = store.all(
            "SELECT r.status, COUNT(*) AS n FROM runs r"
            f" JOIN datasets d ON d.id = r.dataset_id {wf} GROUP BY r.status",
            pp,
        )
        per_day = store.all(
            "SELECT DATE(r.created_at) AS day, COUNT(*) AS n FROM runs r"
            f" JOIN datasets d ON d.id = r.dataset_id {wf}"
            " GROUP BY day ORDER BY day DESC LIMIT 14",
            pp,
        )
        for s in per_day:
            s["day"] = str(s["day"])
        anom_proj = store.all(
            "SELECT p.name, COUNT(a.id) AS n FROM anomalies a"
            " JOIN projects p ON p.id = a.project_id"
            " WHERE a.status = 'pendiente' GROUP BY p.id"
            " ORDER BY n DESC LIMIT 8"
        )
        pipe_status = store.all(
            "SELECT status, COUNT(*) AS n FROM pipelines GROUP BY status"
        )
        quality_avg_proj = store.all(
            "SELECT p.name, COALESCE(AVG(d.quality_score), 0) AS q"
            " FROM projects p LEFT JOIN datasets d ON d.project_id = p.id"
            " GROUP BY p.id ORDER BY p.created_at LIMIT 8"
        )
        return {
            "totals": {
                "projects": projects,
                "datasets": datasets,
                "records": records,
                "runs": runs["n"],
                "runs_ok": runs["ok"],
                "runs_fail": runs["fail"],
                "quality_issues": issues,
                "anomalies": anoms,
                "quality_avg": round(avg_q or 0, 2),
            },
            "recent_alerts": recent_alerts,
            "latest_files": latest_files,
            "charts": {
                "runs_by_status": by_status,
                "runs_per_day": list(reversed(per_day)),
                "anomalies_per_project": anom_proj,
                "pipelines_by_status": pipe_status,
                "quality_avg_project": [
                    {"name": r["name"], "q": round(r["q"] or 0, 2)}
                    for r in quality_avg_proj
                ],
            },
        }

    # ---------- monitoreo ----------

    @app.get("/api/monitoring")
    def monitoring(request: Request):
        current(request)
        active = store.all(
            "SELECT r.*, d.filename, p.name AS pipeline FROM runs r"
            " JOIN datasets d ON d.id = r.dataset_id"
            " LEFT JOIN pipelines p ON p.id = r.pipeline_id"
            " WHERE r.status IN ('queued', 'running')"
            " ORDER BY r.created_at DESC"
        )
        finished = store.all(
            "SELECT r.*, d.filename FROM runs r"
            " JOIN datasets d ON d.id = r.dataset_id"
            " WHERE r.status = 'completed' ORDER BY r.finished_at DESC LIMIT 10"
        )
        failed = store.all(
            "SELECT r.*, d.filename FROM runs r"
            " JOIN datasets d ON d.id = r.dataset_id"
            " WHERE r.status = 'failed' ORDER BY r.finished_at DESC LIMIT 10"
        )
        last = store.all(
            "SELECT r.*, d.filename FROM runs r"
            " JOIN datasets d ON d.id = r.dataset_id"
            " ORDER BY r.created_at DESC LIMIT 12"
        )
        avg_t = store.one(
            "SELECT COALESCE(AVG(duration_ms), 0) AS t FROM runs"
            " WHERE status = 'completed'"
        )["t"]
        errors = store.one("SELECT COUNT(*) AS n FROM runs WHERE status = 'failed'")[
            "n"
        ]
        alerts = store.all(
            "SELECT * FROM alerts WHERE level IN ('error', 'critico')"
            " AND `read` = 0 ORDER BY created_at DESC LIMIT 8"
        )
        return {
            "active": active,
            "finished": finished,
            "failed": failed,
            "last_runs": last,
            "avg_duration_ms": round(avg_t or 0),
            "errors": errors,
            "alerts": alerts,
        }
