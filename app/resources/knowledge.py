"""Knowledge base resources — past proposals, templates, vendors, company profile, standards."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from app.db.database import Database
from app.services.parser import ParserService

logger = logging.getLogger(__name__)

# File types supported for past proposals and knowledge base documents
SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".doc", ".xlsx", ".xls", ".md", ".txt"}


def register_resources(mcp: FastMCP, db: Database, data_dir: Path, parser: ParserService) -> None:
    """Register all resource URI handlers on the MCP server."""

    async def _read_file(file_path: Path) -> str:
        """Read any supported file — plain text or parsed PDF/DOCX/XLSX."""
        ext = file_path.suffix.lower()
        if ext in (".md", ".txt"):
            return file_path.read_text()
        elif ext in (".pdf", ".docx", ".doc", ".xlsx", ".xls"):
            try:
                parsed = await parser.parse_file(str(file_path))
                return parsed["text"]
            except Exception as e:
                logger.warning("Could not parse %s: %s", file_path, e)
                return f"[Error reading {file_path.name}: {e}]"
        return ""

    # ------------------------------------------------------------------
    # Past Proposals: proposals://past/{id}
    # ------------------------------------------------------------------

    @mcp.resource("proposals://past/{proposal_id}")
    async def get_past_proposal(proposal_id: str) -> str:
        """Retrieve a past proposal by ID.

        Scans the data/past_proposals/{id}/ directory for all supported file types
        (PDF, DOCX, XLSX, MD, TXT) and returns their extracted text content.
        """
        proposal_dir = data_dir / "past_proposals" / proposal_id
        if not proposal_dir.exists():
            raise ValueError(f"Past proposal not found: {proposal_id}")

        parts = []
        for f in sorted(proposal_dir.iterdir()):
            if f.suffix.lower() in SUPPORTED_EXTENSIONS:
                content = await _read_file(f)
                if content:
                    parts.append(f"--- {f.name} ---\n{content}")

        if not parts:
            raise ValueError(
                f"No readable files in past proposal: {proposal_id}. "
                f"Supported formats: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
            )

        return "\n\n".join(parts)

    # ------------------------------------------------------------------
    # Templates: templates://{type}
    # ------------------------------------------------------------------

    @mcp.resource("templates://{template_type}")
    async def get_template(template_type: str) -> str:
        """Retrieve a proposal template by type.

        Reads from data/knowledge_base/templates/{type}.md
        """
        template_path = data_dir / "knowledge_base" / "templates" / f"{template_type}.md"
        if not template_path.exists():
            # List available templates
            templates_dir = data_dir / "knowledge_base" / "templates"
            available = []
            if templates_dir.exists():
                available = [f.stem for f in templates_dir.glob("*.md")]
            raise ValueError(
                f"Template not found: {template_type}. Available: {', '.join(available) or 'none'}"
            )

        return template_path.read_text()

    # ------------------------------------------------------------------
    # Vendors: vendors://{name}
    # ------------------------------------------------------------------

    @mcp.resource("vendors://{vendor_name}")
    async def get_vendor_profile(vendor_name: str) -> str:
        """Retrieve a vendor profile by name from the database."""
        vendor = await db.get_vendor_by_name(vendor_name)
        if not vendor:
            # List available vendors
            all_vendors = await db.list_vendors()
            names = [v["name"] for v in all_vendors]
            raise ValueError(
                f"Vendor not found: {vendor_name}. Known vendors: {', '.join(names) or 'none'}"
            )

        return json.dumps(vendor, indent=2, default=str)

    # ------------------------------------------------------------------
    # Company Profile: company://profile
    # ------------------------------------------------------------------

    @mcp.resource("company://profile")
    async def get_company_profile() -> str:
        """Retrieve the company profile from the knowledge base."""
        profile_path = data_dir / "knowledge_base" / "company_profile" / "profile.md"
        if not profile_path.exists():
            return "No company profile configured. Create data/knowledge_base/company_profile/profile.md"

        return profile_path.read_text()

    # ------------------------------------------------------------------
    # Standards: standards://{ref}
    # ------------------------------------------------------------------

    @mcp.resource("standards://{standard_ref}")
    async def get_standard(standard_ref: str) -> str:
        """Retrieve a standard reference document by reference code.

        Reads from data/knowledge_base/standards/{ref}.md
        """
        standard_path = data_dir / "knowledge_base" / "standards" / f"{standard_ref}.md"
        if not standard_path.exists():
            # List available standards
            standards_dir = data_dir / "knowledge_base" / "standards"
            available = []
            if standards_dir.exists():
                available = [f.stem for f in standards_dir.glob("*.md")]
            raise ValueError(
                f"Standard not found: {standard_ref}. Available: {', '.join(available) or 'none'}"
            )

        return standard_path.read_text()
