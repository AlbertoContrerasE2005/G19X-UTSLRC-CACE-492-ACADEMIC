"""Acceso a MySQL: consultas y operaciones de dominio."""

import json
import time
import uuid

from backend import db as mydb
from backend.settings import COLUMNS, now

# ---------------------------------------------------------------- storage


class Store:
    """Acceso MySQL. Cada método abre y cierra su conexión."""

    def one(self, sql, params=()):
        conn = mydb.connect()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return cur.fetchone()
        finally:
            conn.close()

    def all(self, sql, params=()):
        conn = mydb.connect()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return list(cur.fetchall())
        finally:
            conn.close()

    def run(self, sql, params=()):
        """INSERT/UPDATE/DELETE. Devuelve (id_insertado, filas_afectadas)."""
        conn = mydb.connect()
        try:
            with conn.cursor() as cur:
                n = cur.execute(sql, params)
                return cur.lastrowid, n
        finally:
            conn.close()

    # -- helpers de dominio -------------------------------------------

    def audit(self, user_id, action, entity=None):
        self.run(
            "INSERT INTO audit (created_at, user_id, action, entity_id)"
            " VALUES (%s, %s, %s, %s)",
            (now(), user_id, action, entity),
        )

    def activity(
        self,
        user_id,
        username,
        action,
        entity_type="",
        entity_id="",
        project_id=None,
        detail="",
        result="",
    ):
        """Historial visible de actividad (quien, qué, dónde, cuándo)."""
        self.run(
            "INSERT INTO activity_logs (created_at, user_id, username, action,"
            " entity_type, entity_id, project_id, detail, result)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                now(),
                user_id,
                username or "",
                action,
                entity_type,
                str(entity_id or ""),
                project_id,
                detail or "",
                result or "",
            ),
        )

    def log(self, run_id, stage, message):
        self.run(
            "INSERT INTO run_logs (run_id, created_at, stage, message)"
            " VALUES (%s, %s, %s, %s)",
            (run_id, now(), stage, message),
        )
        self.run("UPDATE runs SET stage = %s WHERE id = %s", (stage, run_id))

    def alert(
        self,
        level,
        title,
        message,
        entity_type="",
        entity_id="",
        project_id=None,
        user_id=None,
    ):
        """Crea una alerta visible en Monitoreo/Alertas."""
        new_id, _ = self.run(
            "INSERT INTO alerts (project_id, user_id, level, title, message,"
            " entity_type, entity_id, `read`, created_at)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, 0, %s)",
            (
                project_id,
                user_id,
                level,
                title[:200],
                message[:1000],
                entity_type,
                entity_id,
                now(),
            ),
        )
        return new_id

    def queue(
        self, dataset_id, user_id, kind="manual", parent=None, pipeline="p_ventas"
    ):
        """Encola una ejecución. Solo 1 activa global (compatibilidad)."""
        active = self.one(
            "SELECT id FROM runs WHERE status IN ('queued', 'running') LIMIT 1"
        )
        if active:
            raise ValueError("Ya hay una ejecución en curso. Espera.")
        if not self.one("SELECT id FROM pipelines WHERE id = %s", (pipeline,)):
            raise ValueError("Pipeline no encontrado.")
        run_id = uuid.uuid4().hex
        self.run(
            "INSERT INTO runs (id, dataset_id, pipeline_id, trigger_kind,"
            " status, created_at, created_by, parent_id)"
            " VALUES (%s, %s, %s, %s, 'queued', %s, %s, %s)",
            (run_id, dataset_id, pipeline, kind, now(), user_id, parent),
        )
        self.audit(user_id, "run_queued", run_id)
        return run_id

    def review(self, run_id, lines, user_id, username, motivo, action):
        """Aprueba (carga) o rechaza anomalías pendientes."""
        if action not in ("approved", "rejected"):
            raise ValueError("Acción inválida.")
        if not isinstance(lines, list) or not 1 <= len(lines) <= 500:
            raise ValueError("Selecciona de 1 a 500 filas.")
        try:
            ids = sorted({int(x) for x in lines})
        except (ValueError, TypeError):
            raise ValueError("Filas inválidas.")
        motivo = str(motivo or "").strip()[:500]
        if len(motivo) < 3:
            raise ValueError("Motivo de al menos 3 caracteres.")

        # Todo en una transaccion: si algo falla, no queda ni la carga ni
        # los contadores a medias (una caida a mitad no descuadra el run).
        with mydb.transaction() as cur:
            cur.execute(
                "SELECT r.*, d.columns_json FROM runs r"
                " JOIN datasets d ON d.id = r.dataset_id"
                " WHERE r.id = %s AND r.status = 'completed'",
                (run_id,),
            )
            run = cur.fetchone()
            if not run:
                raise ValueError("Solo runs completados se revisan.")
            columns = json.loads(run["columns_json"] or "[]") or COLUMNS
            is_sales = columns == COLUMNS

            marks = ",".join(["%s"] * len(ids))
            cur.execute(
                f"SELECT line, data_json FROM run_rows"
                f" WHERE run_id = %s AND line IN ({marks})"
                f" AND status = 'anomaly'",
                (run_id, *ids),
            )
            pending = cur.fetchall()
            if not pending:
                raise ValueError("Sin anomalías pendientes en esas filas.")

            loaded = existing = rejected = 0
            for row in pending:
                d = json.loads(row["data_json"])
                if action == "approved":
                    if is_sales:
                        done = cur.execute(
                            "INSERT IGNORE INTO sales"
                            " (id, date, product, quantity,"
                            " unit_price, total, source_run)"
                            " VALUES (%s, %s, %s, %s, %s, %s, %s)",
                            (
                                d["id"],
                                d["fecha"],
                                d["producto"],
                                int(d["cantidad"]),
                                d["precio_unitario"],
                                d.get("total", "0.00"),
                                run_id,
                            ),
                        )
                    else:
                        key = str(d.get(columns[0], ""))[:256]
                        done = cur.execute(
                            "INSERT IGNORE INTO records"
                            " (pipeline_id, run_id, `key`, data_json, created_at)"
                            " VALUES (%s, %s, %s, %s, %s)",
                            (
                                run["pipeline_id"],
                                run_id,
                                key,
                                json.dumps(d, ensure_ascii=False),
                                now(),
                            ),
                        )
                    if done:
                        status, reason, loaded = (
                            "loaded",
                            f"Aprobado por {username}: {motivo}",
                            loaded + 1,
                        )
                    else:
                        status, reason, existing = (
                            "existing",
                            f"Aprobado pero ya existía ({username}): {motivo}",
                            existing + 1,
                        )
                else:
                    status, reason, rejected = (
                        "rejected",
                        f"Rechazado por {username}: {motivo}",
                        rejected + 1,
                    )
                cur.execute(
                    "UPDATE run_rows SET status = %s, reason = %s"
                    " WHERE run_id = %s AND line = %s",
                    (status, reason, run_id, row["line"]),
                )
                cur.execute(
                    "INSERT INTO approvals"
                    " (run_id, line, action, motivo, user_id, created_at)"
                    " VALUES (%s, %s, %s, %s, %s, %s)",
                    (run_id, row["line"], action, motivo, user_id, now()),
                )

            n = len(pending)
            if action == "approved":
                cur.execute(
                    "UPDATE runs SET anomalies = anomalies - %s,"
                    " loaded = loaded + %s, existing = existing + %s,"
                    " approved = approved + %s WHERE id = %s",
                    (n, loaded, existing, n, run_id),
                )
            else:
                cur.execute(
                    "UPDATE runs SET anomalies = anomalies - %s,"
                    " rejected = rejected + %s WHERE id = %s",
                    (n, n, run_id),
                )
            cur.execute(
                "INSERT INTO run_logs (run_id, created_at, stage, message)"
                " VALUES (%s, %s, 'approval', %s)",
                (run_id, now(), f"{n} {action} por {username}: {motivo}"),
            )
            cur.execute(
                "INSERT INTO audit (created_at, user_id, action, entity_id)"
                " VALUES (%s, %s, %s, %s)",
                (now(), user_id, f"anomaly_{action}", run_id),
            )
        return {
            "reviewed": n,
            "loaded": loaded,
            "existing": existing,
            "rejected": rejected,
        }
