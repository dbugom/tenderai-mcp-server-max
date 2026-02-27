"""Document Intelligence tools — RFP parsing, compliance matrix, deadlines, validation."""

from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from app.db.database import Database
from app.services.docwriter import DocWriterService
from app.services.llm import LLMService
from app.services.parser import ParserService

logger = logging.getLogger(__name__)


def register_document_tools(
    mcp: FastMCP,
    db: Database,
    llm: LLMService,
    parser: ParserService,
    docwriter: DocWriterService,
    data_dir: Path,
) -> None:
    """Register all document intelligence tools on the MCP server."""

    @mcp.tool()
    async def parse_tender_rfp(file_path: str) -> dict:
        """Parse a tender RFP document (PDF or DOCX) and extract structured data.

        Extracts the title, client, deadline, sections, requirements, and evaluation
        criteria using AI-powered analysis. Stores the parsed RFP in the database.

        Args:
            file_path: Path to the RFP document (PDF or DOCX)

        Returns:
            Dict with rfp_id, title, client, deadline, sections, requirements,
            and evaluation_criteria
        """
        # Parse the document
        parsed = await parser.parse_file(file_path)
        text = parsed["text"]

        # Use LLM to structure the extracted text
        structure_prompt = (
            "Analyze this tender/RFP document and extract the following as JSON:\n"
            "{\n"
            '  "title": "full tender title",\n'
            '  "client": "issuing organization name",\n'
            '  "rfp_number": "reference number if found, or null",\n'
            '  "sector": "telecom|it|infrastructure|security|general",\n'
            '  "deadline": "submission deadline in YYYY-MM-DD format if found, or null",\n'
            '  "submission_method": "how to submit (email, portal, physical) if stated, or null",\n'
            '  "sections": {"section_name": "brief description of what this section covers"},\n'
            '  "requirements": ["list of specific technical and functional requirements"],\n'
            '  "evaluation_criteria": [{"criterion": "name", "weight": "percentage or description"}]\n'
            "}\n\n"
            "Return ONLY valid JSON, no markdown formatting.\n\n"
            f"Document text:\n{text[:15000]}"
        )

        result_text = await llm.generate(
            system_prompt="You are an expert at analyzing government and enterprise tender documents. Extract structured data accurately.",
            user_prompt=structure_prompt,
        )

        # Parse LLM response as JSON
        try:
            structured = json.loads(result_text.strip())
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code block
            if "```json" in result_text:
                json_str = result_text.split("```json")[1].split("```")[0].strip()
                structured = json.loads(json_str)
            elif "```" in result_text:
                json_str = result_text.split("```")[1].split("```")[0].strip()
                structured = json.loads(json_str)
            else:
                raise ValueError(f"LLM did not return valid JSON: {result_text[:200]}")

        # Copy file to rfp_documents directory
        rfp_docs_dir = data_dir / "rfp_documents"
        rfp_docs_dir.mkdir(parents=True, exist_ok=True)
        dest_path = rfp_docs_dir / Path(file_path).name
        if Path(file_path).resolve() != dest_path.resolve():
            shutil.copy2(file_path, dest_path)

        # Store in database
        rfp = await db.create_rfp(
            title=structured.get("title", "Untitled RFP"),
            client=structured.get("client", "Unknown"),
            sector=structured.get("sector", "telecom"),
            rfp_number=structured.get("rfp_number"),
            deadline=structured.get("deadline"),
            submission_method=structured.get("submission_method"),
            status="analyzing",
            file_path=str(dest_path),
            parsed_sections=structured.get("sections", {}),
            requirements=structured.get("requirements", []),
            evaluation_criteria=structured.get("evaluation_criteria", []),
        )

        logger.info("Parsed RFP: %s (id=%s)", rfp["title"], rfp["id"])

        return {
            "rfp_id": rfp["id"],
            "title": rfp["title"],
            "client": rfp["client"],
            "deadline": rfp["deadline"],
            "sections": rfp["parsed_sections"],
            "requirements": rfp["requirements"],
            "evaluation_criteria": rfp["evaluation_criteria"],
        }

    @mcp.tool()
    async def generate_compliance_matrix(
        rfp_id: str, output_format: str = "docx"
    ) -> str:
        """Generate a compliance matrix for an RFP showing how each requirement is addressed.

        For each requirement in the RFP, generates a compliance status and narrative
        response explaining how the proposed solution meets the requirement.

        Args:
            rfp_id: ID of the parsed RFP
            output_format: Output format — "docx" (default) or "json"

        Returns:
            File path to the generated compliance matrix document, or JSON string
        """
        rfp = await db.get_rfp(rfp_id)
        if not rfp:
            raise ValueError(f"RFP not found: {rfp_id}")

        requirements = rfp["requirements"]
        if not requirements:
            raise ValueError(f"No requirements found for RFP {rfp_id}. Parse the RFP first.")

        # Generate compliance responses via LLM
        responses = []
        for req in requirements:
            req_text = req if isinstance(req, str) else req.get("requirement", str(req))
            narrative = await llm.generate_section(
                "compliance_narrative",
                f"Requirement: {req_text}\n\n"
                f"RFP Title: {rfp['title']}\n"
                f"Client: {rfp['client']}\n\n"
                "Write a formal compliance response (2-3 sentences) explaining how our solution meets this requirement.",
            )
            responses.append({
                "requirement": req_text,
                "status": "Compliant",
                "narrative": narrative.strip(),
            })

        if output_format == "json":
            return json.dumps(responses, indent=2)

        # Generate DOCX
        req_dicts = [{"requirement": r if isinstance(r, str) else r.get("requirement", str(r))} for r in requirements]
        output_path = docwriter.create_compliance_matrix(req_dicts, responses)

        logger.info("Generated compliance matrix: %s", output_path)
        return output_path

    @mcp.tool()
    async def check_submission_deadline(rfp_id: str) -> dict:
        """Check the submission deadline for an RFP and calculate time remaining.

        Returns the deadline date, days remaining, urgency status, and recommended
        milestone dates for proposal preparation.

        Args:
            rfp_id: ID of the parsed RFP

        Returns:
            Dict with deadline, days_remaining, status, and milestones
        """
        rfp = await db.get_rfp(rfp_id)
        if not rfp:
            raise ValueError(f"RFP not found: {rfp_id}")

        deadline_str = rfp.get("deadline")
        if not deadline_str:
            return {
                "deadline": None,
                "days_remaining": None,
                "status": "unknown",
                "message": "No deadline set for this RFP.",
                "milestones": [],
            }

        try:
            deadline = datetime.strptime(deadline_str, "%Y-%m-%d")
        except ValueError:
            return {
                "deadline": deadline_str,
                "days_remaining": None,
                "status": "unparseable",
                "message": f"Could not parse deadline format: {deadline_str}",
                "milestones": [],
            }

        now = datetime.now()
        days_remaining = (deadline - now).days

        if days_remaining < 0:
            status = "overdue"
        elif days_remaining <= 1:
            status = "critical"
        elif days_remaining <= 3:
            status = "urgent"
        elif days_remaining <= 7:
            status = "warning"
        elif days_remaining <= 14:
            status = "attention"
        else:
            status = "on_track"

        # Calculate milestone dates
        milestones = []
        milestone_defs = [
            (14, "Start proposal drafting"),
            (10, "Complete technical approach"),
            (7, "Internal review deadline"),
            (5, "Partner inputs due"),
            (3, "Final review and formatting"),
            (1, "Submission preparation"),
            (0, "Submission deadline"),
        ]
        for days_before, label in milestone_defs:
            m_date = deadline - timedelta(days=days_before)
            is_past = m_date < now
            milestones.append({
                "date": m_date.strftime("%Y-%m-%d"),
                "label": label,
                "days_before_deadline": days_before,
                "completed": is_past,
            })

        return {
            "rfp_title": rfp["title"],
            "deadline": deadline_str,
            "days_remaining": days_remaining,
            "status": status,
            "milestones": milestones,
        }

    @mcp.tool()
    async def validate_document_completeness(rfp_id: str) -> dict:
        """Validate that a proposal has all required sections and documents.

        Checks the RFP requirements against existing proposal sections and identifies
        any gaps or missing mandatory components.

        Args:
            rfp_id: ID of the parsed RFP

        Returns:
            Dict with complete (bool), missing_sections, warnings, and section_status
        """
        rfp = await db.get_rfp(rfp_id)
        if not rfp:
            raise ValueError(f"RFP not found: {rfp_id}")

        proposals = await db.get_proposals_for_rfp(rfp_id)

        # Standard mandatory sections for government tenders
        mandatory_sections = [
            "Executive Summary",
            "Technical Approach",
            "Solution Architecture",
            "Implementation Methodology",
            "Project Timeline",
            "Team Qualifications",
            "Past Experience",
        ]

        # Check what sections exist in proposals
        existing_sections = set()
        if proposals:
            if isinstance(proposals, list):
                for prop in proposals:
                    for sec in prop.get("sections", []):
                        existing_sections.add(sec.get("title", "").lower())
            elif isinstance(proposals, dict):
                for sec in proposals.get("sections", []):
                    existing_sections.add(sec.get("title", "").lower())

        section_status = []
        missing = []
        for section in mandatory_sections:
            found = section.lower() in existing_sections
            section_status.append({"section": section, "present": found})
            if not found:
                missing.append(section)

        # Warnings
        warnings = []
        if not rfp.get("deadline"):
            warnings.append("No submission deadline set — risk of missing submission window.")
        if not rfp.get("requirements"):
            warnings.append("No requirements extracted from RFP — compliance matrix will be empty.")
        if not proposals:
            warnings.append("No proposal documents created yet.")

        complete = len(missing) == 0 and not any("No proposal" in w for w in warnings)

        return {
            "rfp_title": rfp["title"],
            "complete": complete,
            "missing_sections": missing,
            "section_status": section_status,
            "warnings": warnings,
            "total_sections": len(mandatory_sections),
            "completed_sections": len(mandatory_sections) - len(missing),
        }
