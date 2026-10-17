"""Calidad de datos: reglas, evaluación, resultados y anomalías."""

import uuid

from fastapi import HTTPException, Request

from backend.profiling import CONDITIONS, evaluate_rule, quality_score


def register(ctx):
    app, store, current, body = ctx.app, ctx.store, ctx.current, ctx.body
    act = ctx.act
    get_dataset_rows = ctx.get_dataset_rows

    # ---------- reglas ----------

    @app.get("/api/quality/rules")
    def rules_list(
        request: Request,
        dataset_id: str = "",
        project_id: str = "",
        pipeline_id: str = "",
    ):
        current(request)
        where, params = [], []
        if dataset_id:
            where.append("dataset_id = %s")
            params.append(dataset_id)
        if project_id:
            where.append("project_id = %s")
            params.append(project_id)
        if pipeline_id:
            where.append("pipeline_id = %s")
            params.append(pipeline_id)
        clause = ("WHERE " + " AND ".join(where)) if where else ""
        return store.all(
            f"SELECT * FROM quality_rules {clause}"
            " ORDER BY created_at DESC LIMIT 200",
            tuple(params),
        )

    @app.post("/api/quality/rules")
    async def rules_create(request: Request):
        user = current(request, {"admin", "operator"})
        v = await body(request)
        dataset_id = v.get("dataset_id") or None
        project_id = v.get("project_id") or None
        pipeline_id = v.get("pipeline_id") or None
        column = str(v.get("column", v.get("column_name", ""))).strip()[:120]
        condition = str(v.get("condition", "")).strip()
        value = str(v.get("value", ""))[:200]
        severity = str(v.get("severity", "media")).lower()
        if not column:
            raise HTTPException(400, "Indica la columna.")
        if condition not in CONDITIONS:
            raise HTTPException(
                400, "Condición inválida: " + ", ".join(sorted(CONDITIONS))
            )
        if severity not in ("baja", "media", "alta", "critica"):
            raise HTTPException(400, "Severidad inválida.")
        if dataset_id and not store.one(
            "SELECT id FROM datasets WHERE id = %s", (dataset_id,)
        ):
            raise HTTPException(404, "Dataset no encontrado.")
        if project_id and not store.one(
            "SELECT id FROM projects WHERE id = %s", (project_id,)
        ):
            raise HTTPException(404, "Proyecto no encontrado.")
        rid = "rl_" + uuid.uuid4().hex[:10]
        store.run(
            "INSERT INTO quality_rules (id, project_id, dataset_id, pipeline_id,"
            " column_name, `condition`, value, severity, active, created_by,"
            " created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 1, %s, %s)",
            (
                rid,
                project_id,
                dataset_id,
                pipeline_id,
                column,
                condition,
                value,
                severity,
                user["id"],
                ctx.now(),
            ),
        )
        act(
            user,
            "regla_creada",
            "quality_rule",
            rid,
            project_id,
            f"{column} {condition} {value}",
        )
        return {"id": rid}

    @app.put("/api/quality/rules/{rid}")
    async def rules_update(rid: str, request: Request):
        user = current(request, {"admin", "operator"})
        v = await body(request)
        r = store.one("SELECT * FROM quality_rules WHERE id = %s", (rid,))
        if not r:
            raise HTTPException(404, "Regla no encontrada.")
        condition = str(v.get("condition", r["condition"])).strip()
        if condition not in CONDITIONS:
            raise HTTPException(400, "Condición inválida.")
        severity = str(v.get("severity", r["severity"])).lower()
        if severity not in ("baja", "media", "alta", "critica"):
            raise HTTPException(400, "Severidad inválida.")
        active = v.get("active", r["active"])
        active = 1 if active in (1, True, "1", "true") else 0
        store.run(
            "UPDATE quality_rules SET column_name = %s, `condition` = %s,"
            " value = %s, severity = %s, active = %s WHERE id = %s",
            (
                str(v.get("column", v.get("column_name", r["column_name"]))).strip()[
                    :120
                ],
                condition,
                str(v.get("value", r["value"]))[:200],
                severity,
                active,
                rid,
            ),
        )
        act(
            user,
            "regla_actualizada",
            "quality_rule",
            rid,
            r["project_id"],
            condition,
        )
        return {"message": "Regla actualizada."}

    @app.delete("/api/quality/rules/{rid}")
    def rules_delete(rid: str, request: Request):
        user = current(request, {"admin", "operator"})
        r = store.one("SELECT * FROM quality_rules WHERE id = %s", (rid,))
        if not r:
            raise HTTPException(404, "Regla no encontrada.")
        store.run("DELETE FROM quality_rules WHERE id = %s", (rid,))
        act(
            user,
            "regla_eliminada",
            "quality_rule",
            rid,
            r["project_id"],
            r["column_name"],
        )
        return {"message": "Regla eliminada."}

    @app.post("/api/quality/evaluate")
    async def quality_evaluate(request: Request):
        user = current(request)
        v = await body(request)
        dataset_id = v.get("dataset_id")
        if not dataset_id or not isinstance(dataset_id, str):
            raise HTTPException(400, "Indica el dataset.")
        d, columns, rows = get_dataset_rows(dataset_id)
        if not d:
            raise HTTPException(404, "Archivo no encontrado.")
        auto = quality_score(columns, rows)
        rules = store.all(
            "SELECT * FROM quality_rules WHERE active = 1"
            " AND (dataset_id = %s OR dataset_id IS NULL)",
            (dataset_id,),
        )
        evaluated = []
        for rl in rules:
            res = evaluate_rule(
                rl["column_name"],
                rl["condition"],
                rl["value"] or "",
                columns,
                rows,
            )
            evaluated.append({"rule": rl, **res})
        act(
            user,
            "calidad_evaluada",
            "dataset",
            dataset_id,
            d.get("project_id"),
            f"{len(rules)} reglas",
        )
        return {
            "quality": auto,
            "rules": evaluated,
            "columns": columns,
            "row_count": len(rows),
        }

    @app.get("/api/quality/results")
    def quality_results(
        request: Request,
        dataset_id: str = "",
        run_id: str = "",
        project_id: str = "",
        limit: int = 100,
    ):
        current(request)
        where, params = [], []
        if dataset_id:
            where.append("dataset_id = %s")
            params.append(dataset_id)
        if run_id:
            where.append("run_id = %s")
            params.append(run_id)
        if project_id:
            where.append("project_id = %s")
            params.append(project_id)
        clause = ("WHERE " + " AND ".join(where)) if where else ""
        limit = max(1, min(500, limit if isinstance(limit, int) else 100))
        return store.all(
            f"SELECT * FROM quality_results {clause}"
            " ORDER BY created_at DESC LIMIT %s",
            tuple(params) + (limit,),
        )

    # ---------- anomalías ----------

    @app.get("/api/anomalies")
    def anomalies_list(
        request: Request,
        project_id: str = "",
        dataset_id: str = "",
        run_id: str = "",
        severity: str = "",
        status: str = "pendiente",
        offset: int = 0,
        limit: int = 50,
        search: str = "",
    ):
        current(request)
        where, params = [], []
        if project_id:
            where.append("project_id = %s")
            params.append(project_id)
        if dataset_id:
            where.append("dataset_id = %s")
            params.append(dataset_id)
        if run_id:
            where.append("run_id = %s")
            params.append(run_id)
        if severity in ("baja", "media", "alta", "critica"):
            where.append("severity = %s")
            params.append(severity)
        if status in ("pendiente", "aprobada", "rechazada", "resuelta", "todas"):
            if status != "todas":
                where.append("a.status = %s")
                params.append(status)
        if search:
            where.append("(reason LIKE %s OR value LIKE %s OR column_name LIKE %s)")
            params += [f"%{search[:60]}%"] * 3
        clause = ("WHERE " + " AND ".join(where)) if where else ""
        limit = max(1, min(200, limit if isinstance(limit, int) else 50))
        offset = max(0, offset if isinstance(offset, int) else 0)
        items = store.all(
            "SELECT a.*, d.filename FROM anomalies a"
            " LEFT JOIN datasets d ON d.id = a.dataset_id"
            f" {clause} ORDER BY a.created_at DESC LIMIT %s OFFSET %s",
            tuple(params) + (limit, offset),
        )
        total = store.one(
            f"SELECT COUNT(*) AS n FROM anomalies a {clause}", tuple(params)
        )["n"]
        return {
            "items": items,
            "total": total,
            "offset": offset,
            "limit": limit,
        }

    @app.patch("/api/anomalies/{aid}")
    async def anomalies_patch(aid: int, request: Request):
        user = current(request, {"admin", "operator"})
        v = await body(request)
        a = store.one("SELECT * FROM anomalies WHERE id = %s", (aid,))
        if not a:
            raise HTTPException(404, "Anomalía no encontrada.")
        status = str(v.get("status", "")).strip()
        if status not in ("pendiente", "aprobada", "rechazada", "resuelta"):
            raise HTTPException(400, "Estado inválido.")
        store.run("UPDATE anomalies SET status = %s WHERE id = %s", (status, aid))
        act(
            user,
            "anomalia_actualizada",
            "anomaly",
            str(aid),
            a["project_id"],
            status,
        )
        return {"message": "Anomalía actualizada."}
