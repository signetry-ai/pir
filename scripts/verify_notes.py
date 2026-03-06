#!/usr/bin/env python3
"""Adversarial verification of extracted notes.

Second LLM pass that checks whether each note's text is grounded
in its source quote. Flags anything inferred or fabricated.
"""

import json

import anthropic

VERIFY_PROMPT = """You are a fact-checking auditor. For each note below, determine whether the "text" field is fully grounded in the "source_quote" field.

RULES:
1. The text must be a faithful representation of what the source quote says.
2. If the text adds ANY information not present in the source quote, mark it as ungrounded.
3. If the text contradicts the source quote, mark it as ungrounded.
4. Minor rephrasing for clarity is acceptable IF the meaning is preserved exactly.
5. If the text narrows the scope (e.g. applies a general statement to a specific model), that is acceptable.

For each note, respond with ONLY a JSON array of objects:
[
  {{"index": 0, "verified": true, "reason": "Text accurately reflects source quote."}},
  {{"index": 1, "verified": false, "reason": "Text claims 20-amp circuit but source only mentions earthing."}}
]

NOTES TO VERIFY:
{notes}
"""


def verify_notes(notes: list[dict]) -> list[dict]:
    """Verify each note's text is grounded in its source quote."""
    if not notes:
        return []

    client = anthropic.Anthropic()

    notes_text = json.dumps(
        [{"index": i, "text": n["text"], "source_quote": n["source_quote"]}
         for i, n in enumerate(notes)],
        indent=2,
    )

    message = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2048,
        messages=[{"role": "user", "content": VERIFY_PROMPT.format(notes=notes_text)}],
    )

    response_text = message.content[0].text.strip()
    if response_text.startswith("```"):
        response_text = response_text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    verdicts = json.loads(response_text)

    # Merge verdicts back into notes
    results = []
    for note in notes:
        result = {**note, "verified": False, "reason": "No verdict received"}
        results.append(result)

    for verdict in verdicts:
        idx = verdict.get("index")
        if idx is not None and 0 <= idx < len(results):
            results[idx]["verified"] = verdict.get("verified", False)
            results[idx]["reason"] = verdict.get("reason", "")

    return results
