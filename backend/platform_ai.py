"""IA conversacional sobre los datos, resumen, recomendaciones y estado.

El motor local (estadístico + IsolationForest) funciona sin claves.
OpenAI y Azure son opcionales vía variables de entorno.
"""

from fastapi import HTTPException, Request


def register(ctx):
    app, store, current, body = ctx.app, ctx.store, ctx.current, ctx.body
    act = ctx.act
    ai_context_for = ctx.ai_context_for
    ai = ctx.ai

    def save_query(user, dataset_id, project_id, question, answer):
        """Guarda la consulta para el historial de IA."""
        store.run(
            "INSERT INTO ai_queries (user_id, project_id, dataset_id, question,"
            " answer, created_at) VALUES (%s, %s, %s, %s, %s, %s)",
            (
                user["id"],
                project_id,
                dataset_id,
                question[:1000],
                answer[:4000],
                ctx.now(),
            ),
        )

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
        d, ai_ctx, prof, qual, anoms, rows = ai_context_for(dataset_id, project_id)
        columns = [c["name"] for c in ai_ctx.get("columns", [])]
        res = ai.answer(question, ai_ctx, full_rows=rows, columns=columns)
        save_query(user, dataset_id, d.get("project_id"), question, res["answer"])
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
        d, ai_ctx, prof, qual, anoms, rows = ai_context_for(
            dataset_id, v.get("project_id")
        )
        text = ai.summary_text(ai_ctx)
        save_query(user, dataset_id, d.get("project_id"), "[resumen]", text)
        return {
            "summary": text,
            "source": "local",
            "kind": "estadistico",
            "engine": ai.ENGINES["estadistico"],
            "dataset": d["filename"],
        }

    @app.post("/api/ai/recommendations")
    async def ai_recs(request: Request):
        user = current(request)
        v = await body(request)
        dataset_id = v.get("dataset_id")
        if not dataset_id:
            raise HTTPException(400, "Selecciona el dataset.")
        d, ai_ctx, prof, qual, anoms, rows = ai_context_for(
            dataset_id, v.get("project_id")
        )
        text = ai.recommendations(ai_ctx)
        save_query(user, dataset_id, d.get("project_id"), "[recomendaciones]", text)
        return {
            "recommendations": text,
            "source": "local",
            "kind": "estadistico",
            "engine": ai.ENGINES["estadistico"],
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
            **ai.provider_status(),
            "engines": [
                {
                    "kind": "estadistico",
                    "name": "Análisis estadístico",
                    "description": ai.ENGINES["estadistico"] + ". Siempre disponible.",
                },
                {
                    "kind": "ml",
                    "name": "Machine Learning",
                    "description": ai.ENGINES["ml"] + ". Siempre disponible.",
                },
                {
                    "kind": "generativa",
                    "name": "IA generativa",
                    "description": ai.ENGINES["generativa"]
                    + ". Solo con claves en el entorno.",
                },
            ],
        }
