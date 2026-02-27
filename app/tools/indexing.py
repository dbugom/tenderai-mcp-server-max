"""Past Proposal Indexing tools — parse, summarize, and search past proposals.

Supports two search modes:
- FTS5: keyword search with BM25 ranking (always available)
- Hybrid: FTS5 + vector similarity via sqlite-vec + Voyage AI embeddings,
  combined with Reciprocal Rank Fusion (enabled when VOYAGE_API_KEY is set)
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP

from app.db.database import Database
from app.services.embeddings import EmbeddingService
from app.services.llm import LLMService
from app.services.parser import ParserService

logger = logging.getLogger(__name__)

# File extensions we can parse
INDEXABLE_EXTENSIONS = {".pdf", ".docx", ".doc", ".xlsx", ".xls", ".md", ".txt"}

# Budget for combined text sent to LLM
MAX_TOTAL_CHARS = 25_000
FINANCIAL_RESERVE_CHARS = 8_000

# Reciprocal Rank Fusion constant (standard value from literature)
RRF_K = 60


def _rrf_combine(
    fts_results: list[dict],
    vec_results: list[dict],
    fts_weight: float = 1.0,
    vec_weight: float = 1.0,
) -> list[dict]:
    """Combine FTS5 and vector search results using Reciprocal Rank Fusion.

    RRF score = sum(weight / (k + rank)) across both result lists.
    Higher score = better match.
    """
    scores: dict[str, float] = {}
    docs: dict[str, dict] = {}

    for rank, doc in enumerate(fts_results):
        doc_id = doc["id"]
        scores[doc_id] = scores.get(doc_id, 0) + fts_weight / (RRF_K + rank + 1)
        docs[doc_id] = doc

    for rank, doc in enumerate(vec_results):
        doc_id = doc["id"]
        scores[doc_id] = scores.get(doc_id, 0) + vec_weight / (RRF_K + rank + 1)
        if doc_id not in docs:
            docs[doc_id] = doc

    # Sort by combined RRF score descending
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [
        {**docs[doc_id], "rrf_score": score}
        for doc_id, score in ranked
    ]


def register_indexing_tools(
    mcp: FastMCP,
    db: Database,
    llm: LLMService,
    parser: ParserService,
    data_dir: Path,
    embeddings: Optional[EmbeddingService] = None,
) -> None:
    """Register past proposal indexing and search tools on the MCP server."""

    past_dir = data_dir / "past_proposals"

    async def _read_file(file_path: Path) -> str:
        """Read a single file, using parser for binary formats."""
        ext = file_path.suffix.lower()
        if ext in (".md", ".txt"):
            return file_path.read_text()
        elif ext in (".pdf", ".docx", ".doc", ".xlsx", ".xls"):
            try:
                parsed = await parser.parse_file(str(file_path))
                return parsed["text"]
            except Exception as e:
                logger.warning("Could not parse %s: %s", file_path, e)
                return ""
        return ""

    @mcp.tool()
    async def index_past_proposal(folder_name: str) -> dict:
        """Parse all files in a past proposal folder, extract structured metadata via LLM, and index for fast search.

        Scans the folder, parses all supported files (PDF, DOCX, XLSX, MD, TXT),
        sends combined content to the LLM for structured extraction, saves a
        human-readable _summary.md file, and upserts the index into the database
        for FTS5 full-text search.

        Args:
            folder_name: Name of the folder inside data/past_proposals/

        Returns:
            Dict with index_id, folder_name, title, client, sector, file_count, and technologies
        """
        folder_path = past_dir / folder_name
        if not folder_path.exists() or not folder_path.is_dir():
            raise ValueError(
                f"Folder not found: {folder_path}. "
                f"Expected a directory inside data/past_proposals/"
            )

        # Collect all parseable files, skipping _-prefixed files
        files = sorted(
            f for f in folder_path.iterdir()
            if f.is_file()
            and f.suffix.lower() in INDEXABLE_EXTENSIONS
            and not f.name.startswith("_")
        )
        if not files:
            raise ValueError(f"No parseable files found in {folder_path}")

        file_list = [f.name for f in files]
        logger.info("Indexing %d files from %s", len(files), folder_name)

        # Parse files, separating financial (XLSX) from others
        financial_texts = []
        other_texts = []
        for f in files:
            content = await _read_file(f)
            if not content:
                continue
            if f.suffix.lower() in (".xlsx", ".xls"):
                financial_texts.append(f"=== {f.name} (Financial) ===\n{content}")
            else:
                other_texts.append(f"=== {f.name} ===\n{content}")

        # Build combined text with financial data prioritized
        financial_combined = "\n\n".join(financial_texts)
        other_combined = "\n\n".join(other_texts)

        # Truncate: reserve space for financial data
        if financial_combined:
            financial_combined = financial_combined[:FINANCIAL_RESERVE_CHARS]
            remaining = MAX_TOTAL_CHARS - len(financial_combined)
            other_combined = other_combined[:max(remaining, 5000)]
        else:
            other_combined = other_combined[:MAX_TOTAL_CHARS]

        combined_text = other_combined
        if financial_combined:
            combined_text += "\n\n--- FINANCIAL DATA ---\n\n" + financial_combined

        # Call LLM for structured extraction
        user_prompt = (
            f"Analyze the following past proposal documents from folder '{folder_name}' "
            f"and extract structured metadata.\n\n"
            f"Files: {', '.join(file_list)}\n\n"
            f"{combined_text}"
        )

        raw_response = await llm.generate_section(
            "proposal_summary", user_prompt, max_tokens=4096
        )

        # Parse JSON response (handle ```json blocks)
        json_text = raw_response.strip()
        if json_text.startswith("```"):
            # Remove opening ```json or ``` and closing ```
            lines = json_text.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            json_text = "\n".join(lines)

        try:
            extracted = json.loads(json_text)
        except json.JSONDecodeError:
            logger.error("LLM returned invalid JSON for %s: %s", folder_name, json_text[:200])
            extracted = {
                "title": folder_name,
                "full_summary": raw_response[:1000],
            }

        # Build _summary.md for human readability
        summary_md = (
            f"# {extracted.get('title', folder_name)}\n\n"
            f"**Client:** {extracted.get('client', 'Unknown')}\n"
            f"**Sector:** {extracted.get('sector', '')}\n"
            f"**Country:** {extracted.get('country', '')}\n"
            f"**Tender Number:** {extracted.get('tender_number', '')}\n\n"
            f"## Technical Summary\n{extracted.get('technical_summary', '')}\n\n"
            f"## Pricing Summary\n{extracted.get('pricing_summary', '')}\n"
            f"**Total Price:** {extracted.get('total_price', 0.0)}\n"
            f"**Margin Info:** {extracted.get('margin_info', '')}\n\n"
            f"## Technologies\n"
            + "\n".join(f"- {t}" for t in extracted.get("technologies", []))
            + f"\n\n## Keywords\n"
            + ", ".join(extracted.get("keywords", []))
            + f"\n\n## Full Summary\n{extracted.get('full_summary', '')}\n"
        )
        summary_path = folder_path / "_summary.md"
        summary_path.write_text(summary_md)
        logger.info("Wrote summary to %s", summary_path)

        # Upsert into database (triggers auto-sync FTS5)
        index_record = await db.upsert_proposal_index(
            folder_name=folder_name,
            tender_number=extracted.get("tender_number", ""),
            title=extracted.get("title", folder_name),
            client=extracted.get("client", ""),
            sector=extracted.get("sector", ""),
            country=extracted.get("country", ""),
            technical_summary=extracted.get("technical_summary", ""),
            pricing_summary=extracted.get("pricing_summary", ""),
            total_price=float(extracted.get("total_price", 0.0)),
            margin_info=extracted.get("margin_info", ""),
            technologies=extracted.get("technologies", []),
            keywords=extracted.get("keywords", []),
            full_summary=extracted.get("full_summary", ""),
            file_count=len(files),
            file_list=file_list,
        )

        logger.info("Indexed proposal '%s' (id=%s)", folder_name, index_record["id"])

        # Generate and store vector embedding if available
        vector_stored = False
        if embeddings and db.vec_enabled:
            try:
                embed_text = (
                    f"{extracted.get('title', '')} "
                    f"{extracted.get('client', '')} "
                    f"{extracted.get('sector', '')} "
                    f"{extracted.get('technical_summary', '')} "
                    f"{' '.join(extracted.get('keywords', []))} "
                    f"{extracted.get('full_summary', '')}"
                )
                vector = await embeddings.embed(embed_text[:8000])
                vector_stored = await db.upsert_proposal_vector(folder_name, vector)
                if vector_stored:
                    logger.info("Stored embedding vector for '%s'", folder_name)
            except Exception as e:
                logger.warning("Could not generate/store embedding for %s: %s", folder_name, e)

        return {
            "index_id": index_record["id"],
            "folder_name": folder_name,
            "title": index_record.get("title", ""),
            "client": index_record.get("client", ""),
            "sector": index_record.get("sector", ""),
            "file_count": len(files),
            "technologies": index_record.get("technologies", []),
            "summary_path": str(summary_path),
            "vector_indexed": vector_stored,
        }

    @mcp.tool()
    async def search_past_proposals(
        query: str, sector: str = "", limit: int = 5, mode: str = "auto"
    ) -> dict:
        """Search indexed past proposals using keyword, semantic, or hybrid search.

        Modes:
        - "auto": Uses hybrid (FTS5 + vector RRF) if embeddings are available, otherwise FTS5-only
        - "keyword": FTS5 only — supports quoted phrases ("core network"), prefix (cisco*), boolean (AND/OR)
        - "semantic": Vector similarity only — finds conceptually similar proposals even without exact keyword matches
        - "hybrid": Combines FTS5 + vector using Reciprocal Rank Fusion for best results

        Args:
            query: Search query text
            sector: Optional sector filter (telecom, it, infrastructure, security, energy, general)
            limit: Maximum results to return (default 5)
            mode: Search mode — "auto", "keyword", "semantic", or "hybrid"

        Returns:
            Dict with matches (ranked list), result_count, and search_mode used
        """
        use_fts = mode in ("auto", "keyword", "hybrid")
        use_vec = mode in ("auto", "semantic", "hybrid")
        has_vec = embeddings is not None and db.vec_enabled

        # Determine actual mode
        if mode == "auto":
            actual_mode = "hybrid" if has_vec else "keyword"
        elif mode in ("semantic", "hybrid") and not has_vec:
            actual_mode = "keyword"
            logger.info("Vector search unavailable, falling back to keyword mode")
        else:
            actual_mode = mode

        fts_results = []
        vec_results = []

        # FTS5 search
        if actual_mode in ("keyword", "hybrid"):
            try:
                fts_results = await db.search_proposal_index(
                    query, sector=sector, limit=limit * 2
                )
            except Exception as e:
                logger.warning("FTS5 search failed: %s", e)

        # Vector search
        if actual_mode in ("semantic", "hybrid") and has_vec:
            try:
                query_vec = await embeddings.embed_query(query)
                vec_results = await db.search_proposal_vector(
                    query_vec, limit=limit * 2
                )
                # Apply sector filter to vector results if specified
                if sector and vec_results:
                    vec_results = [
                        r for r in vec_results
                        if r.get("sector", "").lower() == sector.lower()
                    ]
            except Exception as e:
                logger.warning("Vector search failed: %s", e)

        # Combine results
        if actual_mode == "hybrid" and fts_results and vec_results:
            combined = _rrf_combine(fts_results, vec_results)[:limit]
        elif actual_mode == "semantic" and vec_results:
            combined = vec_results[:limit]
        else:
            combined = fts_results[:limit]

        matches = []
        for r in combined:
            matches.append({
                "index_id": r["id"],
                "folder_name": r["folder_name"],
                "title": r.get("title", ""),
                "client": r.get("client", ""),
                "sector": r.get("sector", ""),
                "country": r.get("country", ""),
                "technical_summary": r.get("technical_summary", ""),
                "pricing_summary": r.get("pricing_summary", ""),
                "total_price": r.get("total_price", 0.0),
                "technologies": r.get("technologies", []),
                "rrf_score": r.get("rrf_score"),
                "distance": r.get("distance"),
                "rank": r.get("rank"),
            })

        return {
            "query": query,
            "sector_filter": sector,
            "search_mode": actual_mode,
            "vector_available": has_vec,
            "result_count": len(matches),
            "matches": matches,
        }

    @mcp.tool()
    async def list_indexed_proposals() -> dict:
        """List all indexed past proposals with aggregate statistics.

        Returns:
            Dict with proposals list, total count, and breakdowns by sector, country, and total value
        """
        rows = await db.list_proposal_indexes()

        proposals = []
        by_sector: dict[str, int] = {}
        by_country: dict[str, int] = {}
        total_value = 0.0

        for r in rows:
            proposals.append({
                "index_id": r["id"],
                "folder_name": r["folder_name"],
                "title": r.get("title", ""),
                "client": r.get("client", ""),
                "sector": r.get("sector", ""),
                "country": r.get("country", ""),
                "total_price": r.get("total_price", 0.0),
                "file_count": r.get("file_count", 0),
                "technologies": r.get("technologies", []),
                "indexed_at": r.get("indexed_at", ""),
            })
            sector = r.get("sector", "unknown")
            by_sector[sector] = by_sector.get(sector, 0) + 1
            country = r.get("country", "unknown")
            by_country[country] = by_country.get(country, 0) + 1
            total_value += r.get("total_price", 0.0)

        return {
            "total_count": len(proposals),
            "by_sector": by_sector,
            "by_country": by_country,
            "total_value": total_value,
            "vector_search_available": embeddings is not None and db.vec_enabled,
            "proposals": proposals,
        }
