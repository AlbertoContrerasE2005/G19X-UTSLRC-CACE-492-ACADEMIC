# Decisiones de diseño

Tres decisiones que no se ven en la interfaz pero sostienen el sistema:
la ejecución única, la diferencia entre 409 y 503, y el borrado de archivos.
Cada sección sigue el mismo orden: el problema, qué se hizo, qué pasaría sin
eso y qué prueba lo cubre.

## 1. Solo una ejecución activa

**El problema.** El worker busca trabajo cada 10 segundos y la API puede
encolar otra ejecución al mismo tiempo. Si dos corren a la vez, ambas
escriben en las mismas tablas de destino (`sales` o `records`), se pisan los
contadores de `runs` y no hay forma de saber cuál mandó. Además son dos
procesos distintos, así que un `if` en Python no alcanza: entre comprobar y
escribir cabe otra petición.

**Qué se hizo.** Dos barreras que se complementan.

La primera está en la base (`db/schema.sql`):

```sql
active_flag TINYINT GENERATED ALWAYS AS
    (IF(status IN ('queued','running'), 1, NULL)) VIRTUAL,
UNIQUE KEY uq_one_active (active_flag)
```

`active_flag` no se guarda: se calcula. Vale `1` mientras el run está en cola
o corriendo, y `NULL` en cuanto termina o falla. En un índice único los
`NULL` no compiten entre sí (MySQL admite todos los que quieras), pero el
valor `1` solo cabe una vez. Por eso conviven miles de ejecuciones
terminadas y **solo una puede estar activa**. Si alguien lo intenta por otra
vía, la base lanza `IntegrityError` y la fila no entra.

La segunda es `GET_LOCK` (`backend/db.py`), que envuelve el "comprobar y
encolar" de `Store.queue`. El índice evita el estado inválido, pero si dos
procesos compiten, el que pierde recibiría un error crudo de MySQL, es decir
un 500. Con el bloqueo, el segundo espera su turno; si no lo consigue en
10 segundos, se le pide reintentar. El nombre del bloqueo incluye la base
(`dataops_queue_dataops`) porque los locks de MySQL son del servidor, no de
la base: sin eso, las pruebas sobre `dataops_test` bloquearían al servidor
real.

**Sin esto.** Las claves únicas evitan filas duplicadas, pero el
`source_run` de cada fila queda apuntando a la ejecución que llegó primero,
los contadores de ambas cuentan como propias filas que no cargaron y
aparecen errores 500 intermitentes que nadie sabe reproducir.

**Qué lo prueba.**
- `tests/test_extended.py::test_indice_unico_impide_dos_ejecuciones_activas`:
  inserta un segundo run activo saltándose la aplicación y la base lo
  rechaza.
- `tests/test_extended.py::test_bloqueo_con_nombre_serializa_el_encolado`:
  con el bloqueo tomado, una segunda conexión no lo obtiene.
- `tests/test_extended.py::test_bloqueo_es_por_base_de_datos`: dos bases
  distintas no se estorban.

## 2. 409 o 503: esperar o reintentar

**El problema.** Al pulsar "Ejecutar", el sistema puede negarse por dos
motivos muy distintos, y el usuario necesita saber si insistir o esperar.

**Qué se hizo.** `Store.queue` lanza dos errores diferentes y
`backend/api_runs.py` los traduce a dos códigos:

| Situación | Error | Código | Mensaje | Qué debe hacer el usuario |
|---|---|---|---|---|
| Ya hay un run en `queued`/`running` | `ValueError` (`store.py:138`) | **409** | "Ya hay una ejecucion en curso. Espera." | Esperar a que termine la que corre |
| No se pudo tomar el bloqueo | `BusyError` (`store.py:130`) | **503** | "El sistema esta ocupado en este momento. Intenta de nuevo en un segundo." | Reintentar en un segundo |

La diferencia es el estado. El 409 describe un conflicto **real y duradero**
(hay trabajo en curso); el 503, un choque **momentáneo** (otra petición
estaba encolando justo en ese instante). Por eso el 409 es "espera" y el 503
es "reintenta": reintentar contra un 409 no sirve de nada, contra un 503 sí.

**Sin esto.** Un único 409 para todo, o peor, un 500. El usuario
reintentaría en vano o creería que el sistema está roto cuando solo estaba
ocupado.

**Qué lo prueba.**
- `tests/test_extended.py::test_bloqueo_no_conseguido_responde_reintentar`:
  simula que el bloqueo está tomado, espera 503 y comprueba que no quedó
  nada encolado.
- `tests/test_extended.py::test_concurrencia_409` y
  `tests/test_basic.py::test_solo_una_activa`: con un run activo, la
  segunda petición recibe 409.

## 3. Borrar un archivo desvincula su pipeline

**El problema.** `pipelines.dataset_id` apunta a `datasets.id` y la llave
foránea no lleva `ON DELETE`, así que MySQL la trata como `RESTRICT`: no
deja borrar un dataset mientras un pipeline lo use. El borrado, además,
arrastra runs, filas, logs, aprobaciones, anomalías y lo ya cargado en
`sales` o `records`. Hecho paso por paso, un fallo a mitad dejaba media
limpieza: runs borrados, dataset todavía ahí y un 500 en la cara.

**Qué se hizo.** `dataset_delete` (`backend/api_datasets.py`) hace tres
cosas:

1. Responde 409 si el archivo tiene ejecuciones activas.
2. Dentro de `mydb.transaction()`, primero desvincula los pipelines
   (`dataset_id = NULL`, `enabled = 0`, `next_run = NULL`) y después borra
   los hijos y el dataset.
3. Confirma todo junto o no confirma nada: si una sentencia falla, el
   `rollback` deja la base como estaba.

El pipeline no se borra: sigue existiendo, sin archivo y desactivado, para
que el usuario lo apunte a otro dataset sin perder su configuración.

**Sin esto.** Error 1451 de MySQL a mitad del borrado, respuesta 500 y un
archivo imposible de eliminar mientras exista un pipeline que lo use.

**Qué lo prueba.**
- `tests/test_full.py::test_borrar_dataset_con_pipeline`: crea dataset,
  pipeline y run; borra el archivo y verifica 200, 404 en dataset y run, y
  el pipeline con `dataset_id` nulo y desactivado.
- `tests/test_all.py::test_05_dataset_borrar_cascada`: el borrado arrastra
  las ejecuciones asociadas.
