# Mejoras futuras (para otro día)

Guardado el 5 de octubre de 2026. Proyecto verificado al 100 % del PRD v1.0;
esto es backlog v1.1, no deuda pendiente.

## Robustez

1. Transacciones reales en `review()` y `Engine.process` (hoy N commits sueltos).
2. Lock de concurrencia a nivel DB (`GET_LOCK` o `UPDATE ... WHERE status='queued'`).
3. Reintento con backoff + deadlock 1213 / lock timeout (hoy 1 reintento solo temporal).
4. Validar `interval_minutes` también en scheduler ante edición manual de DB.
5. Rate-limit en uploads/runs (hoy solo login) para no saturar disco.

## Datos e IA

6. Versionar/calibrar modelo ventas (contamination/​umbral fijos, sin referencia por run).
7. Normalizar antes del IsolationForest genérico + mínimo de filas configurable.
8. Reglas con tipos fecha/número reales (hoy varias comparan texto).
9. Índice fulltext o tabla pivote para `records` (búsquedas grandes).
10. Evitar duplicar `content` entero + filas (crece rápido con 20k).

## UX

11. `approveAll` avisa que solo aprueba visibles (100) o aprueba por filtro real.
12. Refresh diferencial o SSE (polling 2.5 s pierde foco/scroll).
13. Subida multipart/chunks con progreso real (hoy JSON+base64 +33 %).
14. Accesibilidad: foco visible, labels, `aria-current`, contraste muted.

## Seguridad (postura local actual)

15. Cookie `Secure` + TLS al exponer (ok en localhost).
16. Rate-limit por usuario y en más endpoints.
17. Auditoría visible de logins fallidos y aprobaciones con IP/hora.
18. `object-src 'none'` y reducir `unsafe-inline`.

## Operación

19. Dockerfile + compose + `docs/DESPLIEGUE.md`.
20. Backup/restore en caliente + retención.
21. Logs a archivo con rotación.
22. Healthcheck con latencia DB y umbrales de cola.
