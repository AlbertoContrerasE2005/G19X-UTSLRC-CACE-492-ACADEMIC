"""Servicio de IA desacoplado. Local por defecto; OpenAI/Azure opcionales vía .env.

Nunca envía el archivo completo: solo contexto agregado + muestra (máx 8 filas).
"""
from __future__ import annotations
import json
import os
import re
import urllib.request
from collections import Counter


def provider_status() -> dict:
    provider = os.environ.get("AI_PROVIDER", "local").lower()
    has_openai = bool(os.environ.get("OPENAI_API_KEY"))
    has_azure = bool(os.environ.get("AZURE_OPENAI_ENDPOINT") and os.environ.get("AZURE_OPENAI_API_KEY"))
    return {
        "provider": provider,
        "openai_configured": has_openai,
        "azure_configured": has_azure,
        "mode": "local" if provider == "local" or not (has_openai or has_azure) else provider,
    }


def build_context(profile: dict, quality: dict, anomalies: list, sample: list, meta: dict) -> dict:
    return {
        "dataset": meta.get("filename", ""),
        "rows": profile.get("row_count", 0),
        "columns": [{"name": p["name"], "type": p["type"], "nulls": p["nulls"],
                      "uniques": p["uniques"], **{k: p[k] for k in ("min", "max", "avg") if k in p}}
                     for p in profile.get("profiles", [])],
        "quality": {k: quality.get(k) for k in ("general", "completitud", "unicidad", "validez", "consistencia")},
        "issues": quality.get("issues", [])[:10],
        "anomalies": anomalies[:10],
        "sample": sample[:8],
    }


def _fmt_num(x):
    try:
        return f"{float(x):,.2f}"
    except (ValueError, TypeError):
        return str(x)


ENGINES = {
    "estadistico": "Análisis estadístico · Python sobre tus datos reales",
    "ml": "Machine Learning · Isolation Forest (detección de anomalías)",
    "generativa": "IA generativa · LLM externo con contexto verificado",
}


def _to_float(v):
    try:
        f = float(str(v).replace(",", "").strip())
        import math
        return f if math.isfinite(f) else None
    except (ValueError, TypeError):
        return None


