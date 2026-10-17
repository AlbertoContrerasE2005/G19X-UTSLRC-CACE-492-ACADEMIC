"""Ayudantes compartidos por los módulos de la plataforma.

Un `Context` agrupa lo que cada módulo necesita: app, store, current,
body y funciones derivadas (act, get_dataset_rows, ai_context_for).
"""

from types import SimpleNamespace

from fastapi import HTTPException

from backend import ai_service
from backend.core import now, parse_csv_dynamic
from backend.profiling import profile_dataset, quality_score


def make_context(app, store, current, body):
    """Crea el contexto que consumen los módulos de la plataforma."""

    def act(
        user,
        action,
        entity_type="",
        entity_id="",
        project_id=None,
        detail="",
        result="",
    ):
        """Registra actividad y auditoría, sin romper si algo falla."""
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
        """Devuelve (dataset, columnas, filas) o (None, None, None)."""
        d = store.one("SELECT * FROM datasets WHERE id = %s", (dataset_id,))
        if not d:
            return None, None, None
        try:
            columns = json_columns(d)
        except ValueError:
            columns = []
        try:
            _, rows = parse_csv_dynamic(d["content"])
        except ValueError:
            rows = []
        return d, columns, rows

    def ai_context_for(dataset_id, project_id=None):
        """Construye el contexto que consume la IA (perfil + calidad)."""
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
            anoms = _anoms_from_last_run(store, dataset_id)
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

    return SimpleNamespace(
        app=app,
        store=store,
        current=current,
        body=body,
        act=act,
        get_dataset_rows=get_dataset_rows,
        ai_context_for=ai_context_for,
        now=now,
        ai=ai_service,
    )


def json_columns(dataset):
    """Lee columns_json del dataset y devuelve la lista de columnas."""
    import json

    return json.loads(dataset.get("columns_json") or "[]") or []


def _anoms_from_last_run(store, dataset_id):
    """Sin tabla de anomalías: usa las alertas del último run completado."""
    last = store.one(
        "SELECT id FROM runs WHERE dataset_id = %s AND status = 'completed'"
        " ORDER BY finished_at DESC LIMIT 1",
        (dataset_id,),
    )
    if not last:
        return []
    rows = store.all(
        "SELECT line AS row_line, data_json AS value, reason, score"
        " FROM run_rows WHERE run_id = %s AND status = 'anomaly' LIMIT 10",
        (last["id"],),
    )
    return [
        {
            "column_name": "",
            "row_line": r["row_line"],
            "value": r["value"][:200],
            "reason": r["reason"],
            "severity": "media",
            "score": r["score"],
        }
        for r in rows
    ]
