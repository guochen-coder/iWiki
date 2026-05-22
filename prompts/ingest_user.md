Return ONLY a valid JSON object with these fields (no markdown fences, no prose outside the JSON):
{
  "title": "Human-readable title for this source",
  "slug": "use the source filename stem as-is (e.g. '张三' from '张三.md'). Keep Chinese/Japanese/Korean characters. Do NOT transliterate to pinyin/romaji.",
  "source_page": "full markdown content for wiki/sources/<slug>.md. First line MUST be 'title: <Human-readable Title>'. CRITICAL: Aggressively convert key people, products, concepts and projects into [[Wikilinks]] inline in the text. Omitting [[ ]] for known terms is a failure.",
  "index_entry": "- [Title](sources/slug.md) — one-line summary",
  "overview_update": "full updated content for wiki/overview.md, or null if no update needed",
  "entity_pages": [
    {"path": "entities/EntityName.md", "content": "full markdown content"}
  ],
  "concept_pages": [
    {"path": "concepts/ConceptName.md", "content": "full markdown content"}
  ],
  "contradictions": ["describe any contradiction with existing wiki content, or empty list"],
  "log_entry": "## [{today}] ingest | <title>\n\nAdded source. Key claims: ..."
}

New source to ingest (file: ${source_name}):
=== SOURCE START ===
${source_content}
=== SOURCE END ===
