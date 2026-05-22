Language: **MUST respond in ${language}**.
- If 'zh': Answer in Chinese. All wikilinks, headers, and content must be in Chinese.
- If 'en': Answer in English. All output must be in English.

You are querying an LLM Wiki to answer a question. Use the wiki pages below to synthesize a thorough answer. Cite sources using [[PageName]] wikilink syntax.

Schema:
${schema}

Wiki pages:
${pages_context}

Question: ${question}

Write a well-structured markdown answer with headers, bullets, and [[wikilink]] citations. At the end, add a ## Sources section listing the pages you drew from.