def python_compute(question: str, columns: list, rows: list, col_types: dict) -> str | None:
    """Agregaciones exactas calculadas en Python sobre TODAS las filas.

    Devuelve respuesta o None si la pregunta no es una agregación interpretable
    con confianza. Nunca estima: solo opera sobre datos reales.
    """
    q = (question or "").lower().strip()
    if not rows or not columns:
        return None
    num_cols = [c for c in columns if col_types.get(c) in ("entero", "decimal")]
    txt_cols = [c for c in columns if c not in num_cols]
    if not num_cols:
        return None

    def find_col(names, prefer_num=True):
        pool = num_cols if prefer_num else columns
        for c in pool:
            if c.lower() in q:
                return c
        # por token (evita tokens de 1-2 letras)
        best, best_hit = None, 0
        for c in pool:
            toks = [t for t in re.split(r"[^a-z0-9áéíóúñ]+", c.lower()) if len(t) > 2]
            hit = sum(1 for t in toks if t in q)
            if hit > best_hit:
                best, best_hit = c, hit
        return best

    # columna de medida: mencionada, o 'total'/'monto'/'importe', o primera numérica
    measure = find_col(num_cols)
    if not measure:
        for cand in ("total", "monto", "importe", "valor", "precio", "cantidad"):
            if cand in [c.lower() for c in num_cols]:
                measure = next(c for c in num_cols if c.lower() == cand)
                break
    if not measure:
        measure = num_cols[0]
    # columna de agrupación: solo si la pregunta la pide (por X, categoría, top...)
    group = None
    wants_group = bool(re.search(r"\bpor\b", q)) or any(
        k in q for k in ["categoria", "categoría", "grupo", "ciudad", "producto",
                         "cliente", "tipo", "mayor", "mayores", "top", "desglos"])
    if wants_group:
        m = re.search(r"por\s+([a-záéíóúñ_ ]+)", q)
        if m:
            group = find_col(txt_cols, prefer_num=False)
        if not group:
            for cand in ("categoria", "categoría", "tipo", "grupo", "ciudad", "producto", "cliente"):
                if cand in [c.lower() for c in txt_cols]:
                    group = next(c for c in txt_cols if c.lower() == cand)
                    break
    # operación (orden: palabras inequívocas primero; 'total' solo puede ser columna)
    if any(k in q for k in ["suma", "sumar"]):
        art, op, op_name = "La", "sum", "suma total"
    elif any(k in q for k in ["promedio", "media", "average"]):
        art, op, op_name = "El", "mean", "promedio"
    elif any(k in q for k in ["mínimo", "minimo", "menor", "mín ", "min "]):
        art, op, op_name = "El", "min", "mínimo"
    elif any(k in q for k in ["máximo", "maximo", "mayor valor", "max "]):
        art, op, op_name = "El", "max", "máximo"
    elif any(k in q for k in ["cuánt", "cuant", "conteo", "contar", "número de", "numero de"]):
        art, op, op_name = "El", "count", "conteo"
    elif any(k in q for k in ["total", "mayor", "mayores", "top"]):
        art, op, op_name = "La", "sum", "suma total"
    else:
        return None
    vals = [(_to_float(r.get(measure, "")), r) for r in rows]
    vals = [(v, r) for v, r in vals if v is not None]
    if not vals and op != "count":
        return None
    n = len(rows)
    if group and op in ("sum", "mean", "count"):
        agg: dict = {}
        for v, r in (vals if op != "count" else [(1, r) for r in rows]):
            g = str(r.get(group, "")).strip() or "(vacío)"
            agg.setdefault(g, []).append(v)
        if not agg:
            return None
        scored = {g: (sum(v) if op == "sum" else (sum(v) / len(v) if op == "mean" else len(v))) for g, v in agg.items()}
        top = sorted(scored.items(), key=lambda kv: kv[1], reverse=True)[:5]
        lines = [f"{g}: {_fmt_num(v)}" for g, v in top]
        return (f"{art} {op_name} de '{measure}' por '{group}' (calculado en Python sobre {n} registros) es: "
                + "; ".join(lines) + ".")
    if op == "sum":
        return f"{art} {op_name} de '{measure}' es {_fmt_num(sum(v for v, _ in vals))} ({len(vals)} valores, {n} registros)."
    if op == "mean":
        s = sum(v for v, _ in vals)
        return f"{art} {op_name} de '{measure}' es {_fmt_num(s / len(vals))} ({len(vals)} valores, {n} registros)."
    if op == "min":
        return f"{art} {op_name} de '{measure}' es {_fmt_num(min(v for v, _ in vals))} ({n} registros)."
    if op == "max":
        return f"{art} {op_name} de '{measure}' es {_fmt_num(max(v for v, _ in vals))} ({n} registros)."
    if op == "count":
        # "cuántos X": cuenta filas donde algún valor equals X
        m2 = re.search(r"(?:cuánt[oa]s?|conteo|contar|número de|numero de)\s+(.+)", q)
        if m2:
            needle = m2.group(1).strip().strip("?¿")[:60]
            hit = sum(1 for r in rows if any(str(r.get(c, "")).strip().lower() == needle for c in columns))
            if hit:
                return f"Hay {hit} registros con valor '{needle}' ({n} registros en total)."
        return f"El dataset contiene {n} registros y {len(columns)} columnas."
    return None


