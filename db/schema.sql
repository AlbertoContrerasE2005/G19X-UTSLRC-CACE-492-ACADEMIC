-- DataOps Final · Esquema MySQL/MariaDB
-- Base: dataops (ver start.py). Tablas simples, claves claras.

CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(32) NOT NULL UNIQUE,
    name VARCHAR(80) NOT NULL,
    password_hash VARCHAR(300) NOT NULL,
    role ENUM('admin', 'operator', 'viewer') NOT NULL DEFAULT 'viewer',
    created_at VARCHAR(40) NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    token_hash CHAR(64) PRIMARY KEY,
    user_id INT NOT NULL,
    expires_at DOUBLE NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users (id)
);

CREATE TABLE IF NOT EXISTS projects (
    id VARCHAR(16) PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    description VARCHAR(1000) NOT NULL DEFAULT '',
    status VARCHAR(16) NOT NULL DEFAULT 'activo',
    owner_id INT,
    created_at VARCHAR(40) NOT NULL,
    updated_at VARCHAR(40) NOT NULL,
    FOREIGN KEY (owner_id) REFERENCES users (id)
);

CREATE TABLE IF NOT EXISTS project_members (
    project_id VARCHAR(16) NOT NULL,
    user_id INT NOT NULL,
    role VARCHAR(16) NOT NULL DEFAULT 'viewer',
    PRIMARY KEY (project_id, user_id),
    FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS datasets (
    id CHAR(32) PRIMARY KEY,
    filename VARCHAR(150) NOT NULL,
    content MEDIUMTEXT NOT NULL,
    columns_json TEXT NOT NULL,
    row_count INT NOT NULL DEFAULT 0,
    created_at VARCHAR(40) NOT NULL,
    created_by INT,
    project_id VARCHAR(16),
    file_type VARCHAR(8) NOT NULL DEFAULT 'csv',
    quality_score DOUBLE NOT NULL DEFAULT 0,
    FOREIGN KEY (created_by) REFERENCES users (id),
    FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS pipelines (
    id VARCHAR(16) PRIMARY KEY,
    name VARCHAR(80) NOT NULL,
    description VARCHAR(500) NOT NULL DEFAULT '',
    dataset_id VARCHAR(32),
    interval_minutes INT NOT NULL DEFAULT 0,
    next_run DOUBLE,
    enabled TINYINT NOT NULL DEFAULT 0,
    created_at VARCHAR(40) NOT NULL,
    created_by INT,
    project_id VARCHAR(16),
    status VARCHAR(16) NOT NULL DEFAULT 'activo',
    run_count INT NOT NULL DEFAULT 0,
    last_run VARCHAR(40),
    steps_json TEXT,
    FOREIGN KEY (dataset_id) REFERENCES datasets (id),
    FOREIGN KEY (created_by) REFERENCES users (id),
    FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS runs (
    id CHAR(32) PRIMARY KEY,
    dataset_id VARCHAR(32) NOT NULL,
    pipeline_id VARCHAR(16) NOT NULL DEFAULT 'p_ventas',
    trigger_kind VARCHAR(16) NOT NULL DEFAULT 'manual',
    status ENUM('queued', 'running', 'completed', 'failed') NOT NULL DEFAULT 'queued',
    stage VARCHAR(16) NOT NULL DEFAULT 'queued',
    created_at VARCHAR(40) NOT NULL,
    started_at VARCHAR(40),
    finished_at VARCHAR(40),
    created_by INT,
    total INT NOT NULL DEFAULT 0,
    valid INT NOT NULL DEFAULT 0,
    invalid INT NOT NULL DEFAULT 0,
    anomalies INT NOT NULL DEFAULT 0,
    loaded INT NOT NULL DEFAULT 0,
    existing INT NOT NULL DEFAULT 0,
    approved INT NOT NULL DEFAULT 0,
    rejected INT NOT NULL DEFAULT 0,
    model_version VARCHAR(32),
    duration_ms INT,
    error TEXT,
    attempts INT NOT NULL DEFAULT 0,
    parent_id CHAR(32),
    FOREIGN KEY (dataset_id) REFERENCES datasets (id),
    FOREIGN KEY (pipeline_id) REFERENCES pipelines (id),
    FOREIGN KEY (created_by) REFERENCES users (id),
    UNIQUE KEY uq_one_active (status, id)
);

CREATE TABLE IF NOT EXISTS run_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    run_id CHAR(32) NOT NULL,
    created_at VARCHAR(40) NOT NULL,
    stage VARCHAR(16) NOT NULL,
    message TEXT NOT NULL,
    FOREIGN KEY (run_id) REFERENCES runs (id),
    INDEX idx_run (run_id, id)
);

CREATE TABLE IF NOT EXISTS run_rows (
    id INT AUTO_INCREMENT PRIMARY KEY,
    run_id CHAR(32) NOT NULL,
    line INT NOT NULL,
    data_json MEDIUMTEXT NOT NULL,
    status VARCHAR(16) NOT NULL,
    reason TEXT NOT NULL,
    score DOUBLE,
    FOREIGN KEY (run_id) REFERENCES runs (id),
    INDEX idx_run_line (run_id, line)
);

-- Destino ventas (esquema fijo).
CREATE TABLE IF NOT EXISTS sales (
    id VARCHAR(64) PRIMARY KEY,
    date VARCHAR(16) NOT NULL,
    product VARCHAR(120) NOT NULL,
    quantity INT NOT NULL,
    unit_price DECIMAL(14, 2) NOT NULL,
    total DECIMAL(16, 2) NOT NULL,
    source_run CHAR(32) NOT NULL
);

-- Destino dinámico (cualquier columna en JSON).
CREATE TABLE IF NOT EXISTS records (
    id INT AUTO_INCREMENT PRIMARY KEY,
    pipeline_id VARCHAR(16),
    run_id CHAR(32) NOT NULL,
    `key` VARCHAR(256) NOT NULL,
    data_json MEDIUMTEXT NOT NULL,
    created_at VARCHAR(40) NOT NULL,
    FOREIGN KEY (run_id) REFERENCES runs (id),
    UNIQUE KEY uq_pipe_key (pipeline_id, `key`),
    INDEX idx_run (run_id)
);

CREATE TABLE IF NOT EXISTS approvals (
    id INT AUTO_INCREMENT PRIMARY KEY,
    run_id CHAR(32) NOT NULL,
    line INT NOT NULL,
    action ENUM('approved', 'rejected') NOT NULL,
    motivo VARCHAR(500) NOT NULL DEFAULT '',
    user_id INT,
    created_at VARCHAR(40) NOT NULL,
    FOREIGN KEY (run_id) REFERENCES runs (id),
    INDEX idx_run (run_id, line)
);

CREATE TABLE IF NOT EXISTS audit (
    id INT AUTO_INCREMENT PRIMARY KEY,
    created_at VARCHAR(40) NOT NULL,
    user_id INT,
    action VARCHAR(64) NOT NULL,
    entity_id VARCHAR(64)
);

-- Plataforma: calidad, anomalías, alertas, reportes, IA, actividad.

CREATE TABLE IF NOT EXISTS quality_rules (
    id VARCHAR(16) PRIMARY KEY,
    project_id VARCHAR(16),
    dataset_id VARCHAR(32),
    pipeline_id VARCHAR(16),
    column_name VARCHAR(120) NOT NULL,
    `condition` VARCHAR(32) NOT NULL,
    value VARCHAR(200) NOT NULL DEFAULT '',
    severity VARCHAR(16) NOT NULL DEFAULT 'media',
    active TINYINT NOT NULL DEFAULT 1,
    created_by INT,
    created_at VARCHAR(40) NOT NULL,
    FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE CASCADE,
    FOREIGN KEY (dataset_id) REFERENCES datasets (id) ON DELETE CASCADE,
    FOREIGN KEY (pipeline_id) REFERENCES pipelines (id) ON DELETE CASCADE,
    FOREIGN KEY (created_by) REFERENCES users (id)
);

CREATE TABLE IF NOT EXISTS quality_results (
    id INT AUTO_INCREMENT PRIMARY KEY,
    run_id CHAR(32),
    dataset_id VARCHAR(32),
    project_id VARCHAR(16),
    check_type VARCHAR(64) NOT NULL,
    column_name VARCHAR(120) NOT NULL DEFAULT '',
    message TEXT NOT NULL,
    severity VARCHAR(16) NOT NULL DEFAULT 'media',
    affected INT NOT NULL DEFAULT 0,
    created_at VARCHAR(40) NOT NULL,
    FOREIGN KEY (run_id) REFERENCES runs (id) ON DELETE CASCADE,
    FOREIGN KEY (dataset_id) REFERENCES datasets (id) ON DELETE CASCADE,
    FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE SET NULL,
    INDEX idx_run (run_id),
    INDEX idx_dataset (dataset_id)
);

CREATE TABLE IF NOT EXISTS anomalies (
    id INT AUTO_INCREMENT PRIMARY KEY,
    run_id CHAR(32),
    dataset_id VARCHAR(32),
    project_id VARCHAR(16),
    column_name VARCHAR(120) NOT NULL DEFAULT '',
    row_line INT NOT NULL DEFAULT 0,
    value TEXT NOT NULL,
    reason TEXT NOT NULL,
    severity VARCHAR(16) NOT NULL DEFAULT 'media',
    score DOUBLE,
    status VARCHAR(16) NOT NULL DEFAULT 'pendiente',
    created_at VARCHAR(40) NOT NULL,
    FOREIGN KEY (run_id) REFERENCES runs (id) ON DELETE CASCADE,
    FOREIGN KEY (dataset_id) REFERENCES datasets (id) ON DELETE CASCADE,
    FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE SET NULL,
    INDEX idx_run (run_id),
    INDEX idx_dataset (dataset_id)
);

CREATE TABLE IF NOT EXISTS alerts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    project_id VARCHAR(16),
    user_id INT,
    level VARCHAR(16) NOT NULL DEFAULT 'info',
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    entity_type VARCHAR(64) NOT NULL DEFAULT '',
    entity_id VARCHAR(64) NOT NULL DEFAULT '',
    `read` TINYINT NOT NULL DEFAULT 0,
    created_at VARCHAR(40) NOT NULL,
    FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE SET NULL,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE SET NULL,
    INDEX idx_created (created_at DESC)
);

CREATE TABLE IF NOT EXISTS reports (
    id VARCHAR(16) PRIMARY KEY,
    project_id VARCHAR(16),
    dataset_id VARCHAR(32),
    run_id CHAR(32),
    type VARCHAR(32) NOT NULL DEFAULT 'analisis',
    format VARCHAR(16) NOT NULL DEFAULT 'json',
    title VARCHAR(200) NOT NULL DEFAULT '',
    content_json MEDIUMTEXT NOT NULL,
    created_by INT,
    created_at VARCHAR(40) NOT NULL,
    FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE SET NULL,
    FOREIGN KEY (dataset_id) REFERENCES datasets (id) ON DELETE SET NULL,
    FOREIGN KEY (run_id) REFERENCES runs (id) ON DELETE SET NULL,
    FOREIGN KEY (created_by) REFERENCES users (id)
);

CREATE TABLE IF NOT EXISTS ai_queries (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT,
    project_id VARCHAR(16),
    dataset_id VARCHAR(32),
    question TEXT NOT NULL,
    answer TEXT NOT NULL,
    created_at VARCHAR(40) NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users (id),
    FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE SET NULL,
    FOREIGN KEY (dataset_id) REFERENCES datasets (id) ON DELETE SET NULL,
    INDEX idx_user (user_id, created_at DESC)
);

CREATE TABLE IF NOT EXISTS activity_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    created_at VARCHAR(40) NOT NULL,
    user_id INT,
    username VARCHAR(80) NOT NULL DEFAULT '',
    action VARCHAR(64) NOT NULL,
    entity_type VARCHAR(64) NOT NULL DEFAULT '',
    entity_id VARCHAR(64) NOT NULL DEFAULT '',
    project_id VARCHAR(16),
    detail TEXT NOT NULL,
    result VARCHAR(64) NOT NULL DEFAULT '',
    FOREIGN KEY (user_id) REFERENCES users (id),
    FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE SET NULL
);

-- Columnas extra que la plataforma espera en tablas base.
-- (Se aplican con ALTER IGNORE si ya existen; ver backend/db.py.)

-- Pipeline inicial (ventas). No se elimina desde la UI.
INSERT IGNORE INTO pipelines (id, name, description, created_at)
VALUES ('p_ventas', 'Calidad de ventas', 'Pipeline inicial de ventas.', NOW());

-- Proyecto general (todo dataset/pipeline cuelga de un proyecto).
INSERT IGNORE INTO projects (id, name, description, status, created_at, updated_at)
VALUES ('p_default', 'General', 'Proyecto general.', 'activo', NOW(), NOW());
