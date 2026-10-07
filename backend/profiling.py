"""Perfilado dinámico, calidad y reglas. Genérico: cualquier CSV tabular (1-30 columnas)."""
from __future__ import annotations
import math
import re
from datetime import date

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def infer_type(values: list[str]) -> str:
    vals = [v for v in (values or []) if v != "" and v is not None]
    if not vals:
        return "texto"
    # booleano
    low = [v.strip().lower() for v in vals]
    if all(v in {"true", "false", "si", "no", "sí", "0", "1", "verdadero", "falso", "s", "n"} for v in low):
        # ambiguo con enteros 0/1; prioriza entero si todos son 0/1 numéricos
        if all(v in {"0", "1"} for v in low):
            return "entero"
        return "booleano"
    # entero
    try:
        for v in vals:
            iv = int(str(v).replace(",", "").strip())
            if str(float(str(v).replace(",", ""))).strip() not in (str(iv), str(iv) + ".0"):
                # permite "12" pero no "12.5"
                float_v = float(str(v).replace(",", ""))
                if not float_v.is_integer():
                    raise ValueError()
        return "entero"
    except (ValueError, TypeError):
        pass
    # decimal
    ok = True
    for v in vals:
        try:
            f = float(str(v).replace(",", "").strip())
            if not math.isfinite(f):
                ok = False
                break
        except (ValueError, TypeError):
            ok = False
            break
    if ok:
        return "decimal"
    # fecha ISO
    if all(DATE_RE.match(v.strip()) for v in vals):
        try:
            for v in vals:
                date.fromisoformat(v.strip())
            return "fecha"
        except ValueError:
            pass
    # fecha genérica corta
    if all(re.match(r"^\d{1,2}[/-]\d{1,2}[/-]\d{2,4}$", v.strip()) for v in vals):
        return "fecha"
    return "texto"


def to_float(v: str):
    try:
        f = float(str(v).replace(",", "").strip())
        return f if math.isfinite(f) else None
    except (ValueError, TypeError):
        return None