def local_answer(question: str, ctx: dict) -> str:
    q = (question or "").lower().strip()
    rows = ctx.get("rows", 0)
    cols = ctx.get("columns", [])
    qual = ctx.get("quality", {})
    issues = ctx.get("issues", [])
    anoms = ctx.get("anomalies", [])
    sample = ctx.get("sample", [])
    col_names = [c["name"] for c in cols]

    def col_detail(name):
        for c in cols:
            if c["name"].lower() == name.lower():
                return c
        return None

    # resumen
    if any(k in q for k in ["resume", "resumen", "describe", "qué contiene", "que contiene", "explícame", "explicame"]):
        lines = [f"El conjunto '{ctx.get('dataset','')}' contiene {rows} registros y {len(cols)} columnas ({', '.join(col_names[:8])}).",
                 f"La calidad general es {qual.get('general','—')}%. Completitud {qual.get('completitud','—')}%, unicidad {qual.get('unicidad','—')}%, validez {qual.get('validez','—')}%, consistencia {qual.get('consistencia','—')}%."] 
        if issues:
            lines.append("Principales problemas: " + "; ".join(f"{i['column']}: {i['problem']}" for i in issues[:3]) + ".")
        if anoms:
            lines.append(f"Se detectaron {len(anoms)} anomalías que conviene revisar antes de usar el dataset.")
        else:
            lines.append("No se detectaron anomalías relevantes.")
        return " ".join(lines)
    # cuántos registros
    if "cuánt" in q or "cuant" in q or "cuantos registros" in q or "cuántas filas" in q or "cuantas filas" in q or "tamaño" in q or "registros tiene" in q:
        return f"El archivo tiene {rows} registros y {len(cols)} columnas: {', '.join(col_names)}."
    # columnas / tipos
    if "columna" in q and ("cuál" in q or "cual" in q or "lista" in q or "tiene" in q or "tipos" in q or "tipo" in q):
        parts = [f"{c['name']} ({c['type']})" for c in cols]
        return "Columnas detectadas: " + "; ".join(parts) + "."
    # vacíos
    if "vacío" in q or "vacio" in q or "nulo" in q or "faltante" in q or "missing" in q:
        ranked = sorted(cols, key=lambda c: c.get("nulls", 0), reverse=True)[:5]
        top = "; ".join(f"{c['name']}: {c['nulls']} nulos" for c in ranked if c.get("nulls"))
        return ("Las columnas con más valores vacíos son: " + top + ".") if top else "No hay valores vacíos relevantes."
    # duplicados
    if "duplicad" in q:
        d = next((i for i in issues if "duplicad" in i.get("problem", "").lower()), None)
        return ("Sí. " + d["problem"] + f" Columna/alcance: {d['column']}." if d else "No se detectaron registros duplicados.")
    # promedio de X
    m = re.search(r"promedio(?: de| del| de la)?\s+([a-z0-9_áéíóúñ\. ]+)", q)
    if "promedio" in q or "media" in q or "average" in q:
        target = (m.group(1).strip() if m else "")
        # busca columna mencionada
        for c in cols:
            if c["name"].lower() in q or (target and target in c["name"].lower()):
                if "avg" in c:
                    return f"El promedio de '{c['name']}' es {_fmt_num(c['avg'])} (mín {_fmt_num(c.get('min'))}, máx {_fmt_num(c.get('max'))})."
                return f"La columna '{c['name']}' es de tipo {c['type']} y no corresponde calcular promedio."
        avgs = [f"{c['name']}: {_fmt_num(c['avg'])}" for c in cols if "avg" in c]
        return ("Promedios disponibles: " + "; ".join(avgs) + ".") if avgs else "No hay columnas numéricas para promediar."
    # máximo / mínimo / categoría con mayores ventas genérico
    if any(k in q for k in ["mayor", "máximo", "maximo", "top", "categoría", "categoria"]):
        # intenta agregación real sobre muestra+contexto no disponible completo -> usa stats
        num_cols = [c for c in cols if "max" in c]
        if num_cols:
            c = num_cols[0]
            return f"En '{c['name']}' el valor máximo es {_fmt_num(c.get('max'))} y el mínimo {_fmt_num(c.get('min'))}, promedio {_fmt_num(c.get('avg'))}. Para el desglose por categoría, revisa la columna de texto con más repeticiones en la vista previa."
        return "No hay columnas numéricas para determinar máximos."
    # anomalías
    if "anomal" in q:
        if not anoms:
            return "No se encontraron anomalías. Los valores están dentro de la distribución normal."
        parts = [f"Fila {a.get('row_line', a.get('line','?'))} columna '{a.get('column_name', a.get('column','?'))}' valor {a.get('value','')} — {a.get('reason','')}" for a in anoms[:5]]
        return f"Se encontraron {len(anoms)} anomalías: " + "; ".join(parts) + "."
    # calidad / problemas
    if "calidad" in q or "problema" in q or "error" in q:
        base = f"Calidad general {qual.get('general','—')}% (completitud {qual.get('completitud','—')}%, unicidad {qual.get('unicidad','—')}%, validez {qual.get('validez','—')}%, consistencia {qual.get('consistencia','—')}%). "
        if issues:
            base += "Problemas: " + "; ".join(f"{i['column']}: {i['problem']} (severidad {i.get('severity','media')})" for i in issues[:5]) + "."
        return base
    # qué corregir primero
    if "corregir" in q or "recomien" in q or "debería" in q or "deberia" in q or "qué hago" in q or "que hago" in q or "prioridad" in q:
        return recommendations(ctx)
    # columna específica: "qué sabes de edad"
    for c in cols:
        if c["name"].lower() in q and len(q) < 60:
            d = f"Columna '{c['name']}': tipo {c['type']}, {c.get('nulls',0)} nulos, {c.get('uniques',0)} únicos."
            if "avg" in c:
                d += f" Mín {_fmt_num(c.get('min'))}, máx {_fmt_num(c.get('max'))}, promedio {_fmt_num(c.get('avg'))}."
            return d
    # fallback: respuesta guiada con datos reales
    return (f"Con base en los datos reales ({rows} registros, {len(cols)} columnas, calidad {qual.get('general','—')}%), "
            "puedo ayudarte con: número de registros, columnas y tipos, valores vacíos, duplicados, promedios, anomalías, calidad o recomendaciones. "
            "Ejemplos: '¿Qué columnas tienen más valores vacíos?', '¿Cuál es el promedio de X?', 'Resume este dataset'.")


