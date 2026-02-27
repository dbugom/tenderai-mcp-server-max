# TenderAI — Deployment & Usage Guide

---

## Table of Contents

1. [Folder Structure Overview](#1-folder-structure-overview)
2. [Where to Put Your Files](#2-where-to-put-your-files)
3. [Local Setup (Development)](#3-local-setup-development)
4. [Production Deployment (VPS)](#4-production-deployment-vps)
5. [Connecting to Claude Desktop / Claude Code](#5-connecting-to-claude-desktop--claude-code)
6. [Using TenderAI — Step by Step](#6-using-tenderai--step-by-step)
7. [Complete Tool Reference](#7-complete-tool-reference)
8. [Backups & Maintenance](#8-backups--maintenance)
9. [Troubleshooting](#9-troubleshooting)

---

## 1. Folder Structure Overview

After setup, the project has this structure:

```
tenders/
│
├── app/                            # Application code (do not modify unless developing)
│   ├── server.py                   # Entry point
│   ├── config.py                   # Configuration loader
│   ├── tools/                      # MCP tools (document, technical, financial, partners, indexing)
│   ├── resources/                  # Knowledge base resource handlers
│   ├── prompts/                    # Workflow prompts
│   ├── db/                         # Database schema, async layer, FTS5 + vector search
│   ├── services/                   # LLM, parser, document writer, embeddings
│   └── middleware/                 # Authentication
│
├── data/                           # ⭐ YOUR DATA GOES HERE
│   ├── rfp_documents/              # Auto-populated — parsed RFP files are copied here
│   ├── past_proposals/             # 📁 PUT YOUR PREVIOUS TENDER SUBMISSIONS HERE
│   ├── vendor_quotes/              # Vendor pricing documents
│   ├── generated_proposals/        # Auto-populated — generated DOCX/XLSX output
│   └── knowledge_base/
│       ├── company_profile/        # 📁 PUT YOUR COMPANY PROFILE HERE
│       ├── templates/              # 📁 PUT YOUR SECTION TEMPLATES HERE
│       └── standards/              # 📁 PUT YOUR STANDARDS REFERENCES HERE
│
├── db/                             # SQLite database (auto-created)
│   └── tenderai.db
│
├── venv/                           # Python virtual environment
├── nginx/                          # Nginx reverse proxy config
├── systemd/                        # Systemd service unit
├── requirements.txt
├── .env                            # Your configuration (create from .env.example)
├── .env.example
├── setup.sh                        # Production provisioning script
├── backup.sh                       # Backup script
└── README.md
```

---

## 2. Where to Put Your Files

### 📁 RFP Documents — Where to Copy the RFP

You do **not** need to manually copy RFPs into any folder. When you use the
`parse_tender_rfp` tool, just provide the path to the file wherever it is on
your system. TenderAI will:

1. Parse the PDF/DOCX at the path you provide
2. Automatically copy it to `data/rfp_documents/` for archival
3. Extract title, client, deadline, requirements, and evaluation criteria
4. Store everything in the database

**Example:** If you download an RFP to `~/Downloads/TRA_Network_Upgrade_2026.pdf`,
you tell Claude:

> "Parse the RFP at /home/kitchen/Downloads/TRA_Network_Upgrade_2026.pdf"

Claude calls `parse_tender_rfp` and the file gets archived automatically.

**However**, if you want to organize RFPs manually before parsing, you can place
them in:

```
data/rfp_documents/
├── TRA_Network_Upgrade_2026.pdf
├── MOD_Security_Systems_RFP.docx
└── Omantel_5G_Core_Tender.pdf
```

---

### 📁 Past Proposals — Where to Put Previously Submitted Tenders

This is **critical** for AI quality. Past proposals are used as reference context
when writing new proposals, so the more relevant past work you provide, the
better the generated content.

**Location:** `data/past_proposals/`

**Supported formats:** PDF, DOCX, XLSX, MD, TXT — you can drop in your original
submission files directly. No need to convert anything.

**Structure:** Create one subfolder per past project, using a short identifier.
You can put the files in their original format:

```
data/past_proposals/
├── tra_network_2024/
│   ├── TRA_Technical_Proposal_2024.pdf          # Your full submitted PDF
│   ├── TRA_Technical_Proposal_2024.docx         # Or the Word source file
│   └── TRA_Cost_Sheet_2024.xlsx                  # The cost/margin Excel sheet
│
├── omantel_5g_2024/
│   ├── Omantel_5G_Technical.pdf
│   └── Omantel_5G_BOM.xlsx
│
└── mod_security_2023/
    └── MOD_Security_Full_Proposal.docx
```

**How it works:**
- TenderAI automatically parses PDF and DOCX files to extract text content
- XLSX files are read to extract pricing/BOM data for financial reference
- The AI uses this extracted content as grounding when writing new sections
- You do **not** need to split proposals into separate section files

**Indexing past proposals (recommended):**

After uploading past proposals, you should **index** them for fast search:

> "Index the past proposal in tra_network_2024"

This parses all files, uses AI to extract structured metadata (title, client,
technologies, pricing, etc.), and creates a searchable index. Indexed proposals
are found instantly when writing new proposals instead of re-parsing files every
time.

See [Workflow 11: Index Past Proposals](#workflow-11-index-past-proposals) for details.

**File naming tips (optional but helpful):**
- If you want the AI to match a file to a specific section, include the section
  name in the filename:
  - `technical_approach_tra_2024.pdf` — matched when writing "Technical Approach"
  - `executive_summary.docx` — matched when writing "Executive Summary"
- If your files don't have section-specific names, TenderAI will still use them
  as general reference context (especially for the Company Profile and Past
  Successful Projects opening pages)

**You can also use plain text if you prefer:**
```
data/past_proposals/tra_network_2024/
├── executive_summary.md
├── technical_approach.md
└── solution_architecture.md
```

Both approaches work — use whatever is easiest. Dropping in your original
PDF/DOCX submission files is the fastest way to get started.

---

### 📁 Company Profile — Your Company Information

This is the single most important knowledge base file. Every proposal section
generated by the AI references this profile for accurate company details.

**Location:** `data/knowledge_base/company_profile/`

**Supported formats:** PDF, DOCX, or MD — use whichever you already have.

If you already have a company profile document (many companies do for tender
submissions), just drop it in:

```
data/knowledge_base/company_profile/
├── profile.md                    # Option A: Markdown (simplest to edit)
├── Company_Profile_2025.pdf      # Option B: Your existing PDF
└── Company_Profile_2025.docx     # Option C: Your existing Word doc
```

TenderAI checks for markdown first (`profile.md`), then falls back to parsing
PDF/DOCX files in the folder. You only need one of these.

Create a markdown file or drop in your existing document with your company information:

```markdown
# Company Profile

## Company Name
Your Company Name LLC

## Overview
Brief description of your company (2-3 paragraphs covering what you do,
where you operate, and your market position).

## Headquarters
Muscat, Sultanate of Oman

## Founded
2005

## Key Capabilities
- Telecommunications network design and deployment
- IT infrastructure and data center solutions
- Cybersecurity consulting and managed services
- Systems integration for government and enterprise

## Certifications
- ISO 9001:2015 Quality Management
- ISO 27001:2013 Information Security
- Cisco Gold Partner
- Palo Alto Networks Platinum Partner

## Key Personnel
- CEO: Name — 20+ years in telecom
- CTO: Name — Specializes in network architecture
- Head of Projects: Name — PMP, PRINCE2

## Past Clients
- Telecommunications Regulatory Authority (TRA)
- Omantel
- Ministry of Defence
- Central Bank of Oman

## Differentiators
- Local presence with 150+ engineers in Oman
- Proven track record in government tenders
- Strategic partnerships with Cisco, Palo Alto, Fortinet, F5
- 24/7 Network Operations Center in Muscat
```

---

### 📁 Section Templates — Boilerplate Structure for Proposals

Templates provide structural guidance for each proposal section. Optional but
improves consistency.

**Location:** `data/knowledge_base/templates/`

**Naming:** Match the section name with underscores:

```
data/knowledge_base/templates/
├── executive_summary.md
├── technical_approach.md
├── solution_architecture.md
├── implementation_methodology.md
├── project_timeline.md
├── team_qualifications.md
└── past_experience.md
```

**Example `data/knowledge_base/templates/technical_approach.md`:**

```markdown
# Technical Approach Template

## Structure
1. Understanding of Requirements — demonstrate grasp of client needs
2. Proposed Solution Overview — high-level solution description
3. Key Design Principles — guiding design decisions
4. Technology Selection — justify each technology choice
5. Compliance with Requirements — point-by-point alignment

## Tone
- Formal, confident, third-person
- "The proposed solution..." not "We will..."
- Quantify where possible

## Length
- 800-1200 words
- Include subsections with clear headings
```

---

### 📁 Standards References — Regulatory and Technical Standards

For compliance-heavy tenders, provide standard reference summaries.

**Location:** `data/knowledge_base/standards/`

```
data/knowledge_base/standards/
├── iso27001.md           # Information Security standard
├── iso9001.md            # Quality Management standard
├── tra_regulations.md    # TRA-specific regulations
└── nist_csf.md           # NIST Cybersecurity Framework
```

---

## 3. Local Setup (Development)

Use this when running TenderAI on your own machine, connecting via Claude Code
or Claude Desktop locally.

### Step 1: Prerequisites

```bash
# Ensure Python 3.10+ is installed
python3 --version

# Ensure pip is available
pip3 --version
```

### Step 2: Set Up the Project

```bash
cd /home/kitchen/Desktop/tenders

# Create Python virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### Step 3: Configure Environment

```bash
# Create your .env file from the example
cp .env.example .env

# Edit the .env file
nano .env
```

**Minimum required changes in `.env`:**

```ini
# REQUIRED — your Anthropic API key
ANTHROPIC_API_KEY=sk-ant-api03-your-actual-key-here

# REQUIRED — your company name
COMPANY_NAME=Your Company Name LLC

# OPTIONAL — enables vector/semantic search for past proposals
# Get a free key at https://dashboard.voyageai.com/
VOYAGE_API_KEY=pa-your-voyage-key-here

# Optional — change currency if needed (default: OMR)
DEFAULT_CURRENCY=OMR

# Keep transport as stdio for local use
TRANSPORT=stdio
```

> **Note on Voyage AI:** The `VOYAGE_API_KEY` is optional. Without it, past
> proposal search uses keyword matching (FTS5) which works well. With it, you
> also get semantic/vector search that finds similar proposals even when exact
> keywords don't match. Voyage AI offers 200M free tokens — more than enough
> for indexing hundreds of proposals.

### Step 4: Prepare Your Knowledge Base

```bash
# Create your company profile (IMPORTANT — do this first)
# Option A: Write a new one
nano data/knowledge_base/company_profile/profile.md

# Option B: Copy your existing company profile PDF or DOCX
cp ~/Documents/Company_Profile_2025.pdf data/knowledge_base/company_profile/

# Add past proposals — just copy your original submission files
mkdir -p data/past_proposals/tra_network_2024
cp ~/Documents/Tenders/TRA_2024/Technical_Proposal.pdf data/past_proposals/tra_network_2024/
cp ~/Documents/Tenders/TRA_2024/Cost_Sheet.xlsx data/past_proposals/tra_network_2024/

# Add templates if you have them
nano data/knowledge_base/templates/executive_summary.md
```

### Step 5: Test the Server

```bash
# Activate venv if not already active
source venv/bin/activate

# Run the server (it will start in stdio mode and wait for input)
python -m app.server
```

You should see on stderr:

```
2026-02-27 12:00:00 [INFO] tenderai: Voyage AI embeddings enabled — model=voyage-3-lite, dim=512
2026-02-27 12:00:00 [INFO] tenderai: TenderAI server built — transport=stdio
2026-02-27 12:00:00 [INFO] app.db.database: sqlite-vec loaded — vector search enabled (dim=512)
2026-02-27 12:00:00 [INFO] app.db.database: Database connected: db/tenderai.db (vec=True)
2026-02-27 12:00:00 [INFO] tenderai: Starting stdio transport
```

If you don't have `VOYAGE_API_KEY` set, you'll see `VOYAGE_API_KEY not set — vector search disabled, using FTS5 only` instead, which is fine.

Press `Ctrl+C` to stop. If you see these logs, the server works.

### Step 6: Interactive Testing (Optional)

```bash
# Use FastMCP's built-in inspector to test tools interactively
fastmcp dev app/server.py
```

This opens a web UI where you can call tools, read resources, and test prompts.

---

## 4. Production Deployment (VPS)

For remote access (e.g., from Claude Desktop on your laptop to a Hetzner VPS).

### Step 1: Upload the Project to Your VPS

```bash
# From your local machine
rsync -avz --exclude='venv' --exclude='db/*.db' \
  /home/kitchen/Desktop/tenders/ \
  root@your-vps-ip:/tmp/tenderai/
```

### Step 2: Run the Setup Script

```bash
# SSH into your VPS
ssh root@your-vps-ip

# Run the automated setup
cd /tmp/tenderai
sudo ./setup.sh tender.yfi.ae
```

The script will:
- Install Python, nginx, certbot, SQLite
- Create a `tenderai` system user
- Copy files to `/opt/tenderai/`
- Create a Python venv and install dependencies
- Generate a random `MCP_API_KEY` (printed to screen — save it)
- Set up systemd service and nginx reverse proxy
- Obtain an SSL certificate via Let's Encrypt

### Step 3: Configure

```bash
# Edit the environment file
sudo nano /opt/tenderai/.env
```

Set your Anthropic API key:
```ini
ANTHROPIC_API_KEY=sk-ant-api03-your-actual-key-here
COMPANY_NAME=Your Company Name LLC
```

### Step 4: Upload Your Knowledge Base

```bash
# From your local machine, upload past proposals and company profile
rsync -avz data/knowledge_base/ root@your-vps-ip:/opt/tenderai/data/knowledge_base/
rsync -avz data/past_proposals/ root@your-vps-ip:/opt/tenderai/data/past_proposals/

# Fix permissions on the VPS
ssh root@your-vps-ip "chown -R tenderai:tenderai /opt/tenderai/data"
```

### Step 5: Start the Service

```bash
sudo systemctl start tenderai
sudo systemctl status tenderai
```

### Step 6: Verify

```bash
# Check if it's running
curl https://tender.yfi.ae/mcp
```

### Step 7: View Logs

```bash
sudo journalctl -u tenderai -f
```

---

## 5. Connecting to Claude Desktop / Claude Code

### Option A: Local stdio (Development)

Add to your Claude Desktop config (`~/.config/claude/claude_desktop_config.json`)
or Claude Code config:

```json
{
  "mcpServers": {
    "tenderai": {
      "command": "/home/kitchen/Desktop/tenders/venv/bin/python",
      "args": ["-m", "app.server"],
      "cwd": "/home/kitchen/Desktop/tenders",
      "env": {
        "ANTHROPIC_API_KEY": "sk-ant-api03-your-key-here"
      }
    }
  }
}
```

### Option B: Remote HTTP (Production)

```json
{
  "mcpServers": {
    "tenderai": {
      "type": "http",
      "url": "https://tender.yfi.ae/mcp",
      "headers": {
        "Authorization": "Bearer YOUR_MCP_API_KEY_HERE"
      }
    }
  }
}
```

Replace `YOUR_MCP_API_KEY_HERE` with the key generated during setup (or the
value you set in `.env`).

After adding the config, restart Claude Desktop / Claude Code. You should see
TenderAI tools available.

---

## 6. Using TenderAI — Step by Step

### Workflow 1: Parse a New RFP

**What you say to Claude:**

> "Parse the RFP at /home/kitchen/Downloads/TRA_RFP_2026.pdf"

**What happens:**
1. Claude calls `parse_tender_rfp` with your file path
2. The PDF is parsed (text + tables extracted)
3. AI analyzes the content and extracts structured data
4. File is copied to `data/rfp_documents/`
5. You get back: rfp_id, title, client, deadline, requirements, evaluation criteria

**Save the rfp_id** — you'll use it for everything else.

---

### Workflow 2: Analyze the Tender (Go/No-Go)

> "Analyze this tender and give me a go/no-go recommendation. RFP ID: abc123"

Claude uses the `analyze_new_tender` prompt to produce:
- Executive summary of the opportunity
- Go/No-Go recommendation with justification
- Risk assessment
- Recommended partners
- Estimated effort

---

### Workflow 3: Check the Deadline

> "What's the deadline for RFP abc123?"

Claude calls `check_submission_deadline` and returns:
- Deadline date and days remaining
- Urgency status (on_track / warning / urgent / critical)
- Milestone dates (when to start drafting, review deadlines, etc.)

---

### Workflow 4: Write the Technical Proposal

**Option A — One section at a time (recommended for review):**

> "Write the Technical Approach section for RFP abc123"

> "Write the Solution Architecture section for RFP abc123. Context: We're proposing a hub-and-spoke topology with Cisco ISR routers and Palo Alto firewalls."

**Option B — Full proposal at once:**

> "Build the full technical proposal for RFP abc123"

This generates all 9 standard sections in the correct submission order:

1. **Company Profile** ← opening pages (before TOC)
2. **Past Successful Projects** ← opening pages (before TOC)
3. Table of Contents
4. Executive Summary
5. Technical Approach
6. Solution Architecture
7. Implementation Methodology
8. Project Timeline
9. Team Qualifications
10. Past Experience

The generated DOCX follows the standard government tender structure where the
first few pages are your Company Profile and Past Successful Projects, just
like your real submissions. These sections are placed before the Table of
Contents, with the technical body following after.

The AI uses your company profile document and past submitted proposals (PDF/DOCX
from `data/past_proposals/`) as reference material when generating these sections.

**Output:** A professionally formatted DOCX saved to `data/generated_proposals/`

---

### Workflow 5: Generate Architecture Description

> "Generate an architecture description for a hub-and-spoke topology using Cisco ISR 4451, Palo Alto PA-5200, and F5 BIG-IP. RFP ID: abc123"

Returns a detailed narrative covering topology, components, redundancy,
security, and scalability.

---

### Workflow 6: Generate Compliance Matrix

> "Generate a compliance matrix for RFP abc123"

For each requirement in the RFP, AI generates a compliance status and narrative
response. Output is a DOCX with a formatted table.

---

### Workflow 7: Financial Proposal (Vendor Quotes → BOM → Pricing)

**Step 1 — Ingest vendor quotes:**

> "Ingest this Cisco quote from /home/kitchen/Downloads/cisco_quote.pdf for vendor Cisco Systems"

> "Ingest this Palo Alto quote from /home/kitchen/Downloads/pa_quote.xlsx for vendor Palo Alto Networks"

**Step 2 — Build the BOM:**

> "Build a BOM for RFP abc123 using the Cisco and Palo Alto quotes we just ingested"

**Step 3 — Adjust pricing:**

> "Calculate final pricing for proposal xyz789 with these margins: hardware 12%, software 20%, services 25%"

**Step 4 — Generate financial proposal:**

> "Generate the financial proposal document for RFP abc123, proposal xyz789"

**Output:** DOCX with pricing tables + XLSX BOM spreadsheet in
`data/generated_proposals/`

---

### Workflow 8: Partner Coordination

**Draft a brief for a partner:**

> "Draft a technical brief for our partner Telefonica for RFP abc123"

**Create an NDA checklist:**

> "Create an NDA checklist for Telefonica for RFP abc123"

**Track a deliverable:**

> "Track a deliverable from Telefonica for RFP abc123: 'Core network pricing sheet', deadline 2026-03-15"

---

### Workflow 9: Validate Completeness Before Submission

> "Validate document completeness for RFP abc123"

Returns:
- Which mandatory sections are present/missing
- Warnings about missing deadline, requirements, or proposals
- Overall completeness status

---

### Workflow 10: Full End-to-End (Orchestrated)

> "Walk me through the full proposal workflow for RFP abc123"

Claude uses the `full_proposal_workflow` prompt which provides step-by-step
orchestration across all phases: intake, partner coordination, technical
proposal, financial proposal, review and submission.

---

### Workflow 11: Index Past Proposals

After uploading past proposal files to `data/past_proposals/`, index them for
fast search. Indexing parses all files once, extracts structured metadata using
AI, and stores it in the database.

**Index a single proposal:**

> "Index the past proposal in tra_network_2024"

**What happens:**
1. All files in the folder are parsed (PDF, DOCX, XLSX, MD, TXT)
2. AI extracts: title, client, sector, technologies, pricing, keywords
3. A human-readable `_summary.md` is saved in the folder
4. Metadata is stored in the database for instant search (FTS5 keyword index)
5. If Voyage AI is configured, a vector embedding is generated for semantic search

**Index multiple proposals:**

> "Index all the past proposals in these folders: tra_network_2024, omantel_5g_2024, mod_security_2023"

**Upload from a remote machine and index:**

```bash
# Upload via scp
scp -r my-proposal/ root@tender.yfi.ae:/opt/tenderai/data/past_proposals/tra-network-2024/

# Then tell Claude:
# "Index the past proposal in tra-network-2024"
```

---

### Workflow 12: Search Past Proposals

Once proposals are indexed, you can search them instantly.

**Keyword search (always available):**

> "Search past proposals for network infrastructure telecom"

> "Search past proposals for 'core network' in the telecom sector"

**Semantic search (requires Voyage AI key):**

> "Search past proposals semantically for large-scale government IT modernization projects"

This finds proposals that are conceptually similar even if they don't contain
the exact keywords.

**Search modes:**
- `keyword` — FTS5 with BM25 ranking. Supports `"quoted phrases"`, `prefix*`, `AND/OR` operators
- `semantic` — Vector similarity via Voyage AI embeddings
- `hybrid` — Both combined using Reciprocal Rank Fusion (best results)
- `auto` (default) — Uses hybrid if Voyage AI is configured, keyword otherwise

> "Search past proposals for 5G deployment in hybrid mode"

---

### Workflow 13: List All Indexed Proposals

> "List all indexed past proposals"

Returns a summary of every indexed proposal with aggregate stats: breakdown by
sector, by country, and total combined value.

---

## 7. Complete Tool Reference

| # | Tool | What It Does |
|---|------|-------------|
| 1 | `parse_tender_rfp` | Parse PDF/DOCX RFP → structured data + database record |
| 2 | `generate_compliance_matrix` | RFP requirements → compliance matrix DOCX |
| 3 | `check_submission_deadline` | Show deadline, days remaining, milestone dates |
| 4 | `validate_document_completeness` | Check all mandatory sections exist |
| 5 | `write_technical_section` | Write one proposal section with AI |
| 6 | `build_full_technical_proposal` | Generate all sections → assembled DOCX |
| 7 | `generate_architecture_description` | Technical architecture narrative |
| 8 | `write_compliance_narrative` | Compliance paragraph for one requirement |
| 9 | `ingest_vendor_quote` | Parse vendor PDF/XLSX → extract line items |
| 10 | `build_bom` | Combine vendor quotes → Bill of Materials |
| 11 | `calculate_final_pricing` | Apply margins → final pricing |
| 12 | `generate_financial_proposal` | BOM → financial proposal DOCX + BOM XLSX |
| 13 | `draft_partner_brief` | Generate partner requirements brief |
| 14 | `create_nda_checklist` | Generate NDA checklist for partner |
| 15 | `track_partner_deliverable` | Track expected partner deliverable |
| 16 | `index_past_proposal` | Parse + AI-summarize a past proposal folder → searchable index |
| 17 | `search_past_proposals` | Search indexed proposals (keyword, semantic, or hybrid) |
| 18 | `list_indexed_proposals` | List all indexed proposals with stats |

---

## 8. Backups & Maintenance

### Manual Backup

```bash
./backup.sh /path/to/backup/dir 30
```

This backs up:
- SQLite database (safe online backup)
- Entire `data/` directory (RFPs, proposals, knowledge base)
- `.env` configuration

Old backups beyond 30 days are automatically deleted.

### Automated Daily Backup (Cron)

```bash
# Add to crontab (runs daily at 2 AM)
sudo crontab -e

# Add this line:
0 2 * * * /opt/tenderai/backup.sh /backups/tenderai 30
```

### Updating TenderAI

```bash
# On your VPS
cd /opt/tenderai
sudo systemctl stop tenderai

# Upload new files (from your local machine)
rsync -avz --exclude='venv' --exclude='db' --exclude='data' --exclude='.env' \
  /home/kitchen/Desktop/tenders/ root@your-vps:/opt/tenderai/

# Reinstall dependencies if requirements changed
sudo -u tenderai /opt/tenderai/venv/bin/pip install -r requirements.txt

sudo systemctl start tenderai
```

---

## 9. Troubleshooting

### Server won't start

```bash
# Check logs
journalctl -u tenderai -n 50

# Common fixes:
# 1. Missing ANTHROPIC_API_KEY in .env
# 2. Python venv not created: python3 -m venv venv
# 3. Dependencies not installed: pip install -r requirements.txt
```

### "RFP not found" errors

The `rfp_id` is a 12-character hex string returned by `parse_tender_rfp`.
Make sure you're using the exact ID, not the filename or title.

### Generated DOCX files — where are they?

All generated documents go to: `data/generated_proposals/`

```bash
ls -la data/generated_proposals/
```

### Database reset (start fresh)

```bash
rm db/tenderai.db
# The database is recreated automatically on next server start
```

### SSL certificate renewal (production)

Certbot auto-renews. To manually renew:

```bash
sudo certbot renew
sudo systemctl reload nginx
```

---

## Quick Reference — Folder Cheat Sheet

| What | Where | Format |
|------|-------|--------|
| **RFP files to parse** | Anywhere on disk (auto-copied to `data/rfp_documents/`) | PDF, DOCX |
| **Past submitted proposals** | `data/past_proposals/{project_name}/` | PDF, DOCX, XLSX, MD, TXT |
| **Past cost/margin sheets** | `data/past_proposals/{project_name}/` | XLSX (alongside the proposal) |
| **Indexed proposal summaries** | `data/past_proposals/{project_name}/_summary.md` (auto) | Markdown |
| **Company profile** | `data/knowledge_base/company_profile/` | PDF, DOCX, or MD |
| **Section templates** | `data/knowledge_base/templates/{section_name}.md` | Markdown |
| **Standards references** | `data/knowledge_base/standards/{ref}.md` | Markdown |
| **Vendor quotes** | Anywhere on disk (provide path to tool) | PDF, XLSX |
| **Generated output** | `data/generated_proposals/` (auto) | DOCX, XLSX |
| **Database** | `db/tenderai.db` (auto) | SQLite (+ FTS5 index + vector embeddings) |
| **Configuration** | `.env` | Key=Value |
