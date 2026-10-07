# DataOps Final

Plataforma local simple para el ciclo de vida de los datos:
subir CSV/Excel/SQL, validar, detectar anomalías con IA,
aprobar, programar y monitorear. Paleta oscura cómoda.

**Stack:** HTML + CSS + JavaScript vanilla + PHP + Python (FastAPI)
+ MySQL/MariaDB. Sin frameworks ni nube.

## Requisitos

- Python 3.12 + `.venv` con `requirements.txt`.
- PHP 8 (XAMPP sirve) en el PATH.
- MariaDB/MySQL en `127.0.0.1:3307`, root sin clave, base `dataops`
  (la crea `start.py` solo). Ver `docs/PRD.md`.

## Iniciar

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python start.py
```

Abre http://127.0.0.1:8080, crea tu admin (clave 10+) y prueba
con el CSV de `examples/ventas_ejemplo.csv` (70 filas:
64 cargadas, 4 inválidas, 2 alertas IA).

## Probar (38 tests)

```powershell
.\.venv\Scripts\python -m unittest discover -s tests -v
node --check web/app.js
php -l php/router.php
```

Cobertura: auth/roles, CSV+Excel+SQL, límites, pipelines,
proyectos, runs, IA ventas+genérica, aprobación, métricas,
plataforma (reglas, anomalías, alertas, reportes, IA chat),
estrés 5000 filas, recuperación, programación e idempotencia.
