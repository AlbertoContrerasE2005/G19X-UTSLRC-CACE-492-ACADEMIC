# MVP — DataOps Final

Documento de la primera entrega. Define qué entra, qué queda fuera y cómo
se demuestra. Complementa a `docs/PRD.md` (requisitos) y a
`docs/MEJORAS_FUTURAS.md` (backlog).

> Nota: el proyecto original se llamó `DataOps_MVP`. Al reconstruirlo de cero
> se renombró a **DataOps Final**; este documento describe la primera entrega
> de esa versión.

## 1. Qué entra en la primera entrega

**Autenticación y roles**
- Setup de la primera cuenta (admin), login, logout.
- CRUD de usuarios (solo admin) y cambio de propia clave.
- Tres roles: `admin`, `operator`, `viewer`, con 403 en el servidor.
- Sesión de 8 horas en cookie HttpOnly; claves con scrypt.

**Archivos (datasets)**
- Subida de CSV, Excel `.xlsx` y SQL con `INSERT ... VALUES`.
- Límites: 10 MiB, 20,000 filas, 1-30 columnas, celdas ≤2000 caracteres.
- Detección automática de columnas (sin plantilla fija).
- Vista previa (8 filas), perfil por columna, score de calidad, borrado en cascada.

**Pipelines**
- Crear, ver, editar, eliminar.
- Pasos configurables (1-12), archivo asignado y frecuencia:
  manual, 15 min, 1 h, 24 h.
- Historial por pipeline, contador de ejecuciones y fecha de la última.

**Ejecuciones (runs)**
- Ejecución manual o programada (worker cada 10 s, 1 activa global).
- Detalle con métricas, log por etapa, filas (todas / pendientes / incidencias / rechazos).
- Exportación CSV en 5 tipos, repetición idempotente.
- Recuperación de ejecuciones interrumpidas al reiniciar.

**Calidad**
- Reglas de ventas (5 columnas exactas) con `total` calculado.
- Validación genérica (primera columna como clave única).
- Reglas personalizables por columna (`gte`, `not_empty`, `unique`, …) con evaluación y tabla de resultados.

**Inteligencia artificial**
- Ventas: `IsolationForest(120)` con referencia de 480 filas.
- Genérica: `IsolationForest(100)` sobre columnas numéricas (≥3 filas).
- Score < 0 = alerta pendiente. **Nunca se carga sola.**

**Aprobación humana**
- Aprobar (carga a destino) o rechazar con motivo (≥3 caracteres).
- 1-500 filas por acción, auditoría completa.

**Plataforma**
- Proyectos con miembros y resumen.
- Anomalías con severidad y resolución.
- Alertas automáticas con lectura.
- Reportes en PDF, CSV y JSON.
- IA conversacional local (`/ai/ask`, resumen, recomendaciones, historial).
- Historial de actividad auditable.
- Dashboard con gráficas y monitoreo de pipelines.
- Configuración del sistema.

**Operación y verificación**
- `start.py` crea la base y las tablas desde `db/schema.sql`.
- `/health`, `/ready`, `/metrics/summary`, `/metrics/runs`.
- 20 tablas, 67 rutas de API, 38 pruebas automáticas en verde.

## 2. Qué queda fuera (backlog v1.1)

Detallado en `docs/MEJORAS_FUTURAS.md`. Resumen por área:

**Robustez:** transacciones reales en aprobación y carga; lock de concurrencia a nivel DB; reintento con backoff; validación de frecuencia en el scheduler; rate-limit en uploads y runs.

**Datos e IA:** versionado y calibración del modelo; normalización antes del IsolationForest genérico; reglas con tipos fecha/número reales; índice de búsqueda para `records`; evitar duplicar el contenido del archivo.

**UX:** aviso de que `approveAll` solo cubre lo visible; refresh diferencial o SSE; subida multipart con progreso; accesibilidad.

**Seguridad:** cookie `Secure` y TLS al exponer; rate-limit por usuario; auditoría visible de logins fallidos; endurecer CSP.

**Operación:** Docker y compose; backup en caliente; logs a archivo; healthcheck con umbrales.

> Los puntos de despliegue, TLS y Docker no aplican a esta entrega porque el
> proyecto es **solo local** por decisión de diseño.

## 3. Flujo de demostración

Resultado esperado: **64 cargadas, 4 inválidas, 2 alertas**.

| Paso | Acción | Resultado |
|---|---|---|
| 1 | Entrar a http://127.0.0.1:8080 | Login |
| 2 | Archivos → Cargar archivo → `examples/ventas_ejemplo.csv` | 70 filas guardadas |
| 3 | Ejecutar el pipeline | `completed` |
| 4 | Abrir el detalle | **64 cargadas · 4 inválidas · 2 alertas** |
| 5 | Filtrar "Solo pendientes" | 2 anomalías visibles |
| 6 | Aprobar 1 con motivo | suma 1 a destino |
| 7 | Rechazar la otra con motivo | queda registrada, no suma |
| 8 | Repetir la ejecución | **0 nuevas**, 64 ya existentes |

Comprobación:

```powershell
.\.venv\Scripts\python -m unittest discover -s tests -v
node --check web/app.js
php -l php/router.php
```

## 4. Criterios de aceptación

Los de `docs/PRD.md`, verificados en la entrega:

- Setup → login → subir CSV/XLSX/SQL → ejecutar → completar.
- Ventas ejemplo 70 filas: 64 cargadas, 4 inválidas, 2 alertas.
- Aprobar 1 alerta suma a destino; rechazar la otra la marca.
- Repetir el mismo archivo: 0 nuevas (idempotente).
- `unittest` en verde + `node --check` + `php -l`.