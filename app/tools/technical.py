"""Technical Proposal tools — section writing, full proposal assembly, architecture."""

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

# Maps user-facing section names to LLM prompt template keys
SECTION_TEMPLATE_MAP = {
    "Company Profile": "company_profile",
    "Past Successful Projects": "past_successful_projects",
    "Executive Summary": "executive_summary",
    "Technical Approach": "technical_approach",
    "Solution Architecture": "solution_architecture",
    "Implementation Methodology": "implementation_methodology",
    "Project Timeline": "project_timeline",
    "Team Qualifications": "team_qualifications",
    "Past Experience": "past_experience",
}

# Supported file extensions for past proposals (PDF, DOCX, and text)
PAST_PROPOSAL_EXTENSIONS = {".pdf", ".docx", ".doc", ".xlsx", ".xls", ".md", ".txt"}

DEFAULT_SECTIONS = [
    "Company Profile",
    "Past Successful Projects",
    "Executive Summary",
    "Technical Approach",
    "Solution Architecture",
    "Implementation Methodology",
    "Project Timeline",
    "Team Qualifications",
    "Past Experience",
]


def register_technical_tools(
    mcp: FastMCP,
    db: Database,
    llm: LLMService,
    parser: ParserService,
    docwriter: DocWriterService,
    data_dir: Path,
    company_name: str,
) -> None:
    """Register all technical proposal tools on the MCP server."""

    async def _load_company_profile() -> str:
        """Load company profile from knowledge base if available."""
        profile_dir = data_dir / "knowledge_base" / "company_profile"
        if not profile_dir.exists():
            return f"Company: {company_name}"

        # Check for markdown first, then PDF/DOCX
        md_path = profile_dir / "profile.md"
        if md_path.exists():
            return md_path.read_text()

        # Try PDF/DOCX company profile
        for ext in (".pdf", ".docx", ".doc"):
            for f in profile_dir.iterdir():
                if f.suffix.lower() == ext:
                    try:
                        parsed = await parser.parse_file(str(f))
                        return parsed["text"]
                    except Exception as e:
                        logger.warning("Could not parse company profile %s: %s", f, e)

        return f"Company: {company_name}"

    async def _read_past_proposal_file(file_path: Path) -> str:
        """Read a past proposal file — supports PDF, DOCX, XLSX, and text formats."""
        ext = file_path.suffix.lower()
        if ext in (".md", ".txt"):
            return file_path.read_text()
        elif ext in (".pdf", ".docx", ".doc", ".xlsx", ".xls"):
            try:
                parsed = await parser.parse_file(str(file_path))
                return parsed["text"]
            except Exception as e:
                logger.warning("Could not parse past proposal file %s: %s", file_path, e)
                return ""
        return ""

    async def _load_context_docs(rfp_id: str, section_name: str) -> list[str]:
        """Load relevant context documents for grounding.

        Supports PDF, DOCX, XLSX, and text past proposals as reference material.
        """
        docs = []

        # Company profile
        profile = await _load_company_profile()
        docs.append(f"Company Profile:\n{profile}")

        # RFP data
        rfp = await db.get_rfp(rfp_id)
        if rfp:
            rfp_context = (
                f"RFP Title: {rfp['title']}\n"
                f"Client: {rfp['client']}\n"
                f"Sector: {rfp['sector']}\n"
                f"Country: {rfp['country']}\n"
            )
            if rfp.get("requirements"):
                rfp_context += f"\nRequirements:\n" + "\n".join(
                    f"- {r}" if isinstance(r, str) else f"- {r.get('requirement', str(r))}"
                    for r in rfp["requirements"]
                )
            docs.append(rfp_context)

        # Check for relevant templates
        template_path = data_dir / "knowledge_base" / "templates" / f"{section_name.lower().replace(' ', '_')}.md"
        if template_path.exists():
            docs.append(f"Template for {section_name}:\n{template_path.read_text()}")

        # Check for relevant past proposals (PDF, DOCX, XLSX, MD, TXT)
        past_dir = data_dir / "past_proposals"
        section_key = section_name.lower().replace(" ", "_")
        if past_dir.exists():
            for proposal_dir in sorted(past_dir.iterdir()):
                if proposal_dir.is_dir():
                    # First: look for a file matching this section name
                    matched = False
                    for f in sorted(proposal_dir.iterdir()):
                        if f.suffix.lower() in PAST_PROPOSAL_EXTENSIONS and section_key in f.name.lower():
                            content = await _read_past_proposal_file(f)
                            if content:
                                docs.append(f"Past proposal reference ({proposal_dir.name}/{f.name}):\n{content[:3000]}")
                                matched = True
                                break

                    # If no section-specific match, use full proposal files as general context
                    # (only for Company Profile and Past Successful Projects sections
                    # which benefit from seeing the whole prior submission)
                    if not matched and section_key in ("company_profile", "past_successful_projects"):
                        for f in sorted(proposal_dir.iterdir()):
                            if f.suffix.lower() in PAST_PROPOSAL_EXTENSIONS:
                                content = await _read_past_proposal_file(f)
                                if content:
                                    docs.append(f"Past submission ({proposal_dir.name}/{f.name}):\n{content[:4000]}")
                                    break  # One file per past proposal directory

        return docs

    @mcp.tool()
    async def write_technical_section(
        section_name: str, rfp_id: str, context: str = ""
    ) -> dict:
        """Write a single section of a technical proposal grounded by RFP requirements and company knowledge.

        Generates formal proposal narrative for the specified section using the RFP data,
        company profile, templates, and past proposals as context.

        Args:
            section_name: Name of the section (e.g., "Executive Summary", "Technical Approach")
            rfp_id: ID of the parsed RFP
            context: Additional context or instructions for this section

        Returns:
            Dict with section_name, content, and word_count
        """
        rfp = await db.get_rfp(rfp_id)
        if not rfp:
            raise ValueError(f"RFP not found: {rfp_id}")

        # Load grounding context
        context_docs = await _load_context_docs(rfp_id, section_name)

        # Build section-specific prompt
        template_key = SECTION_TEMPLATE_MAP.get(section_name, "general")
        user_prompt = (
            f"Write the '{section_name}' section for a technical proposal.\n\n"
            f"Tender: {rfp['title']}\n"
            f"Client: {rfp['client']}\n"
            f"Sector: {rfp['sector']}\n"
        )
        if context:
            user_prompt += f"\nAdditional context: {context}\n"
        user_prompt += (
            f"\nWrite 500-1000 words of formal proposal content. "
            f"Do not include the section heading itself — just the body text."
        )

        content = await llm.generate_section(
            template_key, user_prompt, context_docs
        )

        # Store in proposal
        proposals = await db.get_proposals_for_rfp(rfp_id, "technical")
        if isinstance(proposals, dict):
            proposal = proposals
        elif isinstance(proposals, list) and proposals:
            proposal = proposals[0]
        else:
            proposal = await db.create_proposal(
                rfp_id=rfp_id,
                proposal_type="technical",
                title=f"Technical Proposal — {rfp['title']}",
            )

        # Update sections
        sections = proposal.get("sections", [])
        section_id = section_name.lower().replace(" ", "_")

        # Replace existing or append
        updated = False
        for i, sec in enumerate(sections):
            if sec.get("section_id") == section_id:
                sections[i] = {
                    "section_id": section_id,
                    "title": section_name,
                    "content": content.strip(),
                    "order": i,
                }
                updated = True
                break
        if not updated:
            sections.append({
                "section_id": section_id,
                "title": section_name,
                "content": content.strip(),
                "order": len(sections),
            })

        await db.update_proposal(proposal["id"], sections=sections)

        word_count = len(content.split())
        logger.info("Wrote section '%s' for RFP %s (%d words)", section_name, rfp_id, word_count)

        return {
            "section_name": section_name,
            "content": content.strip(),
            "word_count": word_count,
            "proposal_id": proposal["id"],
        }

    @mcp.tool()
    async def build_full_technical_proposal(
        rfp_id: str, sections: list[str] | None = None
    ) -> str:
        """Build a complete technical proposal DOCX with all sections.

        Generates each section using AI, then assembles them into a professionally
        formatted DOCX document with cover page, table of contents, and consistent styling.

        Args:
            rfp_id: ID of the parsed RFP
            sections: Optional list of section names. Defaults to standard 7-section structure.

        Returns:
            File path to the generated DOCX document
        """
        rfp = await db.get_rfp(rfp_id)
        if not rfp:
            raise ValueError(f"RFP not found: {rfp_id}")

        section_list = sections or DEFAULT_SECTIONS

        # Generate each section
        doc_sections = []
        for section_name in section_list:
            logger.info("Generating section: %s", section_name)
            result = await write_technical_section(
                section_name=section_name,
                rfp_id=rfp_id,
            )
            doc_sections.append({
                "title": section_name,
                "content": result["content"],
            })

        # Assemble DOCX
        metadata = {
            "client": rfp["client"],
            "company": company_name,
            "rfp_number": rfp.get("rfp_number", ""),
            "rfp_id": rfp_id,
        }
        output_path = docwriter.create_technical_proposal(
            title=f"Technical Proposal — {rfp['title']}",
            sections=doc_sections,
            metadata=metadata,
        )

        # Update proposal record with output path
        proposals = await db.get_proposals_for_rfp(rfp_id, "technical")
        if isinstance(proposals, dict):
            await db.update_proposal(proposals["id"], output_path=output_path, status="review")
        elif isinstance(proposals, list) and proposals:
            await db.update_proposal(proposals[0]["id"], output_path=output_path, status="review")

        logger.info("Built full technical proposal: %s", output_path)
        return output_path

    @mcp.tool()
    async def generate_architecture_description(
        topology_type: str,
        components: list[str],
        rfp_id: str = "",
    ) -> str:
        """Generate a formal architecture description narrative.

        Creates a detailed technical architecture description covering topology,
        components, interconnections, redundancy, and security considerations.

        Args:
            topology_type: Type of architecture (e.g., "hub-and-spoke", "mesh", "three-tier", "microservices")
            components: List of technology components (e.g., ["Cisco ISR 4451", "Palo Alto PA-5200", "F5 BIG-IP"])
            rfp_id: Optional RFP ID for additional context

        Returns:
            Markdown text with the architecture description
        """
        context_docs = []
        if rfp_id:
            rfp = await db.get_rfp(rfp_id)
            if rfp:
                context_docs.append(
                    f"RFP: {rfp['title']}\nClient: {rfp['client']}\n"
                    f"Requirements: {json.dumps(rfp.get('requirements', []))}"
                )

        profile = await _load_company_profile()
        context_docs.append(profile)

        user_prompt = (
            f"Write a formal architecture description for a {topology_type} topology.\n\n"
            f"Components:\n" + "\n".join(f"- {c}" for c in components) + "\n\n"
            "Cover:\n"
            "1. Architecture Overview — overall topology and design philosophy\n"
            "2. Component Descriptions — role and function of each component\n"
            "3. Interconnections — how components communicate and integrate\n"
            "4. Redundancy & High Availability — failover and resilience design\n"
            "5. Security Architecture — security layers and controls\n"
            "6. Scalability — how the architecture supports future growth\n\n"
            "Write 800-1200 words in formal proposal language."
        )

        content = await llm.generate_section(
            "architecture_description", user_prompt, context_docs
        )

        logger.info("Generated architecture description: %s topology, %d components", topology_type, len(components))
        return content.strip()

    @mcp.tool()
    async def write_compliance_narrative(
        requirement: str, our_solution: str, rfp_id: str = ""
    ) -> str:
        """Write a formal compliance narrative explaining how our solution meets a specific requirement.

        Args:
            requirement: The tender requirement to address
            our_solution: Brief description of our proposed solution/approach
            rfp_id: Optional RFP ID for additional context

        Returns:
            Formal compliance paragraph suitable for inclusion in a proposal
        """
        context_docs = [await _load_company_profile()]
        if rfp_id:
            rfp = await db.get_rfp(rfp_id)
            if rfp:
                context_docs.append(f"RFP: {rfp['title']}\nClient: {rfp['client']}")

        user_prompt = (
            f"Requirement: {requirement}\n\n"
            f"Our Solution: {our_solution}\n\n"
            "Write a formal compliance response (3-5 sentences) explaining how our solution "
            "fully addresses this requirement. Use language like 'The proposed solution...', "
            "'Our approach ensures...', etc. Reference specific capabilities where relevant."
        )

        content = await llm.generate_section(
            "compliance_narrative", user_prompt, context_docs
        )

        logger.info("Generated compliance narrative for requirement: %.60s...", requirement)
        return content.strip()
