# PRD — DataOps Final (proyecto nuevo)

Versión 1.0 · 5 de octubre de 2026.
Stack: HTML + CSS + PHP + Python (FastAPI) + MySQL/MariaDB + SQL.
Todo local: API `127.0.0.1:8010`, web `127.0.0.1:8080`, MySQL `127.0.0.1:3307`.

## 1. Objetivo

Plataforma simple para automatizar el ciclo de vida de los datos:
cargar archivos, validar calidad, detectar anomalías con IA,
aprobar con criterio humano, programar ejecuciones y monitorear todo.
Código fácil de leer: un archivo por capa, comentarios en español,
paleta oscura cómoda.

## 2. Usuarios y roles

| Rol      | Puede |
|----------|-------|
| admin    | Todo: usuarios, pipelines, cargas, ejecuciones, aprobaciones |
| operator | Cargar, ejecutar, programar, aprobar/rechazar |
| viewer   | Solo ver y descargar |

Primera cuenta = admin (setup). Sesión 8 h en cookie HttpOnly.

## 3. Funciones (100 %)

1. **Auth**: setup inicial, login, logout, crear usuarios (admin).
2. **Datasets**: subir CSV/XLSX/SQL hasta 10 MiB y 20000 filas,
   1-30 columnas, cualquier nombre de columna. Vista previa (8),
   eliminar. Todo se normaliza a CSV interno.
3. **Pipelines**: crear, ver, editar (nombre, descripción, archivo,
   frecuencia manual/15/60/1440 min), eliminar, historial por pipeline.
4. **Runs**: ejecutar manual o programada (worker cada 10 s, 1 activa
   global), ver detalle (métricas, logs, filas all/issues/pending),
   exportar CSV, repetir.
5. **Calidad**: si las columnas son `id,fecha,producto,cantidad,
   precio_unitario` se aplican reglas de ventas + total calculado.
   Si no, validación genérica (primera columna = clave única).
6. **IA**: ventas `IsolationForest(120)` con referencia de 480 filas;
   genérico `IsolationForest(100)` sobre columnas numéricas (≥3 filas).
   Score < 0 = alerta pendiente, nunca se carga sola.
7. **Aprobación**: aprobar (carga a destino) o rechazar con motivo
   (≥3 caracteres), auditoría completa.
8. **Monitoreo**: dashboard (activas, éxito 7 días, p50/p95, filas),
   `/health`, `/ready`, serie diaria por pipeline.
9. **Destino**: ventas → tabla `sales`; dinámico → tabla `records`
   (clave única por pipeline). Repetir no duplica.
10. **Plataforma** (`backend/platform_api.py`, 35 endpoints):
    proyectos con miembros, perfilado por columna (tipo, nulos,
    únicos, min/max/promedio), score de calidad, reglas
    personalizables (`gte`, `not_empty`, `unique`…), tabla de
    anomalías con severidad y resolución, alertas con lectura,
    reportes JSON/CSV/PDF, IA conversacional local
    (`/ai/ask`, resumen, recomendaciones, historial; OpenAI/Azure
    opcionales por `.env`), actividad auditable, dashboard con
    gráficas y monitoreo de pipelines.

## 4. Límites

10 MiB por archivo, 20000 filas, 1-30 columnas únicas,
celdas ≤2000 caracteres, revisión 1-500 filas por acción,
1 ejecución activa global, 1 reintento solo ante fallo temporal.

## 5. Seguridad

Scrypt, sesiones sha256, 401/403 por rol, solo localhost,
`X-Requested-With`, allowlist de origen, CSP, `no-store` en API,
anti-fórmulas en CSV exportado, rate-limit de login.

## 6. Criterios de aceptación

- Setup → login → subir CSV/XLSX/SQL → ejecutar → completar.
- Ventas ejemplo 70 filas: 64 cargadas, 4 inválidas, 2 alertas.
- Aprobar 1 alerta suma a destino; rechazar la otra la marca.
- Repetir mismo archivo: 0 nuevas (idempotente).
- `unittest` en verde + `node --check` + `php -l`.
