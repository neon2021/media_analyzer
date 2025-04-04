-- SQLite

CREATE TABLE IF NOT EXISTS devices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid TEXT UNIQUE NOT NULL,
    mount_path TEXT,
    label TEXT,  -- 可选的描述标签（如“摄影师A_硬盘1”）
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_seen TIMESTAMP
);

CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_uuid TEXT NOT NULL,
    path TEXT NOT NULL,
    hash TEXT,
    size INTEGER,
    modified_time TEXT,
    scanned_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (device_uuid, path)
);


CREATE TABLE IF NOT EXISTS image_analysis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id INTEGER NOT NULL,
    camera_model TEXT,
    taken_time TEXT,
    gps_lat REAL,
    gps_lon REAL,
    has_faces INTEGER DEFAULT 0,
    objects TEXT,
    analyzed_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(file_id) REFERENCES files(id)
);

CREATE TABLE IF NOT EXISTS scan_progress (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_uuid TEXT NOT NULL,
    total_files INTEGER,
    new_files INTEGER,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(device_uuid) REFERENCES devices(uuid)
);
