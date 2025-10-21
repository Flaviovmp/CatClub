PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    dob TEXT,
    sex TEXT,
    cpf TEXT,
    email TEXT UNIQUE NOT NULL,
    phone TEXT,
    address TEXT,
    address2 TEXT,
    district TEXT,
    city TEXT,
    state TEXT,
    zipcode TEXT,
    country TEXT,
    password_hash TEXT NOT NULL,
    is_admin INTEGER NOT NULL DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS breeds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS colors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    breed_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    ems_code TEXT NOT NULL,
    UNIQUE(breed_id, name),
    FOREIGN KEY (breed_id) REFERENCES breeds(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS cats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    breed_id INTEGER NOT NULL,
    color_id INTEGER NOT NULL,
    dob TEXT,
    registry_number TEXT,
    registry_entity TEXT, -- FIFE Brasil, FIFE não Brasil, não FIFE
    microchip TEXT,
    sex TEXT NOT NULL,
    neutered INTEGER NOT NULL DEFAULT 0, -- 0/1
    breeder_type TEXT, -- 'eu' or 'outro'
    breeder_name TEXT,

    sire_name TEXT,
    sire_breed_id INTEGER,
    sire_color_id INTEGER,

    dam_name TEXT,
    dam_breed_id INTEGER,
    dam_color_id INTEGER,

    status TEXT NOT NULL DEFAULT 'pending', -- pending, approved, rejected
    created_at TEXT DEFAULT (datetime('now')),

    FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (breed_id) REFERENCES breeds(id),
    FOREIGN KEY (color_id) REFERENCES colors(id),
    FOREIGN KEY (sire_breed_id) REFERENCES breeds(id),
    FOREIGN KEY (sire_color_id) REFERENCES colors(id),
    FOREIGN KEY (dam_breed_id) REFERENCES breeds(id),
    FOREIGN KEY (dam_color_id) REFERENCES colors(id)
);
