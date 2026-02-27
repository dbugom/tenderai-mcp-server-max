-- TenderAI SQLite Schema

CREATE TABLE IF NOT EXISTS rfp (
    id              TEXT PRIMARY KEY,
    title           TEXT NOT NULL,
    client          TEXT NOT NULL,
    sector          TEXT DEFAULT 'telecom',
    country         TEXT DEFAULT 'OM',
    rfp_number      TEXT,
    issue_date      TEXT,
    deadline        TEXT,
    submission_method TEXT,
    status          TEXT DEFAULT 'new' CHECK(status IN ('new','analyzing','in_progress','submitted','awarded','lost','cancelled')),
    file_path       TEXT,
    parsed_sections TEXT DEFAULT '{}',
    requirements    TEXT DEFAULT '[]',
    evaluation_criteria TEXT DEFAULT '[]',
    notes           TEXT DEFAULT '',
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS proposal (
    id              TEXT PRIMARY KEY,
    rfp_id          TEXT NOT NULL REFERENCES rfp(id),
    proposal_type   TEXT NOT NULL CHECK(proposal_type IN ('technical','financial','combined')),
    status          TEXT DEFAULT 'draft' CHECK(status IN ('draft','review','final','submitted')),
    title           TEXT DEFAULT '',
    sections        TEXT DEFAULT '[]',
    output_path     TEXT,
    version         INTEGER DEFAULT 1,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS vendor (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL UNIQUE,
    category        TEXT DEFAULT 'general',
    specialization  TEXT DEFAULT '',
    country         TEXT DEFAULT '',
    contact_name    TEXT DEFAULT '',
    contact_email   TEXT DEFAULT '',
    contact_phone   TEXT DEFAULT '',
    currency        TEXT DEFAULT 'USD',
    past_projects   TEXT DEFAULT '[]',
    notes           TEXT DEFAULT '',
    is_approved     INTEGER DEFAULT 0,
    rating          INTEGER DEFAULT 0,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS bom (
    id              TEXT PRIMARY KEY,
    proposal_id     TEXT NOT NULL REFERENCES proposal(id),
    category        TEXT NOT NULL,
    item_name       TEXT NOT NULL,
    description     TEXT DEFAULT '',
    vendor_id       TEXT REFERENCES vendor(id),
    manufacturer    TEXT DEFAULT '',
    part_number     TEXT DEFAULT '',
    quantity        REAL DEFAULT 1.0,
    unit            TEXT DEFAULT 'unit',
    unit_cost       REAL NOT NULL DEFAULT 0.0,
    margin_pct      REAL DEFAULT 15.0,
    total_cost      REAL GENERATED ALWAYS AS (quantity * unit_cost * (1 + margin_pct / 100.0)) STORED,
    warranty_months INTEGER DEFAULT 12,
    sort_order      INTEGER DEFAULT 0,
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS partner (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL UNIQUE,
    country         TEXT DEFAULT '',
    specialization  TEXT DEFAULT '',
    contact_name    TEXT DEFAULT '',
    contact_email   TEXT DEFAULT '',
    contact_phone   TEXT DEFAULT '',
    nda_status      TEXT DEFAULT 'none' CHECK(nda_status IN ('none','sent','signed','expired')),
    nda_signed_date TEXT,
    nda_expiry_date TEXT,
    past_projects   TEXT DEFAULT '[]',
    notes           TEXT DEFAULT '',
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS partner_deliverable (
    id              TEXT PRIMARY KEY,
    partner_id      TEXT NOT NULL REFERENCES partner(id),
    proposal_id     TEXT NOT NULL REFERENCES proposal(id),
    title           TEXT NOT NULL,
    deliverable_type TEXT DEFAULT 'document' CHECK(deliverable_type IN ('technical_input','pricing','cv','reference_letter','certification','document','other')),
    due_date        TEXT,
    status          TEXT DEFAULT 'pending' CHECK(status IN ('pending','requested','in_progress','received','approved','overdue')),
    file_path       TEXT,
    notes           TEXT DEFAULT '',
    created_at      TEXT DEFAULT (datetime('now')),
    updated_at      TEXT DEFAULT (datetime('now'))
);
