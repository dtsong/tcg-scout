"""Auto-generated meta reports for Scout Web via Claude Haiku LLM."""

import hashlib
import json
import logging
import re
from datetime import UTC, datetime
from pathlib import Path

import anthropic
from jinja2 import Environment, FileSystemLoader

from config import REPORT_LLM_MAX_TOKENS, REPORT_LLM_MODEL, REPORT_LLM_TEMPERATURE

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).parent / "templates"


def _load_json(path: Path) -> dict | list | None:
    """Load JSON from path, returning None if file is missing or malformed."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        logger.warning("Could not load %s: %s", path, exc)
        return None


def _slugify(name: str) -> str:
    """Convert a name to a URL-friendly slug."""
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def assemble_report_context(format_slug: str, data_dir: Path) -> dict:
    """
    Read freshly exported JSON files and build a structured context dict.

    Returns a dict with: meta summary (tier list, top archetypes),
    trend movements (surging/declining cards), winning edge highlights,
    matchup spotlight data.
    """
    fmt_dir = data_dir / format_slug

    meta = _load_json(fmt_dir / "meta.json") or {}
    trends = _load_json(fmt_dir / "trends.json") or {}
    winning_edge_raw = _load_json(fmt_dir / "winning-edge.json") or []
    matchup = _load_json(fmt_dir / "matchup.json") or {}

    # Top archetypes from meta (limit to top 10 for prompt size)
    archetypes = meta.get("archetypes", [])
    top_archetypes = archetypes[:10]

    # Surging cards with top archetype context (limit to top 5)
    surging_cards = []
    for card in trends.get("surging", [])[:5]:
        arch_list = card.get("archetypes", [])
        top_arch = max(arch_list, key=lambda a: a.get("delta", 0), default=None)
        surging_cards.append(
            {
                "card_name": card["card_name"],
                "early_pct": round(card.get("early_pct", 0), 1),
                "late_pct": round(card.get("late_pct", 0), 1),
                "delta": round(card.get("delta", 0), 1),
                "top_archetype": top_arch["archetype"] if top_arch else None,
            }
        )

    # Winning edge cards (top 5)
    winning_edge_cards = []
    for card in (winning_edge_raw if isinstance(winning_edge_raw, list) else [])[:5]:
        winning_edge_cards.append(
            {
                "card_name": card["card_name"],
                "field_pct": round(card.get("field_pct", 0), 1),
                "win_pct": round(card.get("win_pct", 0), 1),
                "edge": round(card.get("edge", 0), 1),
            }
        )

    # Matchup spotlight: find the most extreme (highest absolute score) pairings
    matchup_spotlight = []
    arch_names = matchup.get("archetypes", [])
    matrix = matchup.get("matrix", [])
    if arch_names and matrix:
        pairings = []
        for i, row in enumerate(matrix):
            for j, score in enumerate(row):
                if i != j and score is not None:
                    pairings.append((abs(score), i, j, score))
        pairings.sort(reverse=True)
        seen_pairs: set[frozenset] = set()
        for _, i, j, score in pairings[:10]:
            pair_key = frozenset({i, j})
            if pair_key not in seen_pairs:
                seen_pairs.add(pair_key)
                matchup_spotlight.append(
                    {
                        "archetype": arch_names[i],
                        "opponent": arch_names[j],
                        "score": round(score, 1),
                    }
                )
            if len(matchup_spotlight) >= 4:
                break

    date_range = meta.get("date_range", {})
    context = {
        "format_slug": format_slug,
        "format_name": meta.get("format_name", format_slug),
        "tournament_count": meta.get("tournament_count", 0),
        "deck_count": meta.get("deck_count", 0),
        "date_start": date_range.get("start", ""),
        "date_end": date_range.get("end", ""),
        "top_archetypes": top_archetypes,
        "surging_cards": surging_cards,
        "winning_edge_cards": winning_edge_cards,
        "matchup_spotlight": matchup_spotlight,
    }
    return context


def validate_report_facts(report_text: str, context: dict) -> list[str]:
    """
    Validate that numbers and names in report_text match source data.

    Returns a list of validation error strings (empty list = valid).
    """
    errors = []

    # Build sets of valid names from context (used for future name validation)
    valid_cards = {c["card_name"] for c in context.get("surging_cards", [])}
    valid_cards.update(c["card_name"] for c in context.get("winning_edge_cards", []))

    # Check that any percentage figures in the text are within plausible range
    pct_pattern = re.compile(r"(\d+(?:\.\d+)?)\s*%")
    for match in pct_pattern.finditer(report_text):
        val = float(match.group(1))
        if val > 100:
            errors.append(f"Implausible percentage value: {val}%")

    # Check meta_share figures mentioned against actual data
    meta_share_map = {a["archetype"]: a["meta_share"] for a in context.get("top_archetypes", [])}
    for arch, share in meta_share_map.items():
        # If an archetype is mentioned with a specific wrong share, flag it
        pattern = re.compile(re.escape(arch) + r"[^.]*?(\d+(?:\.\d+)?)\s*%\s*meta")
        for match in pattern.finditer(report_text, re.IGNORECASE):
            mentioned_share = float(match.group(1))
            if abs(mentioned_share - share) > 0.5:
                errors.append(
                    f"Meta share mismatch for {arch}: report says {mentioned_share}%, data has {share}%"
                )

    return errors


def generate_report(format_slug: str, data_dir: Path, output_dir: Path) -> Path:
    """
    Generate a narrative meta report for the given format.

    Steps:
      1. Assembles context from exported JSON files
      2. Renders the Jinja2 prompt template
      3. Calls Claude Haiku to generate narrative
      4. Parses and validates the response
      5. Writes report.json and report-thread.json
      6. Uses prompt+data hash caching to skip regeneration if unchanged

    Returns the path to the written report.json.
    """
    out_dir = output_dir / format_slug
    out_dir.mkdir(parents=True, exist_ok=True)

    context = assemble_report_context(format_slug, data_dir)

    # Build prompt from template
    jinja_env = Environment(loader=FileSystemLoader(str(_TEMPLATES_DIR)), autoescape=False)
    template = jinja_env.get_template("meta_report.j2")
    prompt = template.render(**context)

    # Compute hash for cache key
    data_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:12]
    cache_path = out_dir / f".report-cache-{data_hash}.json"
    report_path = out_dir / "report.json"
    thread_path = out_dir / "report-thread.json"

    if cache_path.exists():
        logger.info("Cache hit for format %s (hash %s), skipping LLM call", format_slug, data_hash)
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        report_path.write_text(
            json.dumps(cached["report"], indent=2, ensure_ascii=False), encoding="utf-8"
        )
        thread_path.write_text(
            json.dumps(cached["thread"], indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return report_path

    logger.info("Calling %s for format %s (hash %s)", REPORT_LLM_MODEL, format_slug, data_hash)
    client = anthropic.Anthropic()
    message = client.messages.create(
        model=REPORT_LLM_MODEL,
        max_tokens=REPORT_LLM_MAX_TOKENS,
        temperature=REPORT_LLM_TEMPERATURE,
        messages=[{"role": "user", "content": prompt}],
    )
    raw_text = message.content[0].text.strip()

    # Parse JSON response
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        # Try extracting JSON object from the response
        json_match = re.search(r"\{.*\}", raw_text, re.DOTALL)
        if not json_match:
            raise ValueError(f"LLM response did not contain valid JSON: {raw_text[:200]}")
        parsed = json.loads(json_match.group(0))

    sections = parsed.get("sections", [])
    tweets = parsed.get("tweets", [])

    # Validate facts in each section
    full_content = " ".join(s.get("content", "") for s in sections)
    validation_errors = validate_report_facts(full_content, context)
    if validation_errors:
        for err in validation_errors:
            logger.warning("Report validation warning: %s", err)

    now = datetime.now(UTC).isoformat()

    report_data = {
        "format": format_slug,
        "generated_at": now,
        "data_hash": data_hash,
        "sections": sections,
    }

    thread_data = {
        "format": format_slug,
        "generated_at": now,
        "tweets": tweets,
    }

    report_path.write_text(json.dumps(report_data, indent=2, ensure_ascii=False), encoding="utf-8")
    thread_path.write_text(json.dumps(thread_data, indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info("Wrote %s and %s", report_path, thread_path)

    # Write cache
    cache_data = {"report": report_data, "thread": thread_data}
    cache_path.write_text(json.dumps(cache_data, ensure_ascii=False), encoding="utf-8")

    return report_path
