# Instalación en carpeta limpia — 5-nov-2026 · commit 41cbf3f

Prueba de reproducibilidad: clonar el repositorio en una carpeta nueva y seguir
`README.md` (secciones 1 a 6) sin reutilizar nada del equipo de desarrollo
(no se copiaron `.env` ni `.venv`). Al final se ejecutó el flujo de
`docs/MVP.md` y la suite de 49 pruebas.

- **Repositorio:** `https://github.com/AlbertoContrerasE2005/G19X-UTSLRC-CACE-492-ACADEMIC.git`
- **Commit probado:** `41cbf3f` (rama `main`)
- **Carpeta de la corrida 1:** `C:\prueba-limpia`
- **Carpeta de la corrida 2:** `C:\prueba-limpia2`
- **Base de datos de prueba:** MariaDB 10.4.32 nueva, `127.0.0.1:3306`,
  datadir `C:\prueba-limpia-db`, usuario `root` sin contraseña.
  (La instalación del equipo de desarrollo usa el puerto **3307**; no se tocó.)

## Entorno

| Componente | Versión |
|---|---|
| Windows | 10/11 (PowerShell 5.1) |
| Python | 3.12.10 (64 bits, `py -3.12`) |
| PHP | 8.2.12 (`C:\xampp\php\php.exe`) |
| Node.js | v24.15.0 |
| MariaDB | 10.4.32 |

## Resumen

| Paso | Qué hice | Resultado | Tiempo |
|---|---|---|---|
| 1 | `git clone` en `C:\prueba-limpia` | Bien; sin `.env` ni `.venv` | 0.9 s |
| 2 | MariaDB nueva en 3306 con datadir propio | `10.4.32`, root sin clave | 1.6 s (init) |
| 3 | `py -3.12 -m venv .venv` | Python 3.12.10 | 6.4 s |
| 4 | `pip install -r requirements.txt` | 8 paquetes base | 38.8 s |
| 5 | `Copy-Item .env.example .env` + `python start.py --no-browser` | 20 tablas, health OK, web 200 | 5.1 s |
| 6 | `python -m backend.seed` | 4 cuentas, 3 datasets, 2 ejecuciones | 4.2 s |
| 7 | Flujo de `docs/MVP.md` en navegador real | 64 / 4 / 2; aprobar + rechazar; repetición 0 nuevas | ~5 min |
| 8 | `python -m unittest discover -s tests -v` | **47 OK, 2 fallos** (PDF 500) | 78.5 s |
| 9 | Diagnóstico y `pip install reportlab` | PDF OK; 2 pruebas enfocadas en verde | 6.6 s |
| 10 | Suite completa otra vez | **49 pruebas OK** | 77.7 s |
| 11 | `node --check web/app.js` / `php -l php/router.php` | Sin errores | <1 s |
| 12 | Corrida 2 desde cero con las correcciones aplicadas | **49 pruebas OK** y flujo 64/4/2 → 0/64 | ver abajo |

## Corrida 1 — paso a paso

### 1. Clon

```powershell
git clone https://github.com/AlbertoContrerasE2005/G19X-UTSLRC-CACE-492-ACADEMIC.git C:\prueba-limpia
```

Resultado: commit `41cbf3f`, sin `.env` ni `.venv` (comprobado con `Test-Path`).
Tiempo: 0.9 s.

### 2. Base de datos limpia

Se creó una instancia **nueva** para no depender de la base del equipo de
desarrollo (puerto 3306, valores por omisión de `.env.example`):

```powershell
C:\xampp\mysql\bin\mysql_install_db.exe --datadir="C:\prueba-limpia-db" --port=3306 --password=
C:\xampp\mysql\bin\mysqld.exe --defaults-file="C:\prueba-limpia-db\my.ini" --console
```

Resultado: `MariaDB 10.4.32`, `@@port = 3306`, root sin contraseña.
Tiempo: 1.6 s la inicialización; el servidor arrancó en segundos.

