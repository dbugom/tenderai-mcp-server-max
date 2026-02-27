"""Partner Coordination tools — briefs, NDA checklists, deliverable tracking."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from app.db.database import Database
from app.services.llm import LLMService

logger = logging.getLogger(__name__)


def register_partner_tools(
    mcp: FastMCP,
    db: Database,
    llm: LLMService,
    data_dir: Path,
) -> None:
    """Register all partner coordination tools on the MCP server."""

    @mcp.tool()
    async def draft_partner_brief(partner_name: str, rfp_id: str) -> str:
        """Draft a technical requirements brief for a partner/subcontractor.

        Generates a professional document outlining the project scope, deliverables
        expected from the partner, timeline, and format requirements.

        Args:
            partner_name: Name of the partner company
            rfp_id: ID of the parsed RFP

        Returns:
            Markdown text of the partner brief
        """
        rfp = await db.get_rfp(rfp_id)
        if not rfp:
            raise ValueError(f"RFP not found: {rfp_id}")

        # Ensure partner exists in DB
        partner = await db.get_partner_by_name(partner_name)
        if not partner:
            partner = await db.upsert_partner(name=partner_name)

        context_docs = [
            f"RFP Title: {rfp['title']}\n"
            f"Client: {rfp['client']}\n"
            f"Sector: {rfp['sector']}\n"
            f"Country: {rfp['country']}\n"
            f"Deadline: {rfp.get('deadline', 'TBD')}\n\n"
            f"Requirements:\n" + "\n".join(
                f"- {r}" if isinstance(r, str) else f"- {r.get('requirement', str(r))}"
                for r in rfp.get("requirements", [])
            )
        ]

        if partner.get("specialization"):
            context_docs.append(f"Partner Specialization: {partner['specialization']}")

        user_prompt = (
            f"Draft a technical requirements brief for {partner_name} as a subcontractor/partner "
            f"for the tender '{rfp['title']}'.\n\n"
            "Include:\n"
            "1. Project Background — brief overview of the tender and client\n"
            "2. Scope of Work — specific deliverables required from the partner\n"
            "3. Technical Requirements — specifications and standards to meet\n"
            "4. Deliverables — list of documents/items expected\n"
            "5. Timeline — key dates and deadlines\n"
            "6. Submission Format — how to submit their input\n"
            "7. Confidentiality — note about NDA requirements\n\n"
            "Write in a professional, clear style suitable for external communication."
        )

        brief = await llm.generate_section("partner_brief", user_prompt, context_docs)

        logger.info("Drafted partner brief for %s (RFP: %s)", partner_name, rfp_id)
        return brief.strip()

    @mcp.tool()
    async def create_nda_checklist(partner_name: str, rfp_id: str) -> dict:
        """Create an NDA checklist for a partner engagement.

        Generates a comprehensive checklist of NDA items and updates the partner's
        NDA status in the database.

        Args:
            partner_name: Name of the partner company
            rfp_id: ID of the parsed RFP

        Returns:
            Dict with checklist_items list and partner_id
        """
        rfp = await db.get_rfp(rfp_id)
        if not rfp:
            raise ValueError(f"RFP not found: {rfp_id}")

        # Ensure partner exists
        partner = await db.get_partner_by_name(partner_name)
        if not partner:
            partner = await db.upsert_partner(name=partner_name)

        # Standard NDA checklist items
        checklist_items = [
            {
                "item": "Confidentiality Scope",
                "description": f"Define what information related to '{rfp['title']}' is considered confidential, including RFP documents, pricing, technical designs, and client information.",
                "status": "pending",
            },
            {
                "item": "Term and Duration",
                "description": "NDA should be effective from signing date and remain in force for a minimum of 3 years after project completion or termination of discussions.",
                "status": "pending",
            },
            {
                "item": "Permitted Disclosures",
                "description": "Specify that confidential information may only be shared with employees and subcontractors who need-to-know, and who are bound by similar obligations.",
                "status": "pending",
            },
            {
                "item": "Jurisdiction and Governing Law",
                "description": f"NDA governed by laws of {rfp.get('country', 'OM')}. Disputes to be resolved through arbitration in the agreed jurisdiction.",
                "status": "pending",
            },
            {
                "item": "Return/Destroy Obligations",
                "description": "Upon termination or request, all confidential materials must be returned or destroyed, with written confirmation provided within 30 days.",
                "status": "pending",
            },
            {
                "item": "Exceptions to Confidentiality",
                "description": "Standard carve-outs: publicly available information, independently developed information, information received from third parties without restriction.",
                "status": "pending",
            },
            {
                "item": "Non-Solicitation",
                "description": "Neither party shall solicit or hire employees of the other party for the duration of the NDA plus 12 months.",
                "status": "pending",
            },
            {
                "item": "Breach Remedies",
                "description": "Define remedies for breach including injunctive relief and indemnification for damages caused by unauthorized disclosure.",
                "status": "pending",
            },
        ]

        # Update partner NDA status
        await db.update_partner(partner["id"], nda_status="sent")

        logger.info("Created NDA checklist for %s (%d items)", partner_name, len(checklist_items))

        return {
            "partner_id": partner["id"],
            "partner_name": partner_name,
            "rfp_title": rfp["title"],
            "checklist_items": checklist_items,
            "nda_status": "sent",
        }

    @mcp.tool()
    async def track_partner_deliverable(
        partner_name: str, rfp_id: str, item: str, deadline: str
    ) -> dict:
        """Track a deliverable expected from a partner.

        Creates a tracking record for a specific deliverable from a partner,
        linked to the proposal for the given RFP.

        Args:
            partner_name: Name of the partner company
            rfp_id: ID of the parsed RFP
            item: Description of the deliverable (e.g., "Technical specifications for core network")
            deadline: Due date in YYYY-MM-DD format

        Returns:
            Dict with deliverable_id, status, and tracking details
        """
        rfp = await db.get_rfp(rfp_id)
        if not rfp:
            raise ValueError(f"RFP not found: {rfp_id}")

        # Ensure partner exists
        partner = await db.get_partner_by_name(partner_name)
        if not partner:
            partner = await db.upsert_partner(name=partner_name)

        # Find or create proposal
        proposals = await db.get_proposals_for_rfp(rfp_id)
        if isinstance(proposals, list) and proposals:
            proposal_id = proposals[0]["id"]
        elif isinstance(proposals, dict):
            proposal_id = proposals["id"]
        else:
            prop = await db.create_proposal(
                rfp_id=rfp_id,
                proposal_type="technical",
                title=f"Proposal — {rfp['title']}",
            )
            proposal_id = prop["id"]

        # Determine deliverable type from item description
        item_lower = item.lower()
        if any(kw in item_lower for kw in ("price", "pricing", "cost", "quote")):
            deliv_type = "pricing"
        elif any(kw in item_lower for kw in ("cv", "resume", "personnel")):
            deliv_type = "cv"
        elif any(kw in item_lower for kw in ("cert", "certificate", "accreditation")):
            deliv_type = "certification"
        elif any(kw in item_lower for kw in ("reference", "letter")):
            deliv_type = "reference_letter"
        elif any(kw in item_lower for kw in ("technical", "spec", "design", "architecture")):
            deliv_type = "technical_input"
        else:
            deliv_type = "document"

        deliverable = await db.create_deliverable(
            partner_id=partner["id"],
            proposal_id=proposal_id,
            title=item,
            deliverable_type=deliv_type,
            due_date=deadline,
            status="requested",
        )

        logger.info(
            "Tracking deliverable from %s: '%s' (due: %s)",
            partner_name, item, deadline,
        )

        return {
            "deliverable_id": deliverable["id"],
            "partner_name": partner_name,
            "partner_id": partner["id"],
            "item": item,
            "deliverable_type": deliv_type,
            "deadline": deadline,
            "status": "requested",
            "proposal_id": proposal_id,
        }
