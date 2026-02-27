"""TenderAI MCP Server — entry point.

Usage:
    python -m app.server          # stdio transport (default)
    TRANSPORT=http python -m app.server  # HTTP transport
"""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from app.config import Settings, load_settings
from app.db.database import Database
from app.services.docwriter import DocWriterService
from app.services.llm import LLMService
from app.services.parser import ParserService

logger = logging.getLogger("tenderai")


def build_server(settings: Settings) -> tuple[FastMCP, Database]:
    """Wire up all dependencies and return the configured MCP server + database."""

    # --- Logging ---
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        stream=sys.stderr,
    )

    # --- Database ---
    db = Database(settings.abs_database_path())

    # --- Services ---
    llm = LLMService(
        api_key=settings.anthropic_api_key,
        model=settings.llm_model,
        max_tokens=settings.llm_max_tokens,
    )
    parser = ParserService(data_dir=settings.abs_data_dir())
    docwriter = DocWriterService(
        output_dir=settings.abs_data_dir() / "generated_proposals",
    )

    # --- MCP Server ---
    mcp = FastMCP(
        "TenderAI",
        instructions=(
            "TenderAI is a tender/proposal management system. Use its tools to parse RFP documents, "
            "write technical and financial proposals, coordinate with partners, and track compliance. "
            "Always start by parsing the RFP with parse_tender_rfp, then use the analysis and "
            "writing tools to build the proposal."
        ),
    )

    # --- Register Tools ---
    from app.tools.document import register_document_tools
    from app.tools.financial import register_financial_tools
    from app.tools.partners import register_partner_tools
    from app.tools.technical import register_technical_tools

    data_dir = settings.abs_data_dir()

    register_document_tools(mcp, db, llm, parser, docwriter, data_dir)
    register_technical_tools(mcp, db, llm, parser, docwriter, data_dir, settings.company_name)
    register_financial_tools(
        mcp, db, llm, parser, docwriter, data_dir,
        settings.default_currency, settings.default_margin_pct,
    )
    register_partner_tools(mcp, db, llm, data_dir)

    # --- Register Resources ---
    from app.resources.knowledge import register_resources
    register_resources(mcp, db, data_dir, parser)

    # --- Register Prompts ---
    from app.prompts.workflows import register_prompts
    register_prompts(mcp, db, llm, data_dir)

    logger.info("TenderAI server built — transport=%s", settings.transport)
    return mcp, db


async def _run(settings: Settings) -> None:
    """Initialize DB and run the server."""
    mcp, db = build_server(settings)

    # Connect database and run schema migration
    await db.connect()

    try:
        if settings.transport == "http":
            logger.info("Starting HTTP transport on %s:%d", settings.host, settings.port)
            await mcp.run_async(
                transport="streamable-http",
                host=settings.host,
                port=settings.port,
            )
        else:
            logger.info("Starting stdio transport")
            await mcp.run_async(transport="stdio")
    finally:
        await db.close()


def main() -> None:
    settings = load_settings()
    asyncio.run(_run(settings))


if __name__ == "__main__":
    main()
