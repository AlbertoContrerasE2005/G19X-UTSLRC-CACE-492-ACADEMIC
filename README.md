# DataOps Final

Plataforma local del ciclo de vida de los datos: subir archivos
(CSV, Excel, SQL), validar calidad, detectar anomalías con IA,
aprobar con criterio humano, programar pipelines y monitorear todo.

**Stack (sin frameworks ni nube):** HTML + CSS + JavaScript vanilla,
PHP 8, Python 3.12 (FastAPI), MySQL/MariaDB 10.4 + SQL.
Todo corre en tu equipo: web `127.0.0.1:8080`, API `127.0.0.1:8010`,
base de datos `127.0.0.1:3306` (configurable).

### Declaración

Este proyecto fue desarrollado con asistencia de inteligencia
artificial (Claude, de Anthropic). La IA participó en la
redacción del código, las pruebas y la
documentación; las decisiones de diseño, la
revisión del código y la validación
de resultados corresponden a las personas responsables del
proyecto. Toda la funcionalidad se verifica con la suite de
pruebas incluida (`tests/`, 51 pruebas).

---

## 1. Requisitos

- **Python 3.12** (64 bits) con `py` en el PATH.
- **PHP 8** (sirve el de XAMPP: `C:\xampp\php\php.exe`).
- **Node.js 18+** (solo para `node --check web/app.js`; si no lo tienes,
  puedes omitir esa comprobación).
- **MySQL 8 o MariaDB 10.4+** en `127.0.0.1:3306` (el puerto estándar).
  Sirve cualquiera: XAMPP, una instalación propia, o Docker. Si el tuyo
  usa otro puerto, se cambia en `.env`.
  → **Guía completa: [`docs/BASE-DE-DATOS.md`](docs/BASE-DE-DATOS.md)**
- Puertos libres: `8010` y `8080`.

### Base de datos: usuario por defecto o el tuyo

Por omisión el proyecto conecta como `root` **sin contraseña** en
`127.0.0.1:3306`, que es lo habitual en una instalación local. Si prefieres
un usuario propio (recomendado), créalo con estos comandos:

```sql
-- Entra como root (o el administrador de tu MySQL) y ejecuta:
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
$env:DATAOPS_DB_PORT     = "3306"
$env:DATAOPS_DB_USER     = "dataops"
$env:DATAOPS_DB_PASSWORD = "tu_clave_aqui"
$env:DATAOPS_DB_NAME     = "dataops"
```

O bien define las variables de forma permanente para tu usuario de
Windows (se aplican a toda consola nueva):

```powershell
[Environment]::SetEnvironmentVariable("DATAOPS_DB_USER",     "dataops", "User")
[Environment]::SetEnvironmentVariable("DATAOPS_DB_PASSWORD", "tu_clave_aqui", "User")
[Environment]::SetEnvironmentVariable("DATAOPS_DB_PORT",     "3306", "User")
[Environment]::SetEnvironmentVariable("DATAOPS_DB_NAME",     "dataops", "User")
```

El archivo `.env.example` lista todas las variables disponibles.
El proyecto **carga automáticamente un archivo `.env`** si existe en la raíz:
copia `.env.example` como `.env` y edítalo, y funciona sin pasos extra.

```powershell
Copy-Item .env.example .env
```

Las variables ya fijadas en el entorno tienen prioridad sobre el `.env`,
así que puedes sobreescribir algo solo para una corrida sin tocar el archivo.

Si prefieres no usar `.env`, define las variables directamente (arriba).

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

> Si tu MySQL no esta en el puerto 3306, define `DATAOPS_DB_*` antes
> de ejecutar `start.py` en la misma consola, o copia `.env.example`
> como `.env` y ajusta el puerto ahi. Ver `docs/BASE-DE-DATOS.md`.
>
> Si ya hay otra instancia de DataOps corriendo, `start.py` se detiene con
> `Puerto 8010 ocupado`. Localiza el proceso antes de cerrarlo:
>
> ```powershell
> Get-NetTCPConnection -State Listen -LocalPort 8010,8080 |
>   Select-Object LocalPort,OwningProcess
> ```
>
> Tambien sirve `netstat -ano | findstr ":8010 :8080"`.

## 4. Primer uso (5 minutos)