def recommendations(ctx: dict) -> str:
    rows = ctx.get("rows", 0)
    qual = ctx.get("quality", {})
    issues = ctx.get("issues", [])
    anoms = ctx.get("anomalies", [])
    recs = []
    total_nulls = sum(c.get("nulls", 0) for c in ctx.get("columns", []))
    if total_nulls:
        worst = sorted(ctx.get("columns", []), key=lambda c: c.get("nulls", 0), reverse=True)[0]
        pct = round(worst.get("nulls", 0) / rows * 100, 1) if rows else 0
        recs.append(f"1. Revisar la columna '{worst['name']}' ({worst.get('nulls',0)} nulos, {pct}%). Define si se imputan, se descartan o se corrigen en origen.")
    for i in issues[:4]:
        if "duplicad" in i.get("problem", "").lower():
            recs.append(f"2. Existen {i.get('affected',0)} registros duplicados. Elimínalos o define una clave única antes de analizar.")
        elif "negativo" in i.get("problem", "").lower():
            recs.append(f"3. La columna '{i['column']}' presenta valores fuera del rango esperado ({i['problem']}). Valida reglas de captura.")
        elif "correo" in i.get("column", "").lower() or "vacío" in i.get("problem", ""):
            if not any("Revisar la columna" in r for r in recs):
                recs.append(f"4. Atender '{i['column']}': {i['problem']}")
    if anoms:
        recs.append(f"{len(recs)+1}. Se recomienda revisar las {len(anoms)} anomalías detectadas antes de usar este dataset para análisis posteriores.")
    if not recs:
        return "El dataset está en buen estado. Como mantenimiento: documenta las columnas, versiona el archivo y programa el pipeline para monitoreo continuo."
    head = f"Se encontraron {total_nulls} valores faltantes. Recomendaciones generadas automáticamente:\n" if total_nulls else "Recomendaciones generadas automáticamente:\n"
    return head + "\n".join(recs)


