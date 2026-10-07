"""API DataOps Final (solo /api). El frontend es PHP en :8080."""

import base64
import hashlib
import json
import re
import secrets
import time
import uuid
from collections import defaultdict, deque
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, Response

from backend import db as mydb
from backend.core import (
    COLUMNS,
    MODEL_SALES,
    Engine,
    Store,
    Worker,
    csv_export,
    rows_to_csv,
    now,
    parse_csv_dynamic,
    parse_excel_dynamic,
    parse_sql_dynamic,
    password_hash,
    password_ok,
)

COOKIE = "dataops_session"


def create_app(background=True):
    """Crea la app. background=False en tests (sin hilo worker)."""
    store = Store()
    failures = defaultdict(deque)

    @asynccontextmanager
    async def lifespan(app):
        worker = Worker(store)
        app.state.worker = worker
        if background:
            worker.start()
        yield
        worker.stop()

    app = FastAPI(
        title="DataOps API",
        version="1.0.0",
        lifespan=lifespan,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    app.state.store = store

    # -- seguridad --------------------------------------------------

    @app.middleware("http")
    async def protect(request, call_next):
        if request.url.hostname not in ("localhost", "127.0.0.1", "testserver"):
            return JSONResponse({"detail": "Solo acceso local."}, status_code=403)
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            if request.headers.get("x-requested-with") != "DataOps":
                return JSONResponse(
                    {"detail": "Falta encabezado de seguridad."}, status_code=403
                )
            origin = request.headers.get("origin")
            allowed = {
                "http://localhost:8080",
                "http://127.0.0.1:8080",
                "http://localhost:8010",
                "http://127.0.0.1:8010",
                "http://testserver",
            }
            if origin and origin not in allowed:
                return JSONResponse({"detail": "Origen no permitido."}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self';"
            " style-src 'self' 'unsafe-inline'; img-src 'self' data:;"
            " connect-src 'self'; frame-ancestors 'none'; base-uri 'self'"
        )
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    async def body(request):
        """Lee JSON del body (máx 16 MiB por el base64 de Excel)."""
        chunks = bytearray()
        async for chunk in request.stream():
            chunks.extend(chunk)
            if len(chunks) > 16 * 1024 * 1024:
                raise HTTPException(413, "Archivo hasta 10 MiB.")
        try:
            value = json.loads(chunks)
            if not isinstance(value, dict):
                raise ValueError()
            return value
        except (ValueError, UnicodeDecodeError):
            raise HTTPException(400, "JSON inválido.")

    def current(request, roles=None):
        token = request.cookies.get(COOKIE, "")
        user = store.one(
            "SELECT u.id, u.username, u.name, u.role FROM sessions s"
            " JOIN users u ON u.id = s.user_id"
            " WHERE s.token_hash = %s AND s.expires_at > %s",
            (hashlib.sha256(token.encode()).hexdigest(), time.time()),
        )
        if not user:
            raise HTTPException(401, "Inicia sesión.")
        if roles and user["role"] not in roles:
            raise HTTPException(403, "Tu rol no permite esto.")
        return user

    def check_credentials(value):
        username = str(value.get("username", "")).strip().lower()
        password = str(value.get("password", ""))
        name = str(value.get("name", "")).strip()
        if not re.fullmatch(r"[a-z][a-z0-9_.\-]{2,31}", username):
            raise HTTPException(400, "Usuario inválido (3-32, inicia con letra).")
        if not 10 <= len(password) <= 128:
            raise HTTPException(400, "Clave de 10 a 128 caracteres.")
        if not name or len(name) > 80:
            raise HTTPException(400, "Nombre hasta 80 caracteres.")
        return username, password, name

    # -- salud ------------------------------------------------------

    @app.get("/api/health")
    def health():
        return {"status": "ok", "version": "1.0.0"}

    @app.get("/api/ready")
    def ready():
        checks = {}
        try:
            store.one("SELECT 1 AS ok")
            checks["db"] = "ok"
        except Exception:
            checks["db"] = "fail"
        try:
            worker = getattr(app.state, "worker", None)
            ok = (
                worker is not None
                and getattr(getattr(worker, "engine", None), "model", None) is not None
            )
            if not ok:  # En tests no hay worker: prueba construirlo.
                Engine(store)
            checks["model"] = "ok"
        except Exception:
            checks["model"] = "fail"
        checks["worker"] = "ok"
        return {"ready": all(v == "ok" for v in checks.values()), "checks": checks}

    # -- auth -------------------------------------------------------

    @app.get("/api/setup")
    def setup_state():
        return {"needs_setup": not bool(store.one("SELECT id FROM users LIMIT 1"))}

    @app.post("/api/setup")
    async def setup(request: Request):
        username, password, name = check_credentials(await body(request))
        if store.one("SELECT id FROM users LIMIT 1"):
            raise HTTPException(409, "La cuenta inicial ya existe.")
        store.run(
            "INSERT INTO users (username, name, password_hash, role, created_at)"
            " VALUES (%s, %s, %s, 'admin', %s)",
            (username, name, password_hash(password), now()),
        )
        return {"message": "Cuenta creada. Inicia sesión."}

    @app.post("/api/login")
    async def login(request: Request):
        value = await body(request)
        username = str(value.get("username", "")).strip().lower()
        password = str(value.get("password", ""))
        key = request.client.host if request.client else "local"
        recent = failures[key]
        while recent and recent[0] < time.monotonic() - 60:
            recent.popleft()
        if len(recent) >= 8:
            raise HTTPException(429, "Espera un minuto.")
        user = store.one("SELECT * FROM users WHERE username = %s", (username,))
        if not user or not password_ok(password, user["password_hash"]):
            recent.append(time.monotonic())
            raise HTTPException(401, "Usuario o clave incorrectos.")
        recent.clear()
        token = secrets.token_urlsafe(32)
        store.run(
            "INSERT INTO sessions (token_hash, user_id, expires_at)"
            " VALUES (%s, %s, %s)",
            (
                hashlib.sha256(token.encode()).hexdigest(),
                user["id"],
                time.time() + 8 * 3600,
            ),
        )
        store.audit(user["id"], "login")
        response = JSONResponse({"message": "Sesión iniciada."})
        response.set_cookie(
            COOKIE, token, httponly=True, samesite="strict", max_age=8 * 3600
        )
        return response

    @app.post("/api/logout")
    def logout(request: Request):
        token = request.cookies.get(COOKIE, "")
        store.run(
            "DELETE FROM sessions WHERE token_hash = %s",
            (hashlib.sha256(token.encode()).hexdigest(),),
        )
        response = JSONResponse({"message": "Sesión cerrada."})
        response.delete_cookie(COOKIE)
        return response

    @app.get("/api/me")
    def me(request: Request):
        return current(request)

    # -- usuarios (admin) -------------------------------------------

    @app.get("/api/users")
    def users(request: Request):
        current(request, {"admin"})
        return store.all(
            "SELECT id, username, name, role, created_at FROM users ORDER BY id"
        )

    @app.post("/api/users")
    async def add_user(request: Request):
        actor = current(request, {"admin"})
        value = await body(request)
        username, password, name = check_credentials(value)
        role = value.get("role", "viewer")
        if role not in ("admin", "operator", "viewer"):
            raise HTTPException(400, "Rol inválido.")
        try:
            new_id, _ = store.run(
                "INSERT INTO users (username, name, password_hash, role,"
                " created_at) VALUES (%s, %s, %s, %s, %s)",
                (username, name, password_hash(password), role, now()),
            )
        except Exception:
            raise HTTPException(409, "Ese usuario ya existe.")
        store.audit(actor["id"], "user_created", str(new_id))
        return {"id": new_id}

    # -- datasets ---------------------------------------------------

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

    # -- pipelines --------------------------------------------------

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

    # -- runs -------------------------------------------------------

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

    # -- métricas ---------------------------------------------------

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

    @app.get("/api/template")
    def template(request: Request):
        current(request)
        from pathlib import Path as _P

        path = _P(__file__).resolve().parents[1] / "examples" / "plantilla.csv"
        from fastapi.responses import FileResponse as _FR

        return _FR(path, filename="plantilla.csv", media_type="text/csv")

    # Plataforma extendida: proyectos, calidad, anomalías, IA,
    # alertas, reportes, actividad y dashboard (MySQL).
    from backend.platform_api import register as _register_platform

    _register_platform(app, store, current, body)

    return app


app = create_app()
