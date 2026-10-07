"""Endpoints plataforma: proyectos, calidad, anomalías, IA, alertas,
reportes, actividad, dashboard. Se registran sobre la app de backend/app.py.
"""

import json
import time
import uuid

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse, Response


def register(app, store, current, body):
    from backend.core import now, parse_csv_dynamic
    from backend.profiling import (
        CONDITIONS,
        evaluate_rule,
        profile_dataset,
        quality_score,
    )
    from backend import ai_service
    from backend.reports import report_payload, to_csv, to_pdf

    def act(
        user,
        action,
        entity_type="",
        entity_id="",
        project_id=None,
        detail="",
        result="",
    ):
        try:
            store.activity(
                user["id"],
                user.get("name", user.get("username", "")),
                action,
                entity_type,
                entity_id,
                project_id,
                detail,
                result,
            )
        except Exception:
            pass
        try:
            store.audit(user["id"], action, entity_id or None)
        except Exception:
            pass

    def get_dataset_rows(dataset_id):
        d = store.one("SELECT * FROM datasets WHERE id = %s", (dataset_id,))
        if not d:
            return None, None, None
        try:
            columns = json.loads(d.get("columns_json") or "[]") or []
        except (ValueError, TypeError):
            columns = []
        try:
            _, rows = parse_csv_dynamic(d["content"])
        except ValueError:
            rows = []
        return d, columns, rows

    def ai_context_for(dataset_id, project_id=None):
        d, columns, rows = get_dataset_rows(dataset_id)
        if not d:
            raise HTTPException(404, "Selecciona un dataset existente.")
        prof = (
            profile_dataset(columns, rows)
            if rows
            else {
                "row_count": 0,
                "column_count": len(columns),
                "profiles": [],
                "columns": columns,
            }
        )
        qual = (
            quality_score(columns, rows)
            if rows
            else {
                "general": 0,
                "completitud": 0,
                "unicidad": 0,
                "validez": 0,
                "consistencia": 0,
                "issues": [],
            }
        )
        anoms = store.all(
            "SELECT column_name, row_line, value, reason, severity, score"
            " FROM anomalies WHERE dataset_id = %s"
            " ORDER BY created_at DESC LIMIT 20",
            (dataset_id,),
        )
        if not anoms:
            last = store.one(
                "SELECT id FROM runs WHERE dataset_id = %s AND status = 'completed'"
                " ORDER BY finished_at DESC LIMIT 1",
                (dataset_id,),
            )
            if last:
                rr = store.all(
                    "SELECT line AS row_line, data_json AS value, reason, score"
                    " FROM run_rows WHERE run_id = %s AND status = 'anomaly' LIMIT 10",
                    (last["id"],),
                )
                anoms = [
                    {
                        "column_name": "",
                        "row_line": r["row_line"],
                        "value": r["value"][:200],
                        "reason": r["reason"],
                        "severity": "media",
                        "score": r["score"],
                    }
                    for r in rr
                ]
        ctx = {
            "dataset": d["filename"],
            "rows": prof.get("row_count", 0),
            "columns": [
                {
                    "name": p["name"],
                    "type": p["type"],
                    "nulls": p["nulls"],
                    "uniques": p["uniques"],
                    **{k: p[k] for k in ("min", "max", "avg") if k in p},
                }
                for p in prof.get("profiles", [])
            ],
            "quality": {
                k: qual.get(k)
                for k in (
                    "general",
                    "completitud",
                    "unicidad",
                    "validez",
                    "consistencia",
                )
            },
            "issues": qual.get("issues", [])[:10],
            "anomalies": anoms[:10],
            "sample": rows[:8],
        }
        return d, ctx, prof, qual, anoms, rows

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
            f" FROM projects p LEFT JOIN users u ON u.id = p.owner_id"
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
        ts = now()
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
            (name, desc, status, now(), pid),
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

    # ---------- reglas de calidad ----------

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
            f" ORDER BY created_at DESC LIMIT 200",
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
                now(),
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
        act(user, "regla_actualizada", "quality_rule", rid, r["project_id"], condition)
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
            f" ORDER BY created_at DESC LIMIT %s",
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
        return {"items": items, "total": total, "offset": offset, "limit": limit}

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
        act(user, "anomalia_actualizada", "anomaly", str(aid), a["project_id"], status)
        return {"message": "Anomalía actualizada."}

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
            f" ORDER BY created_at DESC LIMIT %s OFFSET %s",
            tuple(params) + (limit, offset),
        )
        total = store.one(f"SELECT COUNT(*) AS n FROM alerts {clause}", tuple(params))[
            "n"
        ]
        unread_n = store.one("SELECT COUNT(*) AS n FROM alerts WHERE `read` = 0")["n"]
        return {"items": items, "total": total, "unread": unread_n, "offset": offset}

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

    # ---------- reportes ----------

    @app.get("/api/reports")
    def reports_list(
        request: Request, project_id: str = "", dataset_id: str = "", type: str = ""
    ):
        current(request)
        where, params = [], []
        if project_id:
            where.append("project_id = %s")
            params.append(project_id)
        if dataset_id:
            where.append("dataset_id = %s")
            params.append(dataset_id)
        if type in ("analisis", "calidad", "anomalias", "ejecucion"):
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
        if rtype not in ("analisis", "calidad", "anomalias", "ejecucion"):
            raise HTTPException(400, "Tipo inválido.")
        if fmt not in ("json", "csv", "pdf"):
            raise HTTPException(400, "Formato: json, csv o pdf.")
        if not dataset_id or not store.one(
            "SELECT id FROM datasets WHERE id = %s", (dataset_id,)
        ):
            raise HTTPException(404, "Selecciona un dataset existente.")
        d, ctx, prof, qual, anoms, rows = ai_context_for(dataset_id, project_id)
        if run_id:
            run = store.one("SELECT * FROM runs WHERE id = %s", (run_id,))
        else:
            run = store.one(
                "SELECT * FROM runs WHERE dataset_id = %s AND status = 'completed'"
                " ORDER BY finished_at DESC LIMIT 1",
                (dataset_id,),
            )
        if rtype == "ejecucion" and not run:
            raise HTTPException(404, "Sin ejecuciones. Ejecuta primero.")
        recs = ai_service.recommendations(ctx)
        summ = ai_service.summary_text(ctx)
        proj = (
            store.one(
                "SELECT name FROM projects WHERE id = %s",
                (d.get("project_id") or project_id or "p_default",),
            )
            or {}
        )
        payload = report_payload(
            {"name": proj.get("name", "Proyecto")},
            d,
            run,
            prof,
            qual,
            anoms,
            recs,
            summ,
            rtype,
        )
        payload["fecha"] = now()
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
                json.dumps(payload, ensure_ascii=False),
                user["id"],
                now(),
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
        try:
            r["payload"] = json.loads(r.get("content_json") or "{}")
        except (ValueError, TypeError):
            r["payload"] = {}
        return r

    @app.get("/api/reports/{rid}/download")
    def reports_download(rid: str, request: Request):
        current(request)
        r = store.one("SELECT * FROM reports WHERE id = %s", (rid,))
        if not r:
            raise HTTPException(404, "Reporte no encontrado.")
        try:
            payload = json.loads(r.get("content_json") or "{}")
        except (ValueError, TypeError):
            payload = {}
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
            f" ORDER BY created_at DESC LIMIT %s OFFSET %s",
            tuple(params) + (limit, offset),
        )
        total = store.one(
            f"SELECT COUNT(*) AS n FROM activity_logs {clause}", tuple(params)
        )["n"]
        return {"items": items, "total": total, "offset": offset, "limit": limit}

    # ---------- dashboard + monitoreo ----------

    @app.get("/api/dashboard")
    def dashboard(request: Request, project_id: str = ""):
        current(request)
        pf = "AND d.project_id = %s" if project_id else ""
        pp = (project_id,) if project_id else ()
        wf = "WHERE d.project_id = %s" if project_id else ""
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
            "SELECT d.id, d.filename, d.row_count, d.quality_score, d.created_at,"
            " p.name AS project FROM datasets d"
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
            " WHERE a.status = 'pendiente' GROUP BY p.id ORDER BY n DESC LIMIT 8"
        )
        pipe_status = store.all(
            "SELECT status, COUNT(*) AS n FROM pipelines GROUP BY status"
        )
        quality_avg_proj = store.all(
            "SELECT p.name, COALESCE(AVG(d.quality_score), 0) AS q FROM projects p"
            " LEFT JOIN datasets d ON d.project_id = p.id"
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

    @app.get("/api/monitoring")
    def monitoring(request: Request):
        current(request)
        active = store.all(
            "SELECT r.*, d.filename, p.name AS pipeline FROM runs r"
            " JOIN datasets d ON d.id = r.dataset_id"
            " LEFT JOIN pipelines p ON p.id = r.pipeline_id"
            " WHERE r.status IN ('queued', 'running') ORDER BY r.created_at DESC"
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

    # ---------- IA ----------

    @app.post("/api/ai/ask")
    async def ai_ask(request: Request):
        user = current(request)
        v = await body(request)
        dataset_id = v.get("dataset_id")
        project_id = v.get("project_id")
        question = str(v.get("question", "")).strip()
        if not question or len(question) > 1000:
            raise HTTPException(400, "Pregunta hasta 1000 caracteres.")
        if not dataset_id or not isinstance(dataset_id, str):
            raise HTTPException(400, "Selecciona proyecto y dataset.")
        d, ctx, prof, qual, anoms, rows = ai_context_for(dataset_id, project_id)
        cols = [c["name"] for c in ctx.get("columns", [])]
        res = ai_service.answer(question, ctx, full_rows=rows, columns=cols)
        store.run(
            "INSERT INTO ai_queries (user_id, project_id, dataset_id, question,"
            " answer, created_at) VALUES (%s, %s, %s, %s, %s, %s)",
            (
                user["id"],
                d.get("project_id"),
                dataset_id,
                question[:1000],
                res["answer"][:4000],
                now(),
            ),
        )
        act(
            user,
            "ia_pregunta",
            "dataset",
            dataset_id,
            d.get("project_id"),
            question[:200],
        )
        return {**res, "dataset": d["filename"]}

    @app.post("/api/ai/summary")
    async def ai_summary(request: Request):
        user = current(request)
        v = await body(request)
        dataset_id = v.get("dataset_id")
        if not dataset_id:
            raise HTTPException(400, "Selecciona el dataset.")
        d, ctx, prof, qual, anoms, rows = ai_context_for(
            dataset_id, v.get("project_id")
        )
        text = ai_service.summary_text(ctx)
        store.run(
            "INSERT INTO ai_queries (user_id, project_id, dataset_id, question,"
            " answer, created_at) VALUES (%s, %s, %s, %s, %s, %s)",
            (
                user["id"],
                d.get("project_id"),
                dataset_id,
                "[resumen]",
                text[:4000],
                now(),
            ),
        )
        return {
            "summary": text,
            "source": "local",
            "kind": "estadistico",
            "engine": ai_service.ENGINES["estadistico"],
            "dataset": d["filename"],
        }

    @app.post("/api/ai/recommendations")
    async def ai_recs(request: Request):
        user = current(request)
        v = await body(request)
        dataset_id = v.get("dataset_id")
        if not dataset_id:
            raise HTTPException(400, "Selecciona el dataset.")
        d, ctx, prof, qual, anoms, rows = ai_context_for(
            dataset_id, v.get("project_id")
        )
        text = ai_service.recommendations(ctx)
        store.run(
            "INSERT INTO ai_queries (user_id, project_id, dataset_id, question,"
            " answer, created_at) VALUES (%s, %s, %s, %s, %s, %s)",
            (
                user["id"],
                d.get("project_id"),
                dataset_id,
                "[recomendaciones]",
                text[:4000],
                now(),
            ),
        )
        return {
            "recommendations": text,
            "source": "local",
            "kind": "estadistico",
            "engine": ai_service.ENGINES["estadistico"],
            "dataset": d["filename"],
        }

    @app.get("/api/ai/history")
    def ai_history(request: Request, dataset_id: str = "", limit: int = 30):
        user = current(request)
        limit = max(1, min(100, limit if isinstance(limit, int) else 30))
        if dataset_id:
            return store.all(
                "SELECT * FROM ai_queries WHERE user_id = %s AND dataset_id = %s"
                " ORDER BY created_at DESC LIMIT %s",
                (user["id"], dataset_id, limit),
            )
        return store.all(
            "SELECT q.*, d.filename FROM ai_queries q"
            " LEFT JOIN datasets d ON d.id = q.dataset_id"
            " WHERE q.user_id = %s ORDER BY q.created_at DESC LIMIT %s",
            (user["id"], limit),
        )

    @app.get("/api/ai/status")
    def ai_status(request: Request):
        current(request)
        return {
            **ai_service.provider_status(),
            "engines": [
                {
                    "kind": "estadistico",
                    "name": "Análisis estadístico",
                    "description": ai_service.ENGINES["estadistico"]
                    + ". Siempre disponible.",
                },
                {
                    "kind": "ml",
                    "name": "Machine Learning",
                    "description": ai_service.ENGINES["ml"] + ". Siempre disponible.",
                },
                {
                    "kind": "generativa",
                    "name": "IA generativa",
                    "description": ai_service.ENGINES["generativa"]
                    + ". Solo con claves en .env.",
                },
            ],
        }

    # ---------- config y usuarios ----------

    @app.get("/api/config")
    def config(request: Request):
        current(request)
        return {
            "version": "1.0.0",
            "limits": {"max_mb": 10, "max_rows": 20000, "max_columns": 30},
            "ai": ai_service.provider_status(),
            "formats": ["csv", "xlsx", "sql"],
        }

    @app.put("/api/users/{uid}")
    async def users_update(uid: int, request: Request):
        actor = current(request, {"admin"})
        v = await body(request)
        u = store.one("SELECT * FROM users WHERE id = %s", (uid,))
        if not u:
            raise HTTPException(404, "Usuario no encontrado.")
        name = str(v.get("name", u["name"])).strip()[:80] or u["name"]
        role = v.get("role", u["role"])
        if role not in ("admin", "operator", "viewer"):
            raise HTTPException(400, "Rol inválido.")
        if (
            u["role"] == "admin"
            and role != "admin"
            and store.one("SELECT COUNT(*) AS n FROM users WHERE role = 'admin'")["n"]
            <= 1
        ):
            raise HTTPException(400, "Debe quedar un administrador.")
        store.run(
            "UPDATE users SET name = %s, role = %s WHERE id = %s", (name, role, uid)
        )
        if v.get("password"):
            pw = str(v.get("password"))
            if not 10 <= len(pw) <= 128:
                raise HTTPException(400, "Clave de 10 a 128.")
            from backend.core import password_hash

            store.run(
                "UPDATE users SET password_hash = %s WHERE id = %s",
                (password_hash(pw), uid),
            )
        act(actor, "usuario_actualizado", "user", str(uid), None, f"{name}/{role}")
        return {"message": "Usuario actualizado."}

    @app.delete("/api/users/{uid}")
    def users_delete(uid: int, request: Request):
        actor = current(request, {"admin"})
        if actor["id"] == uid:
            raise HTTPException(400, "No puedes eliminarte.")
        u = store.one("SELECT * FROM users WHERE id = %s", (uid,))
        if not u:
            raise HTTPException(404, "Usuario no encontrado.")
        if (
            u["role"] == "admin"
            and store.one("SELECT COUNT(*) AS n FROM users WHERE role = 'admin'")["n"]
            <= 1
        ):
            raise HTTPException(400, "Debe quedar un administrador.")
        store.run("DELETE FROM sessions WHERE user_id = %s", (uid,))
        store.run("DELETE FROM users WHERE id = %s", (uid,))
        act(actor, "usuario_eliminado", "user", str(uid), None, u["username"])
        return {"message": "Usuario eliminado."}

    @app.post("/api/me/password")
    async def me_password(request: Request):
        from backend.core import password_hash, password_ok

        user = current(request)
        v = await body(request)
        full = store.one("SELECT * FROM users WHERE id = %s", (user["id"],))
        if not password_ok(str(v.get("current", "")), full["password_hash"]):
            raise HTTPException(400, "Tu clave actual no es correcta.")
        new = str(v.get("new", ""))
        if not 10 <= len(new) <= 128:
            raise HTTPException(400, "Nueva clave de 10 a 128.")
        store.run(
            "UPDATE users SET password_hash = %s WHERE id = %s",
            (password_hash(new), user["id"]),
        )
        return {"message": "Clave actualizada."}
