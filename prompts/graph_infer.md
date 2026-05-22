Analyze this wiki page and identify implicit semantic relationships to other pages in the wiki.

Source page: ${src}
Content:
${content}

All available pages:
${node_list}

Already-extracted edges from this page:
${existing_edge_summary}

Return ONLY a JSON object containing an "edges" array of NEW relationships not already captured by explicit wikilinks. The response must be STRICTLY valid JSON formatted exactly like this:
{
  "edges": [
    {"to": "page-id", "relationship": "one-line description", "confidence": 0.0-1.0, "type": "INFERRED or AMBIGUOUS"}
  ]
}

CRITICAL INSTRUCTION:
YOU MUST RETURN ONLY A RAW JSON STRING BEGINNING WITH { AND ENDING WITH }.
DO NOT OUTPUT BULLET POINTS. DO NOT OUTPUT MARKDOWN LISTS.
ANY CONVERSATIONAL PREAMBLE WILL CAUSE A SYSTEM CRASH.

Rules:
- Only include pages from the available list above
- Confidence >= 0.7 → INFERRED, < 0.7 → AMBIGUOUS
- Do not repeat edges already in the extracted list
- Return {"edges": []} if no new relationships found
