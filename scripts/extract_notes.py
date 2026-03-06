#!/usr/bin/env python3
"""Extract structured notes from PDF text chunks using an LLM.

Each note carries a verbatim source quote for traceability.
Uses Claude Haiku for cost efficiency (~$0.01 per manual).
"""

import json
import os

import anthropic

# Keep in sync with schema/pir.v1.json notes.topic enum
VALID_TOPICS = [
    "power_consumption", "temperature_control", "shelving", "installation",
    "components", "door_configuration", "glass", "noise", "warranty",
    "capacity", "location_suitability", "maintenance", "operation",
    "troubleshooting", "safety", "cleaning", "unpacking", "recycling",
]

EXTRACTION_PROMPT = """You are extracting factual claims from a product manual for the {brand} {sku} ({name}).

RULES:
1. Extract ONLY facts that are explicitly stated in the text. Never infer or add knowledge.
2. Each fact MUST include a verbatim quote from the source text that supports it.
3. The quote must be copied exactly — do not paraphrase or shorten it.
4. Assign each fact to exactly one topic from this list: {topics}
5. Write the "text" field as a concise factual statement. No marketing language. Expert voice.
6. If the manual covers multiple models, only extract facts that apply to the {sku} or its base model family.
7. Skip trivial or obvious statements (e.g. "read the manual before use").
8. Focus on information a customer or installer would need AFTER purchasing the product.

OUTPUT FORMAT — respond with ONLY a JSON array:
[
  {{
    "topic": "installation",
    "text": "Concise factual statement",
    "source_quote": "Exact verbatim quote from the manual",
    "source_page": 5
  }}
]

If no relevant facts are found, return an empty array: []

SOURCE TEXT (with page numbers):
{chunks}
"""

# Rough threshold: ~150K chars ≈ 37K tokens, well within Haiku's 200K context
MAX_CHARS_PER_BATCH = 150_000


def extract_notes(chunks: list[dict], record: dict) -> list[dict]:
    """Extract structured notes from text chunks using Claude Haiku."""
    client = anthropic.Anthropic()

    chunks_text = "\n\n".join(
        f"--- PAGE {c['page']} ---\n{c['text']}" for c in chunks
    )

    # Batch if content exceeds context threshold
    if len(chunks_text) > MAX_CHARS_PER_BATCH:
        return _extract_batched(client, chunks, record)

    return _extract_single(client, chunks_text, record)


def _extract_single(client, chunks_text: str, record: dict) -> list[dict]:
    """Single-pass extraction for manuals that fit in one context window."""
    prompt = EXTRACTION_PROMPT.format(
        brand=record.get("brand", "Unknown"),
        sku=record.get("sku", "Unknown"),
        name=record.get("name", "Unknown"),
        topics=", ".join(VALID_TOPICS),
        chunks=chunks_text,
    )

    try:
        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.APIError as e:
        print(f"  ERROR: Anthropic API call failed: {e}")
        return []

    response_text = message.content[0].text.strip()

    # Parse JSON from response — handle markdown code blocks
    if response_text.startswith("```"):
        response_text = response_text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    try:
        notes = json.loads(response_text)
    except json.JSONDecodeError as e:
        print(f"  ERROR: Failed to parse LLM response as JSON: {e}")
        print(f"  Response (first 200 chars): {response_text[:200]}")
        return []

    return _validate_notes(notes)


def _extract_batched(client, chunks: list[dict], record: dict) -> list[dict]:
    """Batch extraction for large manuals — split into page groups."""
    all_notes = []
    batch = []
    batch_len = 0

    for chunk in chunks:
        chunk_text = f"--- PAGE {chunk['page']} ---\n{chunk['text']}"
        if batch_len + len(chunk_text) > MAX_CHARS_PER_BATCH and batch:
            chunks_text = "\n\n".join(batch)
            all_notes.extend(_extract_single(client, chunks_text, record))
            batch = []
            batch_len = 0
        batch.append(chunk_text)
        batch_len += len(chunk_text)

    if batch:
        chunks_text = "\n\n".join(batch)
        all_notes.extend(_extract_single(client, chunks_text, record))

    return all_notes


def _validate_notes(notes: list) -> list[dict]:
    """Validate and filter extracted notes."""
    validated = []
    for note in notes:
        if not isinstance(note, dict):
            continue
        if not all(k in note for k in ("topic", "text", "source_quote", "source_page")):
            continue
        if note["topic"] not in VALID_TOPICS:
            continue
        validated.append({
            "topic": note["topic"],
            "text": note["text"],
            "source_quote": note["source_quote"],
            "source_page": note["source_page"],
        })
    return validated
