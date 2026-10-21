"""Reglas de validacion de datos.

Dos modos: ventas (5 columnas exactas, reglas estrictas) y generico
(primera columna como clave unica).
"""

import re
from datetime import date
from decimal import Decimal, InvalidOperation

from backend.settings import COLUMNS

# ---------------------------------------------------------------- validación


def validate_sales(rows):
    """Reglas estrictas de ventas. Calcula total y features para IA."""
    from datetime import date

    results, seen = [], set()
    for number, raw in enumerate(rows, 2):
        data = {k: str(raw[k]).strip() for k in COLUMNS}
        errors = []

        ident = data["id"]
        if not ident or len(ident) > 64:
            errors.append("ID obligatorio hasta 64 caracteres")
        if ident in seen:
            errors.append("ID repetido en el archivo")
        seen.add(ident)

        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", data["fecha"]):
            errors.append("Fecha formato AAAA-MM-DD")
        else:
            try:
                date.fromisoformat(data["fecha"])
            except ValueError:
                errors.append("Fecha inexistente")

        if not data["producto"] or len(data["producto"]) > 120:
            errors.append("Producto obligatorio hasta 120 caracteres")

        try:
            qty = Decimal(data["cantidad"])
            if (
                not qty.is_finite()
                or qty != qty.to_integral_value()
                or not 0 < qty <= 1_000_000_000
            ):
                raise ValueError()
        except (ValueError, InvalidOperation):
            errors.append("Cantidad entera 1 a 1000000000")

        try:
            price = Decimal(data["precio_unitario"])
            if (
                not price.is_finite()
                or not 0 <= price <= 1_000_000_000_000
                or price.as_tuple().exponent < -2
            ):
                raise ValueError()
        except (ValueError, InvalidOperation):
            errors.append("Precio 0 a 1e12 con 2 decimales máximo")

        item = {
            "line": number,
            "data": data,
            "status": "invalid" if errors else "valid",
            "reason": "; ".join(errors),
            "score": None,
        }
        if not errors:
            item["features"] = [float(qty), float(price), float(qty * price)]
            data["cantidad"] = str(int(qty))
            data["precio_unitario"] = str(price.quantize(Decimal(".01")))
            data["total"] = str((qty * price).quantize(Decimal(".01")))
        results.append(item)
    return results


def validate_generic(columns, rows):
    """Validación sin plantilla: primera columna = clave única obligatoria."""
    results, seen = [], set()
    key = columns[0]
    for number, raw in enumerate(rows, 2):
        data = {k: str(raw.get(k, "")).strip() for k in columns}
        errors = []
        ident = data.get(key, "")
        if not ident or len(ident) > 256:
            errors.append(f"{key} obligatorio hasta 256 caracteres")
        if ident in seen:
            errors.append(f"{key} repetido en el archivo")
        seen.add(ident)
        if all(v == "" for v in data.values()):
            errors.append("Fila vacía")
        results.append(
            {
                "line": number,
                "data": data,
                "status": "invalid" if errors else "valid",
                "reason": "; ".join(errors),
                "score": None,
            }
        )
    return results