def summary_text(ctx: dict) -> str:
    return local_answer("resume este dataset", ctx)


def try_external(question: str, ctx: dict) -> str | None:
    """Intenta OpenAI o Azure si hay claves. Devuelve None si no configurado o falla."""
    st = provider_status()
    if st["mode"] not in ("openai", "azure"):
        return None
    prompt = ("Eres un asistente de datos. Responde SOLO con base en el contexto JSON. "
              "Si el dato no está, dilo. Sé conciso y en español.\nCONTEXTO:\n" + json.dumps(ctx, ensure_ascii=False)[:6000]
              + "\nPREGUNTA: " + question)
    try:
        if st["mode"] == "openai" and os.environ.get("OPENAI_API_KEY"):
            req = urllib.request.Request(
                "https://api.openai.com/v1/chat/completions",
                data=json.dumps({"model": os.environ.get("OPENAI_MODEL", "gpt-4o-mini"),
                                 "messages": [{"role": "user", "content": prompt}],
                                 "max_tokens": 600, "temperature": 0.2}).encode(),
                headers={"Authorization": "Bearer " + os.environ["OPENAI_API_KEY"], "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=25) as r:
                data = json.loads(r.read().decode())
                return data["choices"][0]["message"]["content"].strip()
        if st["mode"] == "azure" and os.environ.get("AZURE_OPENAI_ENDPOINT"):
            ep = os.environ["AZURE_OPENAI_ENDPOINT"].rstrip("/")
            dep = os.environ.get("AZURE_OPENAI_DEPLOYMENT", "gpt-4o-mini")
            url = f"{ep}/openai/deployments/{dep}/chat/completions?api-version=2024-08-01-preview"
            req = urllib.request.Request(
                url, data=json.dumps({"messages": [{"role": "user", "content": prompt}],
                                      "max_tokens": 600, "temperature": 0.2}).encode(),
                headers={"api-key": os.environ["AZURE_OPENAI_API_KEY"], "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=25) as r:
                data = json.loads(r.read().decode())
                return data["choices"][0]["message"]["content"].strip()
    except Exception:
        return None
    return None


def answer(question: str, ctx: dict, full_rows: list | None = None, columns: list | None = None) -> dict:
    """Pipeline honesto: generativa (si hay LLM) -> cálculo Python -> estadística local.

    kind: estadistico | ml | generativa. Nunca inventa: sin datos, lo dice.
    """
    q = (question or "").lower()
    ext = try_external(question, ctx)
    if ext:
        return {"answer": ext, "source": provider_status()["mode"],
                "kind": "generativa", "engine": ENGINES["generativa"],
                "context_rows": ctx.get("rows", 0)}
    if full_rows is not None and columns is not None:
        col_types = {c.get("name"): c.get("type") for c in ctx.get("columns", [])}
        calc = python_compute(question, columns, full_rows, col_types)
        if calc:
            return {"answer": calc, "source": "local",
                    "kind": "estadistico", "engine": ENGINES["estadistico"],
                    "context_rows": ctx.get("rows", 0)}
    kind = "ml" if "anomal" in q else "estadistico"
    return {"answer": local_answer(question, ctx), "source": "local",
            "kind": kind, "engine": ENGINES[kind],
            "context_rows": ctx.get("rows", 0)}


def local_kind(question: str) -> tuple:
    q = (question or "").lower()
    kind = "ml" if "anomal" in q else "estadistico"
    return kind, ENGINES[kind]
