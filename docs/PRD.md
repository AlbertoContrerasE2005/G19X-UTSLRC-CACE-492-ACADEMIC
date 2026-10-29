# PRD — DataOps Final

Versión 1.1 · 29 de octubre de 2026.
Stack: HTML + CSS + PHP + Python (FastAPI) + MySQL/MariaDB + SQL.
Todo local: API `127.0.0.1:8010`, web `127.0.0.1:8080`, MySQL `127.0.0.1:3306` (configurable).

## 1. Problema que resuelve y para quién

En una PyME, o en un área que apenas empieza a ordenar sus datos, la
información llega en hojas de cálculo sueltas por correo o mensajería.
Nadie valida lo que entra: filas incompletas, precios escritos como texto,
fechas imposibles y valores atípicos terminan en el reporte del mes. Tampoco
queda rastro de quién cargó qué, no hay forma de repetir una carga sin
duplicar registros y nadie la deja programada.

Quien sufre hoy ese problema:

| Quién | Qué le pasa sin la plataforma |
|---|---|
| Analista de datos | Limpia a mano cada archivo y vuelve a revisar lo mismo cada mes. |
| Responsable del área | Decide con cifras que nadie validó y no sabe si el dato es confiable. |
| Quien carga los datos | Sube archivos sin control: si algo sale mal no hay historial ni forma de deshacer. |
| Auditoría o dirección | No puede reconstruir qué se cargó, cuándo y con qué criterio. |

La plataforma cubre ese tramo completo: recibe el archivo, lo valida, señala
lo anómalo, pide una decisión humana con motivo, carga solo lo aprobado y
deja todo registrado. Corre en la máquina del usuario, sin servicios
externos.

## 2. Objetivo

Que cualquier persona del equipo pueda tomar un archivo de datos, saber si es
confiable antes de usarlo y dejar constancia de lo que se cargó, sin escribir
código y sin depender de servicios externos.

Metas concretas:

- Un archivo nuevo queda validado y cargado en segundos.
- Ninguna fila dudosa llega al destino sin una decisión humana con motivo.
- Repetir una carga no duplica registros y todo queda registrado.
- El sistema se entiende leyendo un archivo por capa, con comentarios en español.

## 3. Usuarios y roles

| Rol (código) | Nombre en pantalla | Puede |
|---|---|---|
| admin    | Administrador | Todo: usuarios, pipelines, cargas, ejecuciones, aprobaciones |
| operator | Data Engineer | Cargar, ejecutar, programar, aprobar/rechazar |
| viewer   | Usuario       | Solo ver y descargar |

Primera cuenta = admin (setup). Sesión 8 h en cookie HttpOnly.
El código y la API usan `admin`, `operator` y `viewer`; en la interfaz esos
mismos roles se muestran como Administrador, Data Engineer y Usuario (en el
selector de alta de usuario, «Usuario (consulta)»).

## 4. Funciones (100 %)

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
   `/api/health`, `/api/ready`, serie diaria por pipeline.
9. **Destino**: ventas → tabla `sales`; dinámico → tabla `records`
   (clave única por pipeline). Repetir no duplica.
10. **Plataforma** (módulos `backend/platform_*.py`, 37 endpoints):
    proyectos con miembros, perfilado por columna (tipo, nulos,
    únicos, min/max/promedio), score de calidad, reglas
    personalizables (`gte`, `not_empty`, `unique`…), tabla de
    anomalías con severidad y resolución, alertas con lectura,
    reportes JSON/CSV/PDF, IA conversacional local
    (`/ai/ask`, resumen, recomendaciones, historial; OpenAI/Azure
    opcionales por `.env`), actividad auditable, dashboard con
    gráficas y monitoreo de pipelines.

## 5. Límites

10 MiB por archivo, 20000 filas, 1-30 columnas únicas,
celdas ≤2000 caracteres, revisión 1-500 filas por acción,
1 ejecución activa global, 1 reintento solo ante fallo temporal.

## 6. Fuera de alcance

Queda fuera de esta entrega todo lo que implique sacar el sistema de una
sola máquina o atender varios usuarios trabajando a la vez. El detalle y el
orden previsto están en `docs/MEJORAS_FUTURAS.md`; en resumen:

- Despliegue en red o internet: Docker, compose, TLS y proxy inverso.
- Conectores a bases de datos o APIs externas (solo CSV, XLSX y SQL).
- Varias ejecuciones en paralelo o una cola distribuida.
- Versionado y reentrenamiento del modelo de anomalías.
- Subida multipart con progreso y refresco en vivo de la interfaz.

No es deuda oculta: es alcance decidido. El sistema es local por diseño
(una máquina, una ejecución activa a la vez).

## 7. Seguridad

Scrypt, sesiones sha256, 401/403 por rol, solo localhost,
`X-Requested-With`, allowlist de origen, CSP, `no-store` en API,
anti-fórmulas en CSV exportado, rate-limit de login.

## 8. Criterios de aceptación

- Setup → login → subir CSV/XLSX/SQL → ejecutar → completar.
- Ventas ejemplo 70 filas: 64 cargadas, 4 inválidas, 2 alertas.
- Aprobar 1 alerta suma a destino; rechazar la otra la marca.
- Repetir mismo archivo: 0 nuevas (idempotente).
- `unittest` en verde + `node --check` + `php -l`.
