"""Endpoints de autenticacion, sesion y usuarios."""

import hashlib
import re
import secrets
import time
import uuid

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from backend.settings import COOKIE, now, password_hash, password_ok


def register(ctx):
    """Registra los endpoints de auth en la app."""
    app, store, current, body = ctx.app, ctx.store, ctx.current, ctx.body

    def check_credentials(value):
        """Normaliza y valida usuario, contrasena y nombre."""
        username = str(value.get("username", "")).strip().lower()
        password = str(value.get("password", ""))
        name = str(value.get("name", "")).strip()
        if not re.fullmatch(r"[a-z][a-z0-9_.\-]{2,31}", username):
            raise HTTPException(400, "Usuario invalido (3-32, inicia con letra).")
        if not 10 <= len(password) <= 128:
            raise HTTPException(400, "Clave de 10 a 128 caracteres.")
        if not name or len(name) > 80:
            raise HTTPException(400, "Nombre hasta 80 caracteres.")
        return username, password, name

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
        recent = ctx.failures[key]
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
