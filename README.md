# TenderAI — MCP Server for Tender & Proposal Management

A production-ready [Model Context Protocol](https://modelcontextprotocol.io/) server that automates government/enterprise tender workflows: RFP parsing, technical proposal writing, financial proposal assembly, partner coordination, and compliance tracking.

## Features

- **18 MCP Tools** across 4 domains: Document Intelligence, Technical Proposals, Financial Proposals, Partner Coordination
- **5 Resource URI schemes** for knowledge base access: past proposals, templates, vendors, company profile, standards
- **4 Workflow Prompts** for end-to-end orchestration: tender analysis, executive summaries, partner checks, full proposal workflow
- **AI-Powered**: Uses Claude to parse RFPs, generate proposal sections, and produce compliance narratives
- **Document Generation**: Professional DOCX proposals and XLSX BOM spreadsheets
- **SQLite Database**: Tracks RFPs, proposals, vendors, BOM items, partners, and deliverables

## Quick Start

### Local Development (stdio)

```bash
# Clone and setup
cd tenders
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env — set ANTHROPIC_API_KEY

# Run
python -m app.server
```

### Claude Desktop / Claude Code Configuration

**stdio (local):**
```json
{
  "mcpServers": {
    "tenderai": {
      "command": "python",
      "args": ["-m", "app.server"],
      "cwd": "/path/to/tenders",
      "env": {
        "ANTHROPIC_API_KEY": "sk-ant-..."
      }
    }
  }
}
```

**HTTP (remote):**
```json
{
  "mcpServers": {
    "tenderai": {
      "type": "http",
      "url": "https://tender.yfi.ae/mcp",
      "headers": {
        "Authorization": "Bearer <MCP_API_KEY>"
      }
    }
  }
}
```

### Production Deployment

```bash
sudo ./setup.sh tender.yfi.ae
# Edit /opt/tenderai/.env — set ANTHROPIC_API_KEY
sudo systemctl start tenderai
```

## Tools

### Document Intelligence
| Tool | Description |
|------|-------------|
| `parse_tender_rfp` | Parse PDF/DOCX RFP and extract structured data |
| `generate_compliance_matrix` | Generate compliance matrix DOCX for an RFP |
| `check_submission_deadline` | Check deadline and calculate milestones |
| `validate_document_completeness` | Validate proposal has all required sections |

### Technical Proposals
| Tool | Description |
|------|-------------|
| `write_technical_section` | Write a single proposal section with AI |
| `build_full_technical_proposal` | Generate complete technical proposal DOCX |
| `generate_architecture_description` | Generate formal architecture narrative |
| `write_compliance_narrative` | Write compliance response for a requirement |

### Financial Proposals
| Tool | Description |
|------|-------------|
| `ingest_vendor_quote` | Parse vendor quote and extract line items |
| `build_bom` | Build Bill of Materials from vendor quotes |
| `calculate_final_pricing` | Calculate final pricing with margins |
| `generate_financial_proposal` | Generate financial proposal DOCX + BOM XLSX |

### Partner Coordination
| Tool | Description |
|------|-------------|
| `draft_partner_brief` | Draft technical requirements brief for partner |
| `create_nda_checklist` | Generate NDA checklist for partner engagement |
| `track_partner_deliverable` | Track expected deliverable from partner |

## Resources

| URI Pattern | Description |
|-------------|-------------|
| `proposals://past/{id}` | Past proposal content |
| `templates://{type}` | Proposal templates |
| `vendors://{name}` | Vendor profiles |
| `company://profile` | Company profile |
| `standards://{ref}` | Standards references |

## Prompts

| Prompt | Description |
|--------|-------------|
| `analyze_new_tender` | Full tender intake and go/no-go analysis |
| `write_executive_summary` | Tailored executive summary generation |
| `partner_suitability_check` | Evaluate partner fit for a tender |
| `full_proposal_workflow` | End-to-end proposal orchestration guide |

## Knowledge Base

Populate these directories to improve AI-generated content:

```
data/
├── knowledge_base/
│   ├── company_profile/
│   │   └── profile.md          # Company description, capabilities, differentiators
│   ├── templates/
│   │   ├── executive_summary.md
│   │   ├── technical_approach.md
│   │   └── ...                 # Section-specific templates
│   └── standards/
│       ├── iso27001.md
│       └── ...                 # Standards reference docs
├── past_proposals/
│   ├── project_alpha/
│   │   ├── executive_summary.md
│   │   └── technical_approach.md
│   └── project_beta/
│       └── ...
├── rfp_documents/              # Auto-populated by parse_tender_rfp
├── vendor_quotes/              # Vendor quote files
└── generated_proposals/        # Auto-populated output
```

## Backup

```bash
# Manual backup
./backup.sh /backups/tenderai 30

# Cron (daily at 2 AM)
0 2 * * * /opt/tenderai/backup.sh /backups/tenderai 30
```

## Architecture

```
app/
├── server.py              # Entry point — FastMCP init and wiring
├── config.py              # Settings from .env
├── tools/
│   ├── document.py        # 4 document intelligence tools
│   ├── technical.py       # 4 technical proposal tools
│   ├── financial.py       # 4 financial proposal tools
│   └── partners.py        # 3 partner coordination tools
├── resources/
│   └── knowledge.py       # 5 resource URI handlers
├── prompts/
│   └── workflows.py       # 4 workflow prompts
├── db/
│   ├── schema.sql         # SQLite schema (6 tables)
│   ├── database.py        # Async database layer
│   └── models.py          # Pydantic models
├── services/
│   ├── llm.py             # Anthropic SDK wrapper
│   ├── parser.py          # PDF/DOCX parser
│   └── docwriter.py       # DOCX/XLSX generator
└── middleware/
    └── auth.py            # Bearer token auth
```
