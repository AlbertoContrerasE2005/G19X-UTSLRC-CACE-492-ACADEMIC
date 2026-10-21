"""Motor de una ejecucion: valida, detecta anomalias y carga a destino."""

import json
import math
import time

import numpy as np
from sklearn.ensemble import IsolationForest

from backend import db as mydb
from backend.data_io import parse_csv_dynamic, rows_to_csv
from backend.settings import COLUMNS, MODEL_GENERIC, MODEL_SALES, ROOT, now
from backend.validators import validate_generic, validate_sales

# ---------------------------------------------------------------- motor


class Engine:
    """Procesa un run: valida → IA → carga. Se entrena al iniciar."""

    def __init__(self, store):
        self.store = store
        ref = (ROOT / "examples" / "referencia_ventas.csv").read_text(encoding="utf-8")
        _, rows = parse_csv_dynamic(ref)
        feats = [r["features"] for r in validate_sales(rows) if r["status"] == "valid"]
        self.model = IsolationForest(
            n_estimators=120, contamination="auto", random_state=42, n_jobs=1
        )
        self.model.fit(np.log1p(np.array(feats)))

    def process(self, run_id):
        start = time.perf_counter()
        rec = self.store.one(
            "SELECT r.*, d.content, d.columns_json FROM runs r"
            " JOIN datasets d ON d.id = r.dataset_id WHERE r.id = %s",
            (run_id,),
        )
        columns = json.loads(rec["columns_json"] or "[]") or COLUMNS
        is_sales = columns == COLUMNS
        model = MODEL_SALES

        # 1. Validación.
        if is_sales:
            self.store.log(run_id, "validation", "Reglas de ventas.")
            _, sales_rows = parse_csv_dynamic(rec["content"])
            rows = validate_sales(sales_rows)
        else:
            self.store.log(
                run_id,
                "validation",
                f"Esquema dinámico ({len(columns)} columnas).",
            )
            _, dyn = parse_csv_dynamic(rec["content"])
            rows = validate_generic(
                columns, [{c: r.get(c, "") for c in columns} for r in dyn]
            )
        valid = [r for r in rows if r["status"] == "valid"]

        # 2. Anomalías con IA.
        if is_sales:
            self.store.log(
                run_id,
                "anomaly",
                f"{len(valid)} válidos. Modelo {MODEL_SALES}.",
            )
            if valid:
                scores = self.model.decision_function(
                    np.log1p(np.array([r["features"] for r in valid]))
                )
                for item, s in zip(valid, scores):
                    item["score"] = float(s)
                    if s < 0:
                        item["status"] = "anomaly"
                        item["reason"] = "Atípico según IA. Revisar."
        else:
            nums = []
            for c in columns[1:]:
                try:
                    vals = [
                        float(str(r["data"].get(c, "")).replace(",", "")) for r in valid
                    ]
                    if all(math.isfinite(v) for v in vals) and len(set(vals)) > 1:
                        nums.append(c)
                except (ValueError, TypeError):
                    continue
            if valid and nums and len(valid) >= 3:
                try:
                    matrix = np.array(
                        [
                            [
                                float(str(r["data"].get(c, "0")).replace(",", ""))
                                for c in nums
                            ]
                            for r in valid
                        ]
                    )
                    m = IsolationForest(
                        n_estimators=100,
                        contamination="auto",
                        random_state=42,
                        n_jobs=1,
                    )
                    for item, s in zip(valid, m.fit(matrix).decision_function(matrix)):
                        item["score"] = float(s)
                        if s < 0:
                            item["status"] = "anomaly"
                            item["reason"] = f"Atípico en {', '.join(nums)}."
                    model = MODEL_GENERIC
                    self.store.log(
                        run_id,
                        "anomaly",
                        f"IA genérica en {', '.join(nums)}:"
                        f" {sum(r['status'] == 'anomaly' for r in valid)} alertas.",
                    )
                except Exception:
                    self.store.log(run_id, "anomaly", "IA no aplicable.")
            else:
                self.store.log(run_id, "anomaly", "Sin IA aplicable.")

        # 3. Carga (válidos sin alerta; repetidos no duplican).
        self.store.log(run_id, "loading", "Cargando a destino.")
        # Una sola transaccion: si se corta, no quedan filas a medias ni
        # contadores descuadrados. El run se re-encola limpio al reiniciar.
        with mydb.transaction() as cur:
            cur.execute("DELETE FROM run_rows WHERE run_id = %s", (run_id,))
            pipe = rec["pipeline_id"] or "p_ventas"
            loaded = existing = 0
            for item in rows:
                if item["status"] == "valid":
                    d = item["data"]
                    if is_sales:
                        done = cur.execute(
                            "INSERT IGNORE INTO sales (id, date, product,"
                            " quantity, unit_price, total, source_run)"
                            " VALUES (%s, %s, %s, %s, %s, %s, %s)",
                            (
                                d["id"],
                                d["fecha"],
                                d["producto"],
                                int(d["cantidad"]),
                                d["precio_unitario"],
                                d["total"],
                                run_id,
                            ),
                        )
                    else:
                        done = cur.execute(
                            "INSERT IGNORE INTO records (pipeline_id, run_id,"
                            " `key`, data_json, created_at)"
                            " VALUES (%s, %s, %s, %s, %s)",
                            (
                                pipe,
                                run_id,
                                str(d.get(columns[0], ""))[:256],
                                json.dumps(d, ensure_ascii=False),
                                now(),
                            ),
                        )
                    if done:
                        item["status"], loaded = "loaded", loaded + 1
                    else:
                        item["status"] = "existing"
                        item["reason"] = "Clave ya existente; se conserva."
                        existing += 1
                cur.execute(
                    "INSERT INTO run_rows"
                    " (run_id, line, data_json, status, reason, score)"
                    " VALUES (%s, %s, %s, %s, %s, %s)",
                    (
                        run_id,
                        item["line"],
                        json.dumps(item["data"], ensure_ascii=False),
                        item["status"],
                        item["reason"],
                        item.get("score"),
                    ),
                )
            invalid = sum(r["status"] == "invalid" for r in rows)
            anomalies = sum(r["status"] == "anomaly" for r in rows)
            ms = round((time.perf_counter() - start) * 1000)
            cur.execute(
                "UPDATE runs SET status = 'completed', stage = 'done',"
                " finished_at = %s, total = %s, valid = %s, invalid = %s,"
                " anomalies = %s, loaded = %s, existing = %s,"
                " model_version = %s, duration_ms = %s, error = NULL"
                " WHERE id = %s",
                (
                    now(),
                    len(rows),
                    len(valid),
                    invalid,
                    anomalies,
                    loaded,
                    existing,
                    model,
                    ms,
                    run_id,
                ),
            )
            cur.execute(
                "INSERT INTO run_logs (run_id, created_at, stage, message)"
                " VALUES (%s, %s, 'done', %s)",
                (
                    run_id,
                    now(),
                    f"{loaded} cargados, {invalid} inválidos,"
                    f" {anomalies} alertas, {existing} existentes.",
                ),
            )
            cur.execute(
                "UPDATE pipelines SET last_run = %s, run_count = run_count + 1,"
                " status = 'activo' WHERE id = %s",
                (now(), pipe),
            )

        # 4. Post-proceso: calidad, reglas, anomalías y alertas.
        try:
            from backend.profiling import (
                evaluate_rule,
                quality_score,
            )

            ds = self.store.one(
                "SELECT project_id FROM datasets WHERE id = %s",
                (rec["dataset_id"],),
            )
            proj = (ds and ds.get("project_id")) or "p_default"
            raw = [dict(it["data"]) for it in rows]
            qual = quality_score(columns, raw)
            self.store.run(
                "UPDATE datasets SET quality_score = %s WHERE id = %s",
                (qual.get("general", 0), rec["dataset_id"]),
            )
            self.store.run("DELETE FROM quality_results WHERE run_id = %s", (run_id,))
            for issue in (qual.get("issues") or [])[:30]:
                sev = str(issue.get("severity", "media")).lower()
                if sev not in ("baja", "media", "alta"):
                    sev = "media"
                self.store.run(
                    "INSERT INTO quality_results (run_id, dataset_id,"
                    " project_id, check_type, column_name, message,"
                    " severity, affected, created_at)"
                    " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (
                        run_id,
                        rec["dataset_id"],
                        proj,
                        "automatica",
                        str(issue.get("column", ""))[:120],
                        str(issue.get("problem", ""))[:500],
                        sev,
                        int(issue.get("affected", 0) or 0),
                        now(),
                    ),
                )
            for rl in self.store.all(
                "SELECT * FROM quality_rules WHERE active = 1"
                " AND (dataset_id = %s OR pipeline_id = %s)",
                (rec["dataset_id"], pipe),
            ):
                try:
                    res = evaluate_rule(
                        rl["column_name"],
                        rl["condition"],
                        rl["value"] or "",
                        columns,
                        raw,
                    )
                except Exception:
                    continue
                if res.get("failed"):
                    sev = (
                        rl["severity"]
                        if rl["severity"] in ("baja", "media", "alta", "critica")
                        else "media"
                    )
                    self.store.run(
                        "INSERT INTO quality_results (run_id, dataset_id,"
                        " project_id, check_type, column_name, message,"
                        " severity, affected, created_at)"
                        " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                        (
                            run_id,
                            rec["dataset_id"],
                            proj,
                            "regla:" + rl["id"],
                            rl["column_name"],
                            f"Regla incumplida: {rl['column_name']}"
                            f" {rl['condition']} {rl['value']}"
                            f" ({res['failed']} filas).",
                            sev,
                            int(res["failed"]),
                            now(),
                        ),
                    )
            self.store.run("DELETE FROM anomalies WHERE run_id = %s", (run_id,))
            for it in rows:
                if it["status"] != "anomaly":
                    continue
                score = it.get("score")
                sev = "alta" if score is not None and score < -0.15 else "media"
                self.store.run(
                    "INSERT INTO anomalies (run_id, dataset_id, project_id,"
                    " column_name, row_line, value, reason, severity,"
                    " score, status, created_at)"
                    " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s,"
                    " 'pendiente', %s)",
                    (
                        run_id,
                        rec["dataset_id"],
                        proj,
                        columns[0],
                        int(it.get("line", 0)),
                        json.dumps(it["data"], ensure_ascii=False)[:500],
                        str(it.get("reason", ""))[:500],
                        sev,
                        score,
                        now(),
                    ),
                )
            finished = now()
            if invalid + anomalies > 0 and qual.get("general", 100) < 90:
                self.store.alert(
                    ("critico" if qual.get("general", 100) < 70 else "advertencia"),
                    "Calidad inferior al mínimo",
                    f"Calidad {qual.get('general')}%. {invalid} inválidos"
                    f" y {anomalies} anomalías.",
                    "run",
                    run_id,
                    proj,
                )
            if anomalies > 0:
                self.store.alert(
                    "advertencia" if anomalies < 5 else "error",
                    "Anomalías detectadas",
                    f"{anomalies} valores atípicos requieren revisión.",
                    "run",
                    run_id,
                    proj,
                )
            if invalid > 0 and invalid / max(1, len(rows)) > 0.2:
                self.store.alert(
                    "error",
                    "Muchos datos inválidos",
                    f"{invalid} de {len(rows)} no cumplen reglas.",
                    "run",
                    run_id,
                    proj,
                )
        except Exception:
            import logging

            logging.exception("Post-proceso falló para run %s", run_id)
