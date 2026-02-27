"""LLM service — Anthropic SDK wrapper with proposal-specific prompt templates."""

from __future__ import annotations

import logging
from typing import Optional

import anthropic

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt templates keyed by section type
# ---------------------------------------------------------------------------

PROMPT_TEMPLATES: dict[str, str] = {
    "executive_summary": (
        "You are a senior proposal writer for a systems integrator. "
        "Write a compelling Executive Summary for a government/enterprise tender response. "
        "Use formal, confident language. Reference the client by name, restate their objectives, "
        "highlight our key differentiators, and close with a commitment to delivery. "
        "Output in well-structured paragraphs with no markdown headings."
    ),
    "technical_approach": (
        "You are a senior solutions architect writing the Technical Approach section of a tender proposal. "
        "Describe the proposed solution architecture, technology choices, and how they address each stated requirement. "
        "Use formal language. Include subsections for approach overview, key design principles, "
        "and alignment with the client's requirements. Do not use bullet points excessively."
    ),
    "solution_architecture": (
        "You are a senior solutions architect. Write a detailed Solution Architecture section. "
        "Cover the overall topology, component descriptions with roles and responsibilities, "
        "redundancy and high-availability design, security architecture, and integration points. "
        "Use formal proposal language."
    ),
    "implementation_methodology": (
        "You are a project management expert writing the Implementation Methodology section. "
        "Describe the phased approach, key milestones, deliverables per phase, quality gates, "
        "risk mitigation during implementation, and resource allocation strategy. "
        "Reference industry frameworks (PRINCE2, PMBOK, Agile) where appropriate."
    ),
    "project_timeline": (
        "You are a project manager writing the Project Timeline section. "
        "Create a phase-by-phase timeline with duration estimates, dependencies, "
        "key milestones, and acceptance criteria. Present in a structured format."
    ),
    "team_qualifications": (
        "You are an HR/proposal writer describing the Team Qualifications. "
        "Highlight the team structure, key personnel roles, relevant certifications, "
        "years of experience, and how team composition addresses project requirements."
    ),
    "company_profile": (
        "You are a senior proposal writer composing the Company Profile section that opens a tender submission. "
        "Present the company in a formal, authoritative tone: legal name, year of establishment, headquarters, "
        "core business lines, key certifications (ISO, vendor partnerships), number of employees and engineers, "
        "geographic presence, and strategic vision. This section appears on the first pages of the document "
        "so it must make a strong first impression. Write in third person."
    ),
    "past_successful_projects": (
        "You are a senior proposal writer composing the Past Successful Projects section. "
        "This section appears in the opening pages of a tender submission, right after the Company Profile. "
        "For each relevant project describe: project name, client (sector, not necessarily by name unless public), "
        "scope of work, technologies deployed, project value range, duration, outcome and measurable benefits. "
        "Focus on projects most relevant to the current tender. Present in a formal, evidence-based style."
    ),
    "past_experience": (
        "You are a proposal writer presenting Past Experience / Reference Projects. "
        "Describe 3-5 relevant past projects with: client sector, scope, technologies used, "
        "outcomes/benefits delivered, and relevance to the current tender."
    ),
    "compliance_narrative": (
        "You are a compliance specialist writing tender compliance responses. "
        "For each requirement, explain precisely how our proposed solution meets or exceeds it. "
        "Use formal language: 'The proposed solution fully complies with...' "
        "Reference specific product capabilities, certifications, and standards."
    ),
    "architecture_description": (
        "You are a network/systems architect describing a technical architecture. "
        "Provide a detailed narrative covering: topology overview, component roles, "
        "interconnections, redundancy design, security layers, and scalability considerations. "
        "Write formally for a government/enterprise audience."
    ),
    "partner_brief": (
        "You are a business development manager drafting a technical requirements brief for a subcontractor/partner. "
        "Clearly state: project background, scope of work required from the partner, "
        "deliverables expected, timeline, and format requirements for their submission."
    ),
    "tender_analysis": (
        "You are a senior business development analyst evaluating a new tender opportunity. "
        "Provide: executive summary of the RFP, go/no-go recommendation with justification, "
        "risk assessment, recommended partners/subcontractors, estimated effort, "
        "key compliance requirements, and strategic considerations."
    ),
    "general": (
        "You are a professional proposal writer for a technology systems integrator. "
        "Write in formal, confident language appropriate for government and enterprise tender responses."
    ),
}


class LLMService:
    """Wrapper around the Anthropic SDK for proposal-oriented text generation."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-5-20241022", max_tokens: int = 4096):
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self.model = model
        self.max_tokens = max_tokens

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        context_documents: Optional[list[str]] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Generate text using Claude with optional grounding documents.

        Context documents are prepended to the system prompt inside <document> blocks
        so the model can reference them when producing its answer.
        """
        full_system = system_prompt
        if context_documents:
            docs_block = "\n\n".join(
                f"<document>\n{doc}\n</document>" for doc in context_documents
            )
            full_system = (
                f"{system_prompt}\n\n"
                f"Use the following reference documents to ground your response:\n\n{docs_block}"
            )

        logger.debug("LLM request — model=%s, system_len=%d, user_len=%d", self.model, len(full_system), len(user_prompt))

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens or self.max_tokens,
            system=full_system,
            messages=[{"role": "user", "content": user_prompt}],
        )

        text = response.content[0].text
        logger.debug("LLM response — tokens_in=%d, tokens_out=%d", response.usage.input_tokens, response.usage.output_tokens)
        return text

    async def generate_section(
        self,
        section_type: str,
        user_prompt: str,
        context_documents: Optional[list[str]] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Generate proposal content using a named prompt template."""
        template = PROMPT_TEMPLATES.get(section_type, PROMPT_TEMPLATES["general"])
        return await self.generate(template, user_prompt, context_documents, max_tokens)