### Opción rápida: cuentas y datos de prueba

El repositorio no incluye la base de datos ni cuentas creadas: al arrancar,
la base queda vacía. El sembrador deja todo listo para probar: los usuarios
`demo`, `admin`, `ingeniero` y `consulta`, un proyecto, los archivos de
ejemplo (ventas, pasteles y productos SQL), un pipeline, una regla de
calidad y dos ejecuciones ya hechas.

```powershell
$env:DEMO_PASSWORD  = "Demo2026!!segura"    # cuenta `demo`
$env:ADMIN_PASSWORD = "Admin2026!!segura"   # `admin`, `ingeniero` y `consulta`
.\.venv\Scripts\python -m backend.seed
```

Las claves **no están fijas en el código**: si no defines esas variables, el
script te las pide por consola (la escritura queda oculta). Anótalas, porque
después no hay forma de recuperarlas. Con las variables de arriba quedan
estas cuentas:

| Usuario     | Clave               | Rol           |
|-------------|---------------------|---------------|
| `demo`      | `Demo2026!!segura`  | Administrador|
| `admin`     | `Admin2026!!segura` | Administrador|
| `ingeniero` | `Admin2026!!segura` | Data Engineer |
| `consulta`  | `Admin2026!!segura` | Usuario (consulta) |

> **Nota de seguridad:** son claves de demostración local. Si algún día
> expones el sistema en una red o en internet, **cámbialas de inmediato** y
> añade HTTPS, proxy y respaldos, como se describe en el PRD.

> **El sembrador también crea datos.** Además de las cuentas, deja tres
> datasets, un pipeline, una regla y dos ejecuciones; la ejecución de ventas
> ya carga **64 filas** en el destino. Por eso, si después repites el flujo
> de `docs/MVP.md` sobre la misma base, el detalle mostrará
> **0 cargadas · 64 existentes · 4 inválidas · 2 alertas**, no 64 cargadas.
>
> Para ver el resultado **64 cargadas / 4 inválidas / 2 alertas** desde cero,
> usa la opción normal (cuenta propia, base sin sembrar) **o** vacía el
> destino antes de ejecutar:
>
> ```sql
> TRUNCATE TABLE dataops.sales;
> TRUNCATE TABLE dataops.records;
> ```
>
> Eso borra solo las filas de destino; no borra usuarios, datasets ni
> historial.

Entra en http://127.0.0.1:8080 con `demo` y la clave que definiste.

### Opción normal: crear tu propia cuenta

1. En http://127.0.0.1:8080 verás **"Crea tu cuenta inicial"**.
   Regístrate (usuario ≥3 letras, clave ≥10 caracteres). Serás admin.
2. Ve a **Datasets → Cargar archivo** y carga `examples/ventas_ejemplo.csv`
   (70 filas de prueba incluidas en el repo).
3. Pulsa **Ejecutar**. En segundos verás el resultado:
   **64 cargadas, 4 inválidas y 2 alertas de IA**.
4. En el detalle de la ejecución, filtra **Solo pendientes**,
   escribe un motivo (ej. `Pico validado`) y **Aprueba** una alerta;
   **Rechaza** la otra con otro motivo.
5. Descarga el CSV de resultados y revisa el **Dashboard**
   (métricas de 7 días) y **Monitoreo**.

Las dos opciones sirven por separado: si sembraste las cuentas de prueba,
entra con `demo`; si creaste tu propia cuenta, sigue con ella y no hace
falta el sembrador. Para la demo de **64/4/2**, la opción normal es la que
parte de un destino vacío; si sembraste datos, aplica el `TRUNCATE` de
arriba o espera **0 nuevas / 64 existentes**.

## 5. Guía por función

| Quiero… | Dónde |
|---|---|
| Subir CSV/Excel/SQL (10 MiB, 20000 filas, cualquier columna) | Datasets → Cargar archivo |
| Ver perfil, calidad y filas de un archivo | Datasets → clic en el archivo |
| Crear un pipeline (ej. *Inventario*) | Pipelines → Nuevo |
| Asignar archivo + frecuencia (manual/15/60/1440) | Pipelines → Editar |
| Ejecutar ahora | Datasets → Ejecutar, o Pipelines → Ejecutar |
| Revisar alertas de IA | Detalle de la ejecución → Solo pendientes |
| Descargar resultados/incidencias | Dentro de la ejecución |
| Programar ejecuciones solas | Pipelines → Editar → Frecuencia |
| Preguntar a la IA sobre tus datos | IA / Asistente (elige proyecto y dataset) |
| Generar reporte JSON/CSV/PDF | Reportes → Generar |
| Crear usuarios (admin) | Usuarios |
| Ver actividad y alertas | Historial / Alertas / Dashboard |

