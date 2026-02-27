"""Workflow prompts — pre-assembled contexts for common tender workflows."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from app.db.database import Database
from app.services.llm import LLMService

logger = logging.getLogger(__name__)


def register_prompts(mcp: FastMCP, db: Database, llm: LLMService, data_dir: Path) -> None:
    """Register all workflow prompts on the MCP server."""

    async def _load_company_profile() -> str:
        profile_path = data_dir / "knowledge_base" / "company_profile" / "profile.md"
        if profile_path.exists():
            return profile_path.read_text()
        return ""

    async def _summarize_past_proposals() -> str:
        past_dir = data_dir / "past_proposals"
        if not past_dir.exists():
            return "No past proposals available."
        summaries = []
        for d in sorted(past_dir.iterdir()):
            if d.is_dir():
                files = list(d.glob("*.md")) + list(d.glob("*.txt"))
                if files:
                    first_content = files[0].read_text()[:500]
                    summaries.append(f"- {d.name}: {first_content.split(chr(10))[0]}")
        return "\n".join(summaries) if summaries else "No past proposals available."

    # ------------------------------------------------------------------
    # analyze_new_tender
    # ------------------------------------------------------------------

    @mcp.prompt()
    async def analyze_new_tender(rfp_id: str) -> str:
        """Comprehensive analysis of a new tender opportunity.

        Provides: executive summary, go/no-go recommendation, risk assessment,
        recommended partners, estimated effort, and key compliance requirements.

        Args:
            rfp_id: ID of the parsed RFP to analyze
        """
        rfp = await db.get_rfp(rfp_id)
        if not rfp:
            raise ValueError(f"RFP not found: {rfp_id}")

        company_profile = await _load_company_profile()
        past_proposals = await _summarize_past_proposals()

        return (
            f"You are a senior business development analyst evaluating a new tender opportunity.\n\n"
            f"## RFP Information\n"
            f"- **Title**: {rfp['title']}\n"
            f"- **Client**: {rfp['client']}\n"
            f"- **Sector**: {rfp['sector']}\n"
            f"- **Country**: {rfp['country']}\n"
            f"- **RFP Number**: {rfp.get('rfp_number', 'N/A')}\n"
            f"- **Deadline**: {rfp.get('deadline', 'N/A')}\n"
            f"- **Submission Method**: {rfp.get('submission_method', 'N/A')}\n\n"
            f"## Parsed Sections\n{json.dumps(rfp.get('parsed_sections', {}), indent=2)}\n\n"
            f"## Requirements\n" +
            "\n".join(f"- {r}" if isinstance(r, str) else f"- {json.dumps(r)}" for r in rfp.get("requirements", [])) +
            f"\n\n## Evaluation Criteria\n" +
            "\n".join(f"- {json.dumps(c)}" for c in rfp.get("evaluation_criteria", [])) +
            f"\n\n## Company Profile\n{company_profile}\n\n"
            f"## Past Proposals\n{past_proposals}\n\n"
            f"## Your Analysis Should Cover\n"
            f"1. **Executive Summary** — What is this tender about?\n"
            f"2. **Go/No-Go Recommendation** — Should we bid? Why or why not?\n"
            f"3. **Risk Assessment** — Technical, commercial, and compliance risks\n"
            f"4. **Recommended Partners/Subcontractors** — Who should we engage?\n"
            f"5. **Estimated Effort** — Team size, timeline, key resources needed\n"
            f"6. **Key Compliance Requirements** — What must we strictly comply with?\n"
            f"7. **Strategic Considerations** — Competitive landscape, pricing strategy, differentiators\n"
        )

    # ------------------------------------------------------------------
    # write_executive_summary
    # ------------------------------------------------------------------

    @mcp.prompt()
    async def write_executive_summary(rfp_id: str, differentiators: str = "") -> str:
        """Generate a tailored executive summary for a proposal.

        Args:
            rfp_id: ID of the parsed RFP
            differentiators: Optional key differentiators to highlight
        """
        rfp = await db.get_rfp(rfp_id)
        if not rfp:
            raise ValueError(f"RFP not found: {rfp_id}")

        company_profile = await _load_company_profile()

        # Get existing proposal sections if any
        proposals = await db.get_proposals_for_rfp(rfp_id, "technical")
        sections_context = ""
        if isinstance(proposals, list) and proposals:
            sections = proposals[0].get("sections", [])
            sections_context = "\n".join(
                f"### {s.get('title', '')}\n{s.get('content', '')[:300]}..."
                for s in sections
            )
        elif isinstance(proposals, dict):
            sections = proposals.get("sections", [])
            sections_context = "\n".join(
                f"### {s.get('title', '')}\n{s.get('content', '')[:300]}..."
                for s in sections
            )

        diff_text = f"\n## Key Differentiators\n{differentiators}\n" if differentiators else ""

        return (
            f"Write a compelling Executive Summary for this tender response.\n\n"
            f"## RFP Details\n"
            f"- **Title**: {rfp['title']}\n"
            f"- **Client**: {rfp['client']}\n"
            f"- **Sector**: {rfp['sector']}\n\n"
            f"## Requirements Overview\n" +
            "\n".join(f"- {r}" if isinstance(r, str) else f"- {json.dumps(r)}" for r in rfp.get("requirements", [])[:10]) +
            f"\n\n## Company Profile\n{company_profile}\n"
            f"{diff_text}\n"
            f"## Existing Proposal Sections\n{sections_context}\n\n"
            f"## Instructions\n"
            f"- Address {rfp['client']} by name\n"
            f"- Restate their objectives and challenges\n"
            f"- Present our solution and approach briefly\n"
            f"- Highlight 3-4 key differentiators\n"
            f"- Close with a commitment to successful delivery\n"
            f"- 400-600 words, formal tone\n"
        )

    # ------------------------------------------------------------------
    # partner_suitability_check
    # ------------------------------------------------------------------

    @mcp.prompt()
    async def partner_suitability_check(partner_name: str, rfp_id: str) -> str:
        """Evaluate whether a partner/subcontractor is suitable for a specific tender.

        Args:
            partner_name: Name of the partner to evaluate
            rfp_id: ID of the parsed RFP
        """
        rfp = await db.get_rfp(rfp_id)
        if not rfp:
            raise ValueError(f"RFP not found: {rfp_id}")

        partner = await db.get_partner_by_name(partner_name)
        partner_info = ""
        if partner:
            partner_info = (
                f"## Partner Profile\n"
                f"- **Name**: {partner['name']}\n"
                f"- **Country**: {partner.get('country', 'N/A')}\n"
                f"- **Specialization**: {partner.get('specialization', 'N/A')}\n"
                f"- **NDA Status**: {partner.get('nda_status', 'none')}\n"
                f"- **Past Projects**: {json.dumps(partner.get('past_projects', []))}\n"
                f"- **Notes**: {partner.get('notes', '')}\n"
            )
        else:
            partner_info = f"## Partner Profile\nNo existing record for {partner_name}.\n"

        return (
            f"Evaluate whether {partner_name} is a suitable subcontractor/partner for this tender.\n\n"
            f"## RFP Details\n"
            f"- **Title**: {rfp['title']}\n"
            f"- **Client**: {rfp['client']}\n"
            f"- **Sector**: {rfp['sector']}\n"
            f"- **Country**: {rfp['country']}\n\n"
            f"## Requirements\n" +
            "\n".join(f"- {r}" if isinstance(r, str) else f"- {json.dumps(r)}" for r in rfp.get("requirements", [])) +
            f"\n\n{partner_info}\n\n"
            f"## Evaluation Criteria\n"
            f"1. **Technical Fit** — Does the partner have relevant expertise?\n"
            f"2. **Geographic Suitability** — Can they operate in {rfp.get('country', 'the target country')}?\n"
            f"3. **Compliance** — NDA status, certifications, regulatory requirements\n"
            f"4. **Track Record** — Past project relevance and performance\n"
            f"5. **Risk Factors** — Potential issues with this partner\n"
            f"6. **Recommendation** — Suitable / Conditionally Suitable / Not Recommended\n"
        )

    # ------------------------------------------------------------------
    # full_proposal_workflow
    # ------------------------------------------------------------------

    @mcp.prompt()
    async def full_proposal_workflow(rfp_id: str) -> str:
        """End-to-end orchestration instructions for producing a complete proposal.

        Args:
            rfp_id: ID of the parsed RFP
        """
        rfp = await db.get_rfp(rfp_id)
        if not rfp:
            raise ValueError(f"RFP not found: {rfp_id}")

        company_profile = await _load_company_profile()

        return (
            f"You are orchestrating the end-to-end proposal development for:\n\n"
            f"**{rfp['title']}** (Client: {rfp['client']}, Deadline: {rfp.get('deadline', 'TBD')})\n\n"
            f"## Company Profile\n{company_profile}\n\n"
            f"## Step-by-Step Workflow\n\n"
            f"### Phase 1: Intake & Analysis\n"
            f"1. Review the parsed RFP data (already done — RFP ID: {rfp_id})\n"
            f"2. Use `analyze_new_tender` prompt for go/no-go decision\n"
            f"3. Use `check_submission_deadline` to confirm timeline\n\n"
            f"### Phase 2: Partner Coordination\n"
            f"4. Identify required partners/subcontractors\n"
            f"5. Use `create_nda_checklist` for each partner\n"
            f"6. Use `draft_partner_brief` for each partner\n"
            f"7. Use `track_partner_deliverable` for each expected input\n\n"
            f"### Phase 3: Technical Proposal\n"
            f"8. Use `write_technical_section` for each section, or\n"
            f"9. Use `build_full_technical_proposal` to generate all at once\n"
            f"10. Use `generate_architecture_description` for network/system diagrams\n"
            f"11. Use `generate_compliance_matrix` for compliance documentation\n\n"
            f"### Phase 4: Financial Proposal\n"
            f"12. Use `ingest_vendor_quote` for each vendor quote received\n"
            f"13. Use `build_bom` to assemble the Bill of Materials\n"
            f"14. Use `calculate_final_pricing` to apply margins\n"
            f"15. Use `generate_financial_proposal` for the pricing document\n\n"
            f"### Phase 5: Review & Submit\n"
            f"16. Use `validate_document_completeness` to check for gaps\n"
            f"17. Use `write_executive_summary` prompt for the final exec summary\n"
            f"18. Review all generated DOCX documents\n"
            f"19. Package and submit per the RFP instructions\n\n"
            f"## Current RFP Requirements\n" +
            "\n".join(f"- {r}" if isinstance(r, str) else f"- {json.dumps(r)}" for r in rfp.get("requirements", [])) +
            f"\n\n## Notes\n"
            f"- Always check deadline status before starting each phase\n"
            f"- Track all partner deliverables and follow up on overdue items\n"
            f"- Generate compliance matrix early to identify gaps\n"
        )
