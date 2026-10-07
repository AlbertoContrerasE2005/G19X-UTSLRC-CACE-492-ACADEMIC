# DataOps Final

Plataforma local del ciclo de vida de los datos: subir archivos
(CSV, Excel, SQL), validar calidad, detectar anomalías con IA,
aprobar con criterio humano, programar pipelines y monitorear todo.

**Stack (sin frameworks ni nube):** HTML + CSS + JavaScript vanilla,
PHP 8, Python 3.12 (FastAPI), MySQL/MariaDB 10.4 + SQL.
Todo corre en tu equipo: web `127.0.0.1:8080`, API `127.0.0.1:8010`,
base de datos `127.0.0.1:3307`.

---

## 1. Requisitos

- **Python 3.12** (64 bits) con `py` en el PATH.
- **PHP 8** (sirve el de XAMPP: `C:\xampp\php\php.exe`).
- **MariaDB/MySQL** accesible en `127.0.0.1:3307` con usuario `root`
  sin contraseña y permiso de crear bases. Con XAMPP:
  1. Abre *XAMPP Control Panel* → *Start* en MySQL, o
  2. `C:\xampp\mysql\bin\mysqld.exe --console` (puerto por defecto 3306;
     este proyecto usa **3307**, ver variables abajo).
- Puertos libres: `8010` y `8080`.

Variables opcionales (si tu MySQL es distinto):

```powershell
$env:DATAOPS_DB_HOST = "127.0.0.1"
$env:DATAOPS_DB_PORT = "3307"
$env:DATAOPS_DB_USER = "root"
$env:DATAOPS_DB_PASSWORD = ""
$env:DATAOPS_DB_NAME = "dataops"
```

## 2. Instalación (solo la primera vez)

```powershell
cd C:\ruta\del\proyecto
py -3.12 -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
```

Necesitas internet solo para este paso.

## 3. Iniciar la app

```powershell
.\.venv\Scripts\python start.py
```

Esto hace, en orden:

1. Crea la base `dataops` y las 19 tablas (`db/schema.sql`).
2. Levanta la API Python en http://127.0.0.1:8010 .
3. Levanta la web PHP en http://127.0.0.1:8080 y abre tu navegador.

Deja esa consola abierta. Para detener: `Ctrl+C`.

> Si el puerto MySQL no es 3307, define `DATAOPS_DB_*` antes de
> ejecutar `start.py` en la misma consola.

## 4. Primer uso (5 minutos)

1. En http://127.0.0.1:8080 verás **"Crea tu cuenta inicial"**.
   Regístrate (usuario ≥3 letras, clave ≥10 caracteres). Serás admin.
2. Ve a **Archivos → Subir** y carga `examples/ventas_ejemplo.csv`
   (70 filas de prueba incluidas en el repo).
3. Pulsa **Ejecutar**. En segundos verás el resultado:
   **64 cargadas, 4 inválidas y 2 alertas de IA**.
4. Entra a la ejecución (**Ver**), filtra **Solo pendientes**,
   escribe un motivo (ej. `Pico validado`) y **Aprueba** una alerta;
   **Rechaza** la otra con otro motivo.
5. Descarga el CSV de resultados y revisa el **Resumen**
   (métricas de 7 días) y **Monitoreo**.

Cuenta demo precargada (si existe en tu copia): usuario `demo`,
clave `Demo2026!!segura`.

## 5. Guía por función

| Quiero… | Dónde |
|---|---|
| Subir CSV/Excel/SQL (10 MiB, 20000 filas, cualquier columna) | Archivos → Subir |
| Ver perfil, calidad y filas de un archivo | Archivos → clic en el archivo |
| Crear un pipeline (ej. *Inventario*) | Pipelines → Nuevo |
| Asignar archivo + frecuencia (manual/15/60/1440) | Pipelines → Editar |
| Ejecutar ahora | Archivos → Ejecutar, o Pipelines → Ejecutar |
| Revisar alertas de IA | Ejecuciones → Ver → Solo pendientes |
| Descargar resultados/incidencias | Dentro de la ejecución |
| Programar ejecuciones solas | Pipelines → Editar → Frecuencia |
| Preguntar a la IA sobre tus datos | Sección IA (elige proyecto y dataset) |
| Generar reporte JSON/CSV/PDF | Reportes → Generar |
| Crear usuarios (admin) | Usuarios |
| Ver actividad y alertas | Actividad / Alertas / Dashboard |

Formatos aceptados:
- **CSV**: coma o punto y coma, UTF-8, 1–30 columnas.
- **Excel** `.xlsx`: primera hoja, primera fila = cabecera.
- **SQL**: `INSERT INTO tabla (col1, col2) VALUES (...);`.

## 6. Probar que todo funciona

```powershell
.\.venv\Scripts\python -m unittest discover -s tests -v
node --check web/app.js
php -l php/router.php
```

38 pruebas: auth y roles, cargas, límites, pipelines, proyectos,
IA de ventas y genérica, aprobación, métricas, plataforma completa,
estrés de 5000 filas, recuperación e idempotencia.

## 7. Estructura del proyecto

```text
backend/app.py          API FastAPI (auth, datasets, runs, métricas)
backend/core.py         Parseo, validación, IA IsolationForest, worker
backend/platform_api.py Proyectos, calidad, anomalías, IA chat, reportes…
backend/db.py           Conexión MySQL + creación de esquema
backend/profiling.py    Perfilado y score de calidad (puro Python)
backend/ai_service.py   IA local (estadística + ML; OpenAI/Azure opcional)
backend/reports.py      Reportes JSON/CSV/PDF
db/schema.sql           19 tablas MySQL
php/router.php          Entrada web :8080 (estáticos + proxy /api)
web/                    app.js + styles.css + index.html (SPA, tema oscuro)
examples/               CSV de ejemplo y referencia de IA
tests/                  4 archivos, 38 pruebas
docs/PRD.md             Requisitos del sistema
```

## 8. Problemas comunes

| Síntoma | Causa y solución |
|---|---|
| `Puerto 8010/8080 ocupado` | Cierra la otra consola de `start.py`. |
| `MySQL no responde` | Arranca MariaDB en el puerto 3307 o define `DATAOPS_DB_*`. |
| `409 Ya hay una ejecución` | Solo corre 1 a la vez; espera a que termine. |
| `413 Archivo hasta 10 MiB` | Parte el archivo en trozos menores. |
| `502 API apagada` | La consola de `start.py` se cerró; vuelve a ejecutarlo. |
