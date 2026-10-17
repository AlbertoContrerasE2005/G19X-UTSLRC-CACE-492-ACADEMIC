"""Configuración del sistema y administración de usuarios."""

from fastapi import HTTPException, Request

from backend.core import password_hash, password_ok

ROLES = ("admin", "operator", "viewer")


def register(ctx):
    app, store, current, body = ctx.app, ctx.store, ctx.current, ctx.body
    act = ctx.act
    ai = ctx.ai

    @app.get("/api/config")
    def config(request: Request):
        current(request)
        return {
            "version": "1.0.0",
            "limits": {
                "max_mb": 10,
                "max_rows": 20000,
                "max_columns": 30,
            },
            "ai": ai.provider_status(),
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
        if role not in ROLES:
            raise HTTPException(400, "Rol inválido.")
        if u["role"] == "admin" and role != "admin" and _admin_count(store) <= 1:
            raise HTTPException(400, "Debe quedar un administrador.")
        store.run(
            "UPDATE users SET name = %s, role = %s WHERE id = %s", (name, role, uid)
        )
        if v.get("password"):
            pw = str(v.get("password"))
            if not 10 <= len(pw) <= 128:
                raise HTTPException(400, "Clave de 10 a 128.")
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
        if u["role"] == "admin" and _admin_count(store) <= 1:
            raise HTTPException(400, "Debe quedar un administrador.")
        store.run("DELETE FROM sessions WHERE user_id = %s", (uid,))
        store.run("DELETE FROM users WHERE id = %s", (uid,))
        act(actor, "usuario_eliminado", "user", str(uid), None, u["username"])
        return {"message": "Usuario eliminado."}

    @app.post("/api/me/password")
    async def me_password(request: Request):
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


def _admin_count(store):
    return store.one("SELECT COUNT(*) AS n FROM users WHERE role = 'admin'")["n"]
