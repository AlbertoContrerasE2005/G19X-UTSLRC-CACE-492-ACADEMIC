# DataOps Final

Plataforma local del ciclo de vida de los datos: subir archivos
(CSV, Excel, SQL), validar calidad, detectar anomalías con IA,
aprobar con criterio humano, programar pipelines y monitorear todo.

**Stack (sin frameworks ni nube):** HTML + CSS + JavaScript vanilla,
PHP 8, Python 3.12 (FastAPI), MySQL/MariaDB 10.4 + SQL.
Todo corre en tu equipo: web `127.0.0.1:8080`, API `127.0.0.1:8010`,
base de datos `127.0.0.1:3307`.

### Declaración

Este proyecto fue desarrollado con asistencia de inteligencia
artificial (Claude, de Anthropic). La IA participó en la
redacción del código, las pruebas y la
documentación; las decisiones de diseño, la
revisión del código y la validación
de resultados corresponden a las personas responsables del
proyecto. Toda la funcionalidad se verifica con la suite de
pruebas incluida (`tests/`, 38 pruebas).

---

## 1. Requisitos

- **Python 3.12** (64 bits) con `py` en el PATH.
- **PHP 8** (sirve el de XAMPP: `C:\xampp\php\php.exe`).
- **MariaDB/MySQL** accesible en `127.0.0.1:3307` con permiso de crear
  bases. Con XAMPP:
  1. Abre *XAMPP Control Panel* → *Start* en MySQL, o
  2. `C:\xampp\mysql\bin\mysqld.exe --datadir=<carpeta> --port=3307 --console`
     (si omites `--console`, el proceso se cierra solo en Windows).
- Puertos libres: `8010` y `8080`.

### Base de datos: usuario por defecto o el tuyo

Por omisión el proyecto conecta como `root` **sin contraseña** en
`127.0.0.1:3307`, que es como viene XAMPP. Si prefieres un usuario
propio (recomendado), créalo con estos comandos:

```sql
-- Entra como root (o el administrador de tu MariaDB) y ejecuta:
CREATE USER 'dataops'@'localhost' IDENTIFIED BY 'tu_clave_aqui';
CREATE USER 'dataops'@'127.0.0.1' IDENTIFIED BY 'tu_clave_aqui';
GRANT ALL PRIVILEGES ON dataops.* TO 'dataops'@'localhost';
GRANT ALL PRIVILEGES ON dataops.* TO 'dataops'@'127.0.0.1';
FLUSH PRIVILEGES;
```

> Concede permisos solo sobre la base `dataops`. El proyecto crea esa
> base automáticamente al arrancar; si prefieres crearla tú:
> `CREATE DATABASE dataops CHARACTER SET utf8mb4;`

Luego configura las variables **antes** de ejecutar `start.py`, en la
misma consola de PowerShell:

```powershell
$env:DATAOPS_DB_HOST     = "127.0.0.1"
$env:DATAOPS_DB_PORT     = "3307"
$env:DATAOPS_DB_USER     = "dataops"
$env:DATAOPS_DB_PASSWORD = "tu_clave_aqui"
$env:DATAOPS_DB_NAME     = "dataops"
```

O bien define las variables de forma permanente para tu usuario de
Windows (se aplican a toda consola nueva):

```powershell
[Environment]::SetEnvironmentVariable("DATAOPS_DB_USER",     "dataops", "User")
[Environment]::SetEnvironmentVariable("DATAOPS_DB_PASSWORD", "tu_clave_aqui", "User")
[Environment]::SetEnvironmentVariable("DATAOPS_DB_PORT",     "3307", "User")
[Environment]::SetEnvironmentVariable("DATAOPS_DB_NAME",     "dataops", "User")
```

El archivo `.env.example` lista todas las variables disponibles
(copialo como `.env` como guía de referencia; el proceso actual las lee
del entorno).

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

1. Crea la base `dataops` y las 20 tablas (`db/schema.sql`).
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