def profile_dataset(columns: list[str], rows: list[dict]) -> dict:
    """Devuelve perfil por columna + resumen global. Todo calculado, nada manual."""
    n = len(rows)
    col_profiles = []
    total_nulls = 0
    for c in columns:
        vals = [str(r.get(c, "")) for r in rows]
        nulls = sum(1 for v in vals if v.strip() == "")
        total_nulls += nulls
        non_empty = [v for v in vals if v.strip() != ""]
        uniques = len(set(non_empty))
        dtype = infer_type(vals)
        entry = {
            "name": c, "type": dtype, "nulls": nulls,
            "null_pct": round(nulls / n * 100, 2) if n else 0,
            "uniques": uniques, "duplicates": max(0, len(non_empty) - uniques),
        }
        if dtype in ("entero", "decimal"):
            nums = [to_float(v) for v in non_empty]
            nums = [x for x in nums if x is not None]
            if nums:
                entry["min"] = min(nums)
                entry["max"] = max(nums)
                entry["avg"] = round(sum(nums) / len(nums), 4)
                s = sorted(nums)
                entry["median"] = s[len(s) // 2]
                # distribución en 10 cubetas
                lo, hi = s[0], s[-1]
                buckets = [0] * 10
                if hi > lo:
                    for x in nums:
                        idx = min(9, int((x - lo) / (hi - lo) * 10))
                        buckets[idx] += 1
                entry["distribution"] = buckets
        elif dtype == "texto":
            lens = [len(v) for v in non_empty]
            if lens:
                entry["min_len"] = min(lens)
                entry["max_len"] = max(lens)
                # top valores
                from collections import Counter
                entry["top_values"] = [{"value": k, "count": v} for k, v in Counter(non_empty).most_common(5)]
        col_profiles.append(entry)
    # duplicados de fila completa
    seen = set()
    dups = 0
    for r in rows:
        key = tuple(str(r.get(c, "")) for c in columns)
        if key in seen:
            dups += 1
        seen.add(key)
    return {
        "columns": columns, "row_count": n, "column_count": len(columns),
        "nulls": total_nulls, "duplicates": dups,
        "profiles": col_profiles,
    }


def quality_score(columns: list[str], rows: list[dict]) -> dict:
    """Completitud, unicidad, validez, consistencia + score general 0-100."""
    n = len(rows)
    if not n:
        return {"general": 0, "completitud": 0, "unicidad": 0, "validez": 0, "consistencia": 0, "issues": []}
    total_cells = n * len(columns)
    nulls = sum(1 for r in rows for c in columns if str(r.get(c, "")).strip() == "")
    completitud = round((total_cells - nulls) / total_cells * 100, 2) if total_cells else 100
    # unicidad: filas únicas / total
    seen = set()
    dup_rows = 0
    for r in rows:
        key = tuple(str(r.get(c, "")) for c in columns)
        if key in seen:
            dup_rows += 1
        seen.add(key)
    unicidad = round((n - dup_rows) / n * 100, 2)
    # validez: por tipo inferido, celdas que no mezclan tipo
    invalid_cells = 0
    mixed_cols = []
    issues = []
    for c in columns:
        vals = [str(r.get(c, "")) for r in rows]
        non_empty = [v for v in vals if v.strip() != ""]
        dtype = infer_type(vals)
        bad = 0
        if dtype in ("entero", "decimal"):
            for v in non_empty:
                if to_float(v) is None:
                    bad += 1
        elif dtype == "fecha":
            for v in non_empty:
                if not (DATE_RE.match(v.strip()) or re.match(r"^\d{1,2}[/-]\d{1,2}[/-]\d{2,4}$", v.strip())):
                    bad += 1
        invalid_cells += bad
        if bad:
            mixed_cols.append(c)
    validez = round((total_cells - invalid_cells) / total_cells * 100, 2) if total_cells else 100
    # consistencia: heurísticas (negativos inesperados, emails vacíos, fechas futuras/absurdas, texto en numéricos)
    incons = 0
    for c in columns:
        vals = [str(r.get(c, "")) for r in rows]
        dtype = infer_type(vals)
        lc = c.lower()
        if dtype in ("entero", "decimal"):
            nums = [to_float(v) for v in vals if v.strip() != ""]
            nums = [x for x in nums if x is not None]
            if nums and ("edad" in lc or "cantidad" in lc or "precio" in lc or "total" in lc or "piezas" in lc):
                neg = sum(1 for x in nums if x < 0)
                if neg:
                    incons += neg
                    issues.append({"column": c, "problem": f"{neg} valores negativos inesperados.", "severity": "alta", "affected": neg})
            # fuera de rango extremo (z-score simple)
            if len(nums) >= 5:
                mean = sum(nums) / len(nums)
                var = sum((x - mean) ** 2 for x in nums) / len(nums)
                sd = math.sqrt(var) if var > 0 else 0
                if sd > 0:
                    outliers = sum(1 for x in nums if abs(x - mean) > 4 * sd)
                    incons += outliers
        if "correo" in lc or "email" in lc or "mail" in lc:
            empty = sum(1 for v in vals if v.strip() == "")
            if empty:
                issues.append({"column": c, "problem": f"{empty} valores vacíos.", "severity": "media" if empty / n < 0.2 else "alta", "affected": empty})
            bad_mail = sum(1 for v in vals if v.strip() != "" and not EMAIL_RE.match(v.strip()))
            if bad_mail:
                incons += bad_mail
                issues.append({"column": c, "problem": f"{bad_mail} correos con formato inválido.", "severity": "media", "affected": bad_mail})
        # nulos por columna
        null_c = sum(1 for v in vals if v.strip() == "")
        if null_c and ("correo" not in lc and "email" not in lc):
            if null_c / n > 0.05:
                issues.append({"column": c, "problem": f"{null_c} valores vacíos ({round(null_c/n*100,1)}%).", "severity": "media" if null_c / n < 0.2 else "alta", "affected": null_c})
    # duplicados como issue
    if dup_rows:
        issues.append({"column": "(filas)", "problem": f"{dup_rows} registros duplicados.", "severity": "media", "affected": dup_rows})
    if mixed_cols:
        for c in mixed_cols:
            issues.append({"column": c, "problem": "Columna con datos mezclados o inválidos.", "severity": "media", "affected": 0})
    consistencia = round(max(0, (total_cells - incons) / total_cells * 100), 2) if total_cells else 100
    general = round((completitud + unicidad + validez + consistencia) / 4, 2)
    return {"general": general, "completitud": completitud, "unicidad": unicidad,
            "validez": validez, "consistencia": consistencia, "issues": issues,
            "nulls": nulls, "duplicates": dup_rows}


CONDITIONS = {
    "not_empty": "no puede estar vacío",
    "unique": "debe ser único",
    "gte": "debe ser mayor o igual a",
    "gt": "debe ser mayor que",
    "lte": "debe ser menor o igual a",
    "lt": "debe ser menor que",
    "eq": "debe ser igual a",
    "neq": "debe ser distinto de",
    "valid_format": "debe tener formato válido",
    "contains": "debe contener",
}


def evaluate_rule(column: str, condition: str, value: str, columns: list[str], rows: list[dict]) -> dict:
    """Evalúa una regla personalizada. Devuelve {passed, failed, failures[] (máx 20 ejemplos)}."""
    failures = []
    if column not in columns:
        return {"passed": 0, "failed": len(rows), "failures": [], "error": f"Columna '{column}' no existe."}
    seen_vals: set = set()
    dup_seen: set = set()
    if condition == "unique":
        from collections import Counter
        counts = Counter(str(r.get(column, "")) for r in rows)
        for i, r in enumerate(rows, 2):
            v = str(r.get(column, ""))
            if counts[v] > 1:
                failures.append({"line": i, "value": v})
        return {"passed": len(rows) - len(failures), "failed": len(failures), "failures": failures[:20]}
    for i, r in enumerate(rows, 2):
        v = str(r.get(column, ""))
        ok = True
        if condition == "not_empty":
            ok = v.strip() != ""
        elif condition == "valid_format":
            lc = column.lower()
            if "correo" in lc or "email" in lc or "mail" in lc:
                ok = v.strip() == "" or bool(EMAIL_RE.match(v.strip()))
            elif "fecha" in lc or "date" in lc:
                ok = v.strip() == "" or bool(DATE_RE.match(v.strip()) or re.match(r"^\d{1,2}[/-]\d{1,2}[/-]\d{2,4}$", v.strip()))
            else:
                ok = v.strip() != ""
        elif condition in ("gte", "gt", "lte", "lt", "eq", "neq"):
            f = to_float(v)
            t = to_float(value)
            if f is None or t is None:
                ok = False
            elif condition == "gte":
                ok = f >= t
            elif condition == "gt":
                ok = f > t
            elif condition == "lte":
                ok = f <= t
            elif condition == "lt":
                ok = f < t
            elif condition == "eq":
                ok = f == t
            elif condition == "neq":
                ok = f != t
        elif condition == "contains":
            ok = value.lower() in v.lower()
        else:
            return {"passed": 0, "failed": len(rows), "failures": [], "error": "Condición inválida."}
        if not ok:
            failures.append({"line": i, "value": v})
    return {"passed": len(rows) - len(failures), "failed": len(failures), "failures": failures[:20]}
