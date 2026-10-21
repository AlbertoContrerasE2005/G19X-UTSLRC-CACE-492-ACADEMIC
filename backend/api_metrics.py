"""Endpoints de resumen y metricas de operacion."""

from fastapi import HTTPException, Request
from backend.settings import COLUMNS, MODEL_SALES, now


def register(ctx):
    """Registra los endpoints de metricas en la app."""
    app, store, current, body = ctx.app, ctx.store, ctx.current, ctx.body

    @app.get("/api/summary")
    def summary(request: Request):
        current(request)
        latest = store.one("SELECT * FROM runs ORDER BY created_at DESC LIMIT 1")
        totals = store.one(
            "SELECT COUNT(*) AS runs,"
            " COALESCE(SUM(status = 'completed'), 0) AS completed,"
            " COALESCE(SUM(status = 'failed'), 0) AS failed FROM runs"
        )
        totals["sales"] = store.one("SELECT COUNT(*) AS n FROM sales")["n"]
        totals["records"] = store.one("SELECT COUNT(*) AS n FROM records")["n"]
        totals["destination"] = totals["sales"] + totals["records"]
        latest_completed = store.one(
            "SELECT * FROM runs WHERE status = 'completed'"
            " ORDER BY finished_at DESC LIMIT 1"
        )
        return {
            "totals": totals,
            "latest": latest,
            "latest_completed": latest_completed,
            "model_version": MODEL_SALES,
            "columns": COLUMNS,
        }

    @app.get("/api/metrics/summary")
    def metrics_summary(request: Request):
        current(request)
        active = store.one(
            "SELECT COUNT(*) AS n FROM runs" " WHERE status IN ('queued', 'running')"
        )["n"]
        last7 = store.all(
            "SELECT status, duration_ms,"
            " loaded + existing + invalid + anomalies"
            " + COALESCE(approved, 0) + COALESCE(rejected, 0) AS nrows"
            " FROM runs WHERE created_at >= DATE_SUB(NOW(), INTERVAL 7 DAY)"
        )
        total7 = len(last7)
        ok7 = sum(1 for r in last7 if r["status"] == "completed")
        success = round(ok7 / total7 * 100, 1) if total7 else 0
        durs = sorted(
            r["duration_ms"]
            for r in last7
            if r["status"] == "completed" and r["duration_ms"] is not None
        )

        def pct(p):
            return durs[min(len(durs) - 1, len(durs) * p // 100)] if durs else 0

        per_pipe = store.all(
            "SELECT p.id, p.name, COUNT(r.id) AS runs,"
            " COALESCE(SUM(r.status = 'completed'), 0) AS ok"
            " FROM pipelines p LEFT JOIN runs r ON r.pipeline_id = p.id"
            " GROUP BY p.id ORDER BY p.created_at"
        )
        return {
            "active": active,
            "total_7d": total7,
            "completed_7d": ok7,
            "success_rate": success,
            "duration_p50_ms": pct(50),
            "duration_p95_ms": pct(95),
            "rows_7d": sum(r["nrows"] or 0 for r in last7),
            "per_pipeline": per_pipe,
        }

    @app.get("/api/metrics/runs")
    def metrics_runs(request: Request, pipeline_id: str = "", days: int = 7):
        current(request)
        days = max(1, min(30, days if isinstance(days, int) else 7))
        where, params = (
            (
                "WHERE created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)"
                " AND pipeline_id = %s",
                (days, pipeline_id),
            )
            if pipeline_id
            else (
                "WHERE created_at >= DATE_SUB(NOW(), INTERVAL %s DAY)",
                (days,),
            )
        )
        series = store.all(
            "SELECT DATE(created_at) AS day, status, COUNT(*) AS n"
            f" FROM runs {where} GROUP BY day, status ORDER BY day",
            params,
        )
        for s in series:
            s["day"] = str(s["day"])
        return {"days": days, "series": series}