No viene ninguna cuenta por defecto: la primera que registres en el
paso 1 se queda como administrador. Si quieres datos de ejemplo, usa el
sembrador que se explica abajo.

### Datos de prueba (opcional)

Para arrancar con usuarios, archivos y pipelines ya listos:

```powershell
.\.venv\Scripts\python -m backend.seed
```

Crea los usuarios `demo`, `admin`, `ingeniero` y `consulta`, un proyecto,
los archivos de ejemplo (ventas, pasteles y productos SQL), un pipeline,
una regla de calidad, y ejecuta dos pipelines para que veas resultados
de inmediato.

Las claves **no están fijas en el código**: el script te las pide por
consola (la escritura queda oculta) y son las que tú elijas. Anótalas,
porque la primera vez no hay forma de recuperarlas. Si prefieres no
interactivo, define las variables antes:

```powershell
$env:DEMO_PASSWORD  = "tu_clave_demo"    # mínimo 10 caracteres
$env:ADMIN_PASSWORD = "tu_clave_admin"   # la comparten admin/ingeniero/consulta
.\.venv\Scripts\python -m backend.seed
```

Luego entra en http://127.0.0.1:8080 con `demo` y la clave que
definiste. Si ya habías creado tu propia cuenta en el paso 1, puedes
usar esa y saltarte el sembrador.

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

Las pruebas usan una base aparte llamada `dataops_test`, que borran y
vuelven a crear en cada corrida. Por eso el usuario de base de datos
de las pruebas necesita permiso sobre `dataops_test*`:

```sql
GRANT ALL PRIVILEGES ON `dataops_test%`.* TO 'dataops'@'127.0.0.1';
FLUSH PRIVILEGES;
```

Para correrlas con el usuario limitado, exporta las variables antes del
comando; si prefieres `root` sin contraseña, no necesitas nada extra.

## 7. Estructura del proyecto

```text
backend/app.py             API FastAPI (auth, datasets, runs, métricas)
backend/core.py            Parseo, validación, IA IsolationForest, worker
backend/db.py              Conexión MySQL + creación de esquema
backend/platform_api.py    Orquestador de la plataforma (registra módulos)
backend/platform_common.py Ayudantes compartidos de la plataforma
backend/platform_projects.py   Proyectos + perfil/calidad/filas de datasets
backend/platform_quality.py    Reglas, evaluación, resultados y anomalías
backend/platform_monitoring.py Alertas, actividad, dashboard y monitoreo
backend/platform_reports.py    Reportes JSON/CSV/PDF
backend/platform_ai.py         IA conversacional, resumen y recomendaciones
backend/platform_users.py      Configuración y usuarios
backend/profiling.py       Perfilado y score de calidad (puro Python)
backend/ai_service.py      IA local (estadística + ML; OpenAI/Azure opcional)
backend/reports.py         Reportes JSON/CSV/PDF
backend/seed.py            Datos de prueba (python -m backend.seed)
db/schema.sql              20 tablas MySQL
php/router.php             Entrada web :8080 (estáticos + proxy /api)
web/                       app.js + styles.css + index.html (SPA, tema oscuro)
examples/                  CSV de ejemplo y referencia de IA
tests/                     4 archivos, 38 pruebas
docs/PRD.md                Requisitos del sistema
```

## 8. Problemas comunes

| Síntoma | Causa y solución |
|---|---|
| `Puerto 8010/8080 ocupado` | Cierra la otra consola de `start.py`. |
| `MySQL no responde` | Arranca MariaDB en el puerto 3307 o define `DATAOPS_DB_*`. |
| `409 Ya hay una ejecución` | Solo corre 1 a la vez; espera a que termine. |
| `413 Archivo hasta 10 MiB` | Parte el archivo en trozos menores. |
| `502 API apagada` | La consola de `start.py` se cerró; vuelve a ejecutarlo. |