### 3. Entorno virtual y dependencias (README §2)

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
```

Resultado: Python 3.12.10; `pip` instaló fastapi, uvicorn, scikit-learn,
numpy, openpyxl, pymysql, httpx y python-dotenv.
Tiempos: 6.4 s el venv; 38.8 s el `pip install`.

### 4. Configuración y arranque (README §3)

```powershell
Copy-Item .env.example .env
.\.venv\Scripts\python start.py --no-browser
```

El `.env` se copió **sin editar** (3306, root, sin contraseña).
Resultado: `/api/health` respondió `{"status":"ok","version":"1.0.0"}`,
la web devolvió 200 y se crearon las **20 tablas** de `dataops`.
Tiempo hasta health: 5.1 s.

> **Incidencia (ambiente, no del README):** el primer intento terminó con
> `Puerto 8010 ocupado`. Había otra instancia del proyecto (de una corrida
> anterior) escuchando en 8010/8080. Se localizó con
> `Get-NetTCPConnection -State Listen -LocalPort 8010,8080` y se detuvo su
> árbol de procesos con `taskkill /PID <pid> /T /F`. Tras eso el arranque
> fue limpio. Esto motivó la nota de puertos añadida al README.

### 5. Cuentas y datos de prueba (README §4)

```powershell
$env:DEMO_PASSWORD  = "Demo2026!!segura"
$env:ADMIN_PASSWORD = "Admin2026!!segura"
.\.venv\Scripts\python -m backend.seed
```

Resultado: usuarios `demo`, `admin`, `ingeniero`, `consulta`; datasets
`ventas_ejemplo.csv`, `pasteles.csv`, `productos.sql`; pipeline DEMO; regla
`cantidad >= 1`; dos ejecuciones (`total=70 cargados=64 inválidos=4
anomalías=2` y `total=5 cargados=3`).
Tiempo: 4.2 s.

### 6. Flujo de demostración (docs/MVP.md)

Hecho en navegador real (http://127.0.0.1:8080) con la cuenta `demo`:

1. **Primera ejecución del archivo:** el detalle mostró
   **70 total · 0 cargadas · 64 existentes · 4 inválidas · 2 alertas**.
   Ver `01-seed-0-cargadas-64-existentes.png`.
2. **Causa:** el sembrador ya había cargado las 64 filas de ventas en el
   destino (`sales`). No es un fallo de la app, pero contradice el
   “64 cargadas” que pide la demo si se ejecuta justo después del seed.
3. Para reproducir el escenario documentado se vació el destino:
   `TRUNCATE TABLE dataops.sales; TRUNCATE TABLE dataops.records;`
4. **Repetición desde destino vacío:** **64 cargadas · 4 inválidas ·
   2 alertas · 0 existentes**. Ver `02-demo-limpia-64-cargadas.png`.
5. **Aprobar una alerta:** línea 66 (`VEN-0065`), motivo `Pico validado`.
   Resultado: `approved=1`, `pending=1`; `sales` pasó a 65.
6. **Rechazar la otra:** línea 67 (`VEN-0066`), motivo
   `Precio fuera de rango`. Resultado: `rejected=1`, `pending=0`.
   Ver `03-aprobacion-y-rechazo.png`.
7. **Repetir la ejecución:** **0 cargadas · 64 existentes · 4 inválidas ·
   2 alertas**. Ver `04-repeticion-0-nuevas-64-existentes.png`.

Comprobación directa en la base:

```text
sales = 65   approved = 1   rejected = 1
```

Tiempo del flujo completo: ~5 minutos (incluye capturas y verificación).

### 7. Pruebas (README §6)

```powershell
.\.venv\Scripts\python -m unittest discover -s tests -v
node --check web/app.js
php -l php/router.php
```

Primer resultado: **47 OK y 2 fallos** (`test_14_reportes` y
`test_reportes_ciclo_completo`): la descarga de reportes **PDF** devolvía
**500**. Tiempo: 78.5 s.

**Causa raíz:** `backend/reports.py` genera el PDF con `reportlab`, pero
`requirements.txt` no lo incluía, así que en una instalación limpia el
paquete no existía.

```powershell
.\.venv\Scripts\python -m pip install reportlab
```

Se instaló `reportlab 5.1.0` (con `pillow 13.0.0` y
`charset-normalizer 3.5.2`) en 6.6 s. Las dos pruebas enfocadas pasaron.
La suite completa volvió a correr: **49 pruebas, OK** en 77.7 s.

`node --check web/app.js`: OK. `php -l php/router.php`: sin errores.

## Hallazgos y correcciones aplicadas

| # | Hallazgo | Corrección |
|---|---|---|
| 1 | Faltaba `reportlab` en `requirements.txt`; 2 pruebas de PDF fallaban con 500 en instalación limpia. | Se agregó `reportlab==5.1.0`. |
| 2 | Node.js se usa en §6 pero no estaba en Requisitos. | Se añadió a `README.md` §1, con nota de que la comprobación es opcional. |
| 3 | El README usaba etiquetas antiguas de la UI (`Archivos → Subir`, `Ejecuciones → Ver`, `Actividad`). | Se actualizó a `Datasets → Cargar archivo`, `Detalle de la ejecución → Solo pendientes` e `Historial`. |
| 4 | `backend.seed` carga 64 filas en `sales`; tras sembrar, la demo muestra 0/64 y no 64/4/2. | Se documentó el efecto y se añadió el `TRUNCATE` de `dataops.sales`/`dataops.records` en `README.md` y `docs/MVP.md`. |
| 5 | `start.py` falla con `Puerto 8010 ocupado` sin decir cómo localizar el proceso. | Se agregó el comando `Get-NetTCPConnection` al README. |
| 6 | La demo no aclaraba que aprobaciones/rechazos son por ejecución (la repetición vuelve a mostrar 2 pendientes). | Se anotó en `docs/MVP.md`. |
| 7 | El README no relacionaba el error 500 de PDF con una dependencia faltante. | Se añadió a la tabla de Problemas comunes y al criterio de aceptación. |

Corregido en el commit a55101e:

- `requirements.txt` — `reportlab==5.1.0`.
- `README.md` — Node.js, puertos, aviso del seed, `TRUNCATE`, etiquetas de UI,
  notas de `reportlab` y filas de solución de problemas.
- `docs/MVP.md` — aviso del seed, `TRUNCATE`, pasos de demo actualizados,
  aprobaciones por ejecución, criterios de aceptación y `reportlab`.

## Corrida 2 — verificación de las correcciones

Para comprobar que las instrucciones corregidas sí funcionan desde cero, se
repitió el proceso en `C:\prueba-limpia2`:

1. Clon nuevo del mismo commit `41cbf3f` (1.4 s).
2. Se aplicaron los tres archivos corregidos (commit `a55101e`):
   `README.md`, `requirements.txt`, `docs/MVP.md`.
3. Se borraron las bases `dataops` y `dataops_test` de la instancia de prueba
   para partir de cero.
4. `py -3.12 -m venv .venv` (7.1 s) y `pip install -r requirements.txt`
   (39.9 s). El `pip` instaló **reportlab 5.1.0** desde `requirements.txt`
   (comprobado con `import reportlab`).
5. `Copy-Item .env.example .env` sin editar y `start.py --no-browser`:
   health en 4.1 s, web 200, 20 tablas.
6. `python -m backend.seed` (4.3 s): 4 usuarios, 3 datasets, 2 ejecuciones,
   64 filas en `sales`.
7. Siguiendo el README corregido: `TRUNCATE` del destino y flujo en el
   navegador con `demo`:
   - subir `examples/ventas_ejemplo.csv` → ejecutar →
     **70 total · 64 cargadas · 4 inválidas · 2 alertas**;
   - aprobar línea 66 con `Pico validado` → `approved=1`, `sales=65`;
   - rechazar línea 67 con `Precio fuera de rango` → `rejected=1`;
   - repetir → **0 cargadas · 64 existentes · 4 inválidas · 2 alertas**.
   Ver `05-segunda-corrida-64-4-2.png` y
   `06-segunda-corrida-repeticion-0-64.png`.
8. `python -m unittest discover -s tests -v`: **49 pruebas, OK**
   (`Ran 49 tests in 77.214s`) en 79.6 s, ya sin instalar nada a mano.
9. `node --check web/app.js`: OK. `php -l php/router.php`: sin errores.
10. Base final: `sales=65`, `approved=1`, `rejected=1`,
    `dataops_test` con 20 tablas.

Tiempo total de la corrida 2: ~4 minutos de instalación/arranque y
~2 minutos de flujo, más ~80 s de pruebas.

## Capturas

| Archivo | Qué muestra |
|---|---|
| `01-seed-0-cargadas-64-existentes.png` | Tras el seed: 0 cargadas / 64 existentes / 4 inválidas / 2 alertas. |
| `02-demo-limpia-64-cargadas.png` | Destino vacío: 64 cargadas / 4 inválidas / 2 alertas. |
| `03-aprobacion-y-rechazo.png` | Una alerta aprobada y otra rechazada, con motivo. |
| `04-repeticion-0-nuevas-64-existentes.png` | Repetición: 0 nuevas / 64 existentes. |
| `05-segunda-corrida-64-4-2.png` | Corrida 2 con `requirements.txt` corregido: 64/4/2. |
| `06-segunda-corrida-repeticion-0-64.png` | Corrida 2, repetición: 0/64. |

## Conclusión

Con las correcciones, una instalación desde cero siguiendo el README:

- crea las 20 tablas y arranca API y web sin pasos ocultos;
- siembra cuentas y datos tal como se describe;
- reproduce el flujo **64 cargadas / 4 inválidas / 2 alertas**, la aprobación
  y el rechazo con auditoría, y la repetición con **0 nuevas / 64 existentes**;
- pasa las **49 pruebas** y los chequeos de sintaxis de JavaScript y PHP.

Los dos fallos encontrados en la primera corrida (PDF 500 por `reportlab`
ausente y el aviso del seed) quedaron corregidos y verificados en la segunda.

## Verificación final — 8-nov-2026 · commit 56ed3e1 + pruebas de `_db_down`

Después del arreglo de `backend/worker.py` (reintento si la base se cae) y de
agregar las pruebas de `_db_down`:

- `python -m unittest discover -s tests -v`: **51 pruebas, OK**
  (`Ran 51 tests in 79.777s`).
- `node --check web/app.js`: OK · `php -l php/router.php`: sin errores.

La suite se ejecutó sobre MariaDB 10.4.32 en `127.0.0.1:3306`, con las
dependencias de `requirements.txt` (incluye `reportlab`).