> La interfaz v2.0 llama **Datasets** a lo que antes era *Archivos*, e
> **Historial** a lo que antes era *Actividad*.

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

`node --check` requiere Node.js (ver Requisitos); si no lo tienes, puedes
omitir esa comprobación y correr solo las pruebas de Python y el lint de PHP.
La suite incluye la descarga de reportes PDF: `requirements.txt` instala
`reportlab`, que es lo que genera el PDF.

51 pruebas: auth y roles, cargas, límites, pipelines, proyectos,
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
backend/app.py             Orquestador de la API: seguridad y registro de módulos
backend/api_auth.py            Autenticación, sesión y usuarios
backend/api_datasets.py        Archivos: carga, listado, perfil y plantilla
backend/api_pipelines.py       Pipelines: configuración, estado e historial
backend/api_runs.py            Ejecuciones: encolar, consultar, exportar, aprobar
backend/api_metrics.py         Resumen y métricas de operación
backend/core.py            Fachada del motor (reexporta los módulos de abajo)
backend/settings.py        Constantes, tiempo y funciones de seguridad
backend/data_io.py         Lectura de CSV/Excel/SQL y exportación a CSV
backend/validators.py      Reglas de calidad (ventas y genéricas)
backend/store.py           Acceso a MySQL y operaciones de dominio
backend/engine.py          Motor de una ejecución: valida, detecta y carga
backend/worker.py          Hilo que programa pipelines y ejecuta los runs
backend/db.py              Conexión MySQL, transacciones y creación de esquema
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
tests/base.py              Base compartida: prepara la base de pruebas
tests/test_basic.py        Flujo básico (4 pruebas)
tests/test_full.py         Batería integral (13 pruebas)
tests/test_extended.py     Estrés, idempotencia y casos de fallo (13 pruebas)
tests/test_all.py          Cobertura 1x1 y fallos provocados (16 pruebas)
tests/test_platform_modules.py  Módulos de calidad y reportes (5 pruebas)
docs/PRD.md                Requisitos del sistema
docs/MVP.md                Alcance de la primera entrega
docs/BASE-DE-DATOS.md      Cómo levantar MySQL/MariaDB
docs/DECISIONES.md         Por qué una sola ejecución, 409/503 y borrado
docs/MEJORAS_FUTURAS.md    Plan para la siguiente versión
docs/evidencias/           Bitácora de instalación limpia y capturas
```

**51 pruebas** en 5 archivos, sobre la base `dataops_test`.

## 8. Problemas comunes

| Síntoma | Causa y solución |
|---|---|
| `Puerto 8010/8080 ocupado` | Cierra la otra consola de `start.py`. Para encontrarla: `Get-NetTCPConnection -State Listen -LocalPort 8010,8080 \| Select-Object LocalPort,OwningProcess`. |
| `MySQL no responde` | Enciende tu MySQL/MariaDB o ajusta puerto y credenciales en `.env`. Ver `docs/BASE-DE-DATOS.md`. |
| `La demo muestra 0 cargadas y 64 existentes` | El sembrador ya cargó las 64 filas. Usa una base sin sembrar o vacía `dataops.sales`/`dataops.records` (ver sección 4). |
| `Descarga de PDF devuelve 500` | Falta `reportlab`: ejecuta `pip install -r requirements.txt`. |
| `409 Ya hay una ejecución` | Ya hay una ejecución activa (solo corre 1 a la vez); espera a que termine. |
| `503 El sistema está ocupado` | Otra petición estaba encolando en ese instante; reintenta en un segundo. |
| `413 Archivo hasta 10 MiB` | Parte el archivo en trozos menores. |
| `502 API apagada` | La consola de `start.py` se cerró; vuelve a ejecutarlo. |
