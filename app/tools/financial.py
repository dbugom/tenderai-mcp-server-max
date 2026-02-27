"""Financial Proposal tools — vendor quotes, BOM, pricing, financial proposal generation."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from app.db.database import Database
from app.services.docwriter import DocWriterService
from app.services.llm import LLMService
from app.services.parser import ParserService

logger = logging.getLogger(__name__)


def register_financial_tools(
    mcp: FastMCP,
    db: Database,
    llm: LLMService,
    parser: ParserService,
    docwriter: DocWriterService,
    data_dir: Path,
    default_currency: str,
    default_margin_pct: float,
) -> None:
    """Register all financial proposal tools on the MCP server."""

    @mcp.tool()
    async def ingest_vendor_quote(vendor_name: str, quote_file: str) -> dict:
        """Parse a vendor quote document and extract pricing line items.

        Supports PDF and XLSX formats. Creates or updates the vendor record
        and extracts all pricing line items.

        Args:
            vendor_name: Name of the vendor (e.g., "Cisco", "Palo Alto Networks")
            quote_file: Path to the quote document (PDF or XLSX)

        Returns:
            Dict with vendor_id, items_parsed, total, and parsed_items list
        """
        # Parse the quote file
        parsed = await parser.parse_file(quote_file)

        # Copy to vendor_quotes directory
        quotes_dir = data_dir / "vendor_quotes"
        quotes_dir.mkdir(parents=True, exist_ok=True)

        # Use LLM to extract structured pricing data
        extract_prompt = (
            "Extract pricing line items from this vendor quote as JSON:\n"
            "{\n"
            '  "currency": "USD or OMR or EUR",\n'
            '  "items": [\n'
            "    {\n"
            '      "category": "hardware|software|services|licensing|support",\n'
            '      "item_name": "product/service name",\n'
            '      "description": "brief description",\n'
            '      "manufacturer": "manufacturer name",\n'
            '      "part_number": "part number if available",\n'
            '      "quantity": 1,\n'
            '      "unit": "unit|license|month|year",\n'
            '      "unit_cost": 0.00\n'
            "    }\n"
            "  ]\n"
            "}\n\n"
            "Return ONLY valid JSON.\n\n"
            f"Document text:\n{parsed['text'][:10000]}"
        )

        result_text = await llm.generate(
            system_prompt="You are an expert at parsing vendor quotations and extracting pricing data.",
            user_prompt=extract_prompt,
        )

        try:
            extracted = json.loads(result_text.strip())
        except json.JSONDecodeError:
            if "```json" in result_text:
                json_str = result_text.split("```json")[1].split("```")[0].strip()
                extracted = json.loads(json_str)
            elif "```" in result_text:
                json_str = result_text.split("```")[1].split("```")[0].strip()
                extracted = json.loads(json_str)
            else:
                raise ValueError(f"Could not parse LLM response as JSON: {result_text[:200]}")

        # Upsert vendor
        vendor = await db.upsert_vendor(
            name=vendor_name,
            currency=extracted.get("currency", default_currency),
        )

        items = extracted.get("items", [])
        total = sum(
            item.get("quantity", 1) * item.get("unit_cost", 0) for item in items
        )

        logger.info("Ingested vendor quote: %s (%d items, total=%.2f)", vendor_name, len(items), total)

        return {
            "vendor_id": vendor["id"],
            "vendor_name": vendor_name,
            "items_parsed": len(items),
            "total": total,
            "currency": extracted.get("currency", default_currency),
            "parsed_items": items,
        }

    @mcp.tool()
    async def build_bom(rfp_id: str, vendor_quotes: list[dict]) -> dict:
        """Build a Bill of Materials from multiple vendor quotes.

        Creates a financial proposal record and inserts BOM items from the provided
        vendor quote data. Each quote dict should have: vendor_name, and items list
        (as returned by ingest_vendor_quote).

        Args:
            rfp_id: ID of the parsed RFP
            vendor_quotes: List of dicts, each with "vendor_name" and "items" (list of line items)

        Returns:
            Dict with proposal_id, item_count, subtotal, and by_category breakdown
        """
        rfp = await db.get_rfp(rfp_id)
        if not rfp:
            raise ValueError(f"RFP not found: {rfp_id}")

        # Create financial proposal
        proposal = await db.create_proposal(
            rfp_id=rfp_id,
            proposal_type="financial",
            title=f"Financial Proposal — {rfp['title']}",
        )

        item_count = 0
        sort_order = 0

        for quote in vendor_quotes:
            vendor_name = quote.get("vendor_name", "Unknown")
            vendor = await db.get_vendor_by_name(vendor_name)
            vendor_id = vendor["id"] if vendor else None

            for item in quote.get("items", []):
                await db.add_bom_item(
                    proposal_id=proposal["id"],
                    category=item.get("category", "general"),
                    item_name=item.get("item_name", "Unknown Item"),
                    unit_cost=float(item.get("unit_cost", 0)),
                    description=item.get("description", ""),
                    vendor_id=vendor_id,
                    manufacturer=item.get("manufacturer", vendor_name),
                    part_number=item.get("part_number", ""),
                    quantity=float(item.get("quantity", 1)),
                    unit=item.get("unit", "unit"),
                    margin_pct=default_margin_pct,
                    warranty_months=item.get("warranty_months", 12),
                    sort_order=sort_order,
                )
                item_count += 1
                sort_order += 1

        # Get totals
        totals = await db.get_bom_totals(proposal["id"])

        logger.info("Built BOM for RFP %s: %d items, total=%.2f", rfp_id, item_count, totals["total"])

        return {
            "proposal_id": proposal["id"],
            "item_count": item_count,
            "subtotal": totals["total"],
            "by_category": totals["by_category"],
            "currency": default_currency,
        }

    @mcp.tool()
    async def calculate_final_pricing(
        proposal_id: str, margin_rules: dict | None = None
    ) -> dict:
        """Calculate final pricing for a financial proposal with margin adjustments.

        Applies margin rules per category and recalculates all totals. The SQLite
        computed column handles the total_cost calculation automatically.

        Args:
            proposal_id: ID of the financial proposal
            margin_rules: Optional dict mapping category names to margin percentages.
                         Example: {"hardware": 12, "software": 20, "services": 25}

        Returns:
            Dict with total, by_category breakdown, currency, and item_count
        """
        proposal = await db.get_proposal(proposal_id)
        if not proposal:
            raise ValueError(f"Proposal not found: {proposal_id}")

        bom_items = await db.get_bom_for_proposal(proposal_id)
        if not bom_items:
            raise ValueError(f"No BOM items found for proposal {proposal_id}")

        # Apply margin rules if provided
        if margin_rules:
            for item in bom_items:
                category = item.get("category", "").lower()
                if category in margin_rules:
                    new_margin = margin_rules[category]
                    if item["margin_pct"] != new_margin:
                        await db.update_bom_item(item["id"], margin_pct=new_margin)

        # Re-fetch totals after margin updates
        totals = await db.get_bom_totals(proposal_id)

        logger.info("Calculated pricing for proposal %s: total=%.2f", proposal_id, totals["total"])

        return {
            "proposal_id": proposal_id,
            "total": totals["total"],
            "by_category": totals["by_category"],
            "item_count": totals["item_count"],
            "currency": default_currency,
            "margin_rules_applied": margin_rules or {"default": default_margin_pct},
        }

    @mcp.tool()
    async def generate_financial_proposal(rfp_id: str, proposal_id: str) -> str:
        """Generate a complete financial proposal DOCX with pricing tables and terms.

        Also generates a BOM spreadsheet (XLSX) alongside the DOCX document.

        Args:
            rfp_id: ID of the parsed RFP
            proposal_id: ID of the financial proposal (with BOM items)

        Returns:
            File path to the generated financial proposal DOCX
        """
        rfp = await db.get_rfp(rfp_id)
        if not rfp:
            raise ValueError(f"RFP not found: {rfp_id}")

        proposal = await db.get_proposal(proposal_id)
        if not proposal:
            raise ValueError(f"Proposal not found: {proposal_id}")

        bom_items = await db.get_bom_for_proposal(proposal_id)
        if not bom_items:
            raise ValueError(f"No BOM items found for proposal {proposal_id}")

        metadata = {
            "client": rfp["client"],
            "company": "TenderAI",
            "rfp_number": rfp.get("rfp_number", ""),
            "rfp_id": rfp_id,
            "title": rfp["title"],
            "currency": default_currency,
        }

        # Generate DOCX
        docx_path = docwriter.create_financial_proposal(bom_items, metadata)

        # Also generate BOM spreadsheet
        xlsx_path = docwriter.create_bom_spreadsheet(bom_items, metadata)

        # Update proposal with output path
        await db.update_proposal(proposal_id, output_path=docx_path, status="review")

        logger.info("Generated financial proposal: %s (BOM: %s)", docx_path, xlsx_path)
        return docx_path
