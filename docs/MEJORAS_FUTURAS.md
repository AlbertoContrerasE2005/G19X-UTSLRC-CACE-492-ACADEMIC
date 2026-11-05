# Mejoras futuras (para otro día)

Actualizado el 5 de noviembre de 2026, contra el PRD 1.1.
Esto es lo que queda para la siguiente versión; no es deuda pendiente.

## Robustez

1. ~~Transacciones reales en `review()` y `Engine.process`~~ **Hecho**: `db.transaction()`
   agrupa la aprobación y la carga; con fallo se revierte todo. Cubierto por
   `test_transaccion_revierte_aprobacion_parcial`.
2. ~~Lock de concurrencia a nivel DB~~ **Hecho**: índice único real sobre la
   columna generada `active_flag` (solo una ejecución `queued/running`) más
   `GET_LOCK` en `db.named_lock()` para el encolado. Cubierto por
   `test_indice_unico_impide_dos_ejecuciones_activas` y
   `test_bloqueo_con_nombre_serializa_el_encolado`.
3. Reintento con backoff + deadlock 1213 / lock timeout (hoy 1 reintento solo temporal).
4. Validar `interval_minutes` también en scheduler ante edición manual de DB.
5. Rate-limit en uploads/runs (hoy solo login) para no saturar disco.

## Datos e IA

6. Versionar, calibrar y reentrenar el modelo de ventas (contamination/umbral fijos, sin referencia por run).
7. Normalizar antes del IsolationForest genérico + mínimo de filas configurable.
8. Reglas con tipos fecha/número reales (hoy varias comparan texto).
9. Índice fulltext o tabla pivote para `records` (búsquedas grandes).
10. Evitar duplicar `content` entero + filas (crece rápido con 20k).
11. Conectores a bases de datos o APIs externas: hoy solo entran archivos CSV, XLSX y SQL, así que leer de otro sistema obliga a exportar primero.

## UX

12. `approveAll` avisa que solo aprueba visibles (100) o aprueba por filtro real.
13. Refresh diferencial o SSE (polling 2.5 s pierde foco/scroll).
14. Subida multipart/chunks con progreso real (hoy JSON+base64 +33 %).
15. Accesibilidad: foco visible, labels, `aria-current`, contraste muted.

## Seguridad (postura local actual)

16. Cookie `Secure` + TLS al exponer (ok en localhost).
17. Rate-limit por usuario y en más endpoints.
18. Auditoría visible de logins fallidos y aprobaciones con IP/hora.
19. `object-src 'none'` y reducir `unsafe-inline`.

## Operación

20. Dockerfile + compose + proxy inverso y `docs/DESPLIEGUE.md`.
21. Backup/restore en caliente + retención.
22. Logs a archivo con rotación.
23. Healthcheck con latencia DB y umbrales de cola.
24. Varias ejecuciones en paralelo o una cola distribuida: hoy hay una sola activa global, a propósito, para que los destinos y los contadores no se pisen.
