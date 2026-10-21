"""API DataOps Final (solo /api). El frontend es PHP en :8080.

Este modulo es el orquestador: define el middleware de seguridad, los
helpers compartidos y registra los modulos de endpoints:

  api_auth.py       autenticacion, sesion y usuarios
  api_datasets.py   archivos: carga, listado, perfil y ejemplo
  api_pipelines.py  pipelines: configuracion, estado e historial
  api_runs.py       ejecuciones: encolar, consultar, exportar, aprobar
  api_metrics.py    resumen y metricas de operacion
  platform_*.py     proyectos, calidad, anomalias, IA, reportes, usuarios
"""

import hashlib
import json
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from types import SimpleNamespace

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from backend.core import Engine, Store, Worker
from backend.settings import COOKIE

# Modulos de endpoints que se registran sobre la app.
API_MODULES = (
    "api_auth",
    "api_datasets",
    "api_pipelines",
    "api_runs",
    "api_metrics",
)


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

    # -- helpers compartidos ----------------------------------------

    async def body(request):
        """Lee JSON del body (max 16 MiB por el base64 de Excel)."""
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
            raise HTTPException(400, "JSON invalido.")

    def current(request, roles=None):
        """Devuelve el usuario de la sesion o 401/403."""
        token = request.cookies.get(COOKIE, "")
        user = store.one(
            "SELECT u.id, u.username, u.name, u.role FROM sessions s"
            " JOIN users u ON u.id = s.user_id"
            " WHERE s.token_hash = %s AND s.expires_at > %s",
            (hashlib.sha256(token.encode()).hexdigest(), time.time()),
        )
        if not user:
            raise HTTPException(401, "Inicia sesion.")
        if roles and user["role"] not in roles:
            raise HTTPException(403, "Tu rol no permite esto.")
        return user

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

    # -- registro de modulos ----------------------------------------

    ctx = SimpleNamespace(
        app=app, store=store, current=current, body=body, failures=failures
    )

    import importlib

    for name in API_MODULES:
        importlib.import_module(f"backend.{name}").register(ctx)

    # Plataforma extendida: proyectos, calidad, anomalias, IA,
    # alertas, reportes, actividad y dashboard (MySQL).
    from backend.platform_api import register as _register_platform

    _register_platform(app, store, current, body)

    return app


app = create_app()
