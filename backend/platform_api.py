"""Orquestador de la plataforma.

Registra los endpoints extendidos (proyectos, calidad, anomalías,
alertas, reportes, actividad, dashboard, IA y usuarios) sobre la app
definida en backend/app.py, sin duplicar la API base.

Cada grupo vive en su propio módulo; aquí solo se conectan.
"""

from backend import (
    platform_ai,
    platform_monitoring,
    platform_projects,
    platform_quality,
    platform_reports,
    platform_users,
)
from backend.platform_common import make_context

MODULES = (
    platform_projects,
    platform_quality,
    platform_monitoring,
    platform_reports,
    platform_ai,
    platform_users,
)


def register(app, store, current, body):
    """Conecta todos los módulos de la plataforma en la app."""
    ctx = make_context(app, store, current, body)
    for module in MODULES:
        module.register(ctx)
