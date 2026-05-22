#!/usr/bin/env python3
"""
Query the LLM Wiki.

Usage:
    python tools/query.py "What are the main themes across all sources?"
    python tools/query.py "How does ConceptA relate to ConceptB?" --save
    python tools/query.py "Summarize everything about EntityName" --save synthesis/my-analysis.md

Flags:
    --save              Save the answer back into the wiki (prompts for filename)
    --save <path>       Save to a specific wiki path
"""
from __future__ import annotations

import sys
import re
import json
import hashlib
import argparse
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from datetime import date

import os

REPO_ROOT = Path(__file__).parent.parent
WIKI_DIR = REPO_ROOT / "wiki"
INDEX_FILE = WIKI_DIR / "index.md"
LOG_FILE = WIKI_DIR / "log.md"
SCHEMA_FILE = REPO_ROOT / "CLAUDE.md"


@dataclass
class QueryResult:
    answer: str
    sources: list[str] = field(default_factory=list)
    tokens_used: int = 0
    pages_matched: int = 0


def read_file(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


from tools.llm_client import get_client
from tools.prompt_loader import load_prompt


def write_file(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"  saved: {path.relative_to(REPO_ROOT)}")


def find_relevant_pages(question: str, index_content: str) -> list[Path]:
    """Find relevant pages using embedding-based semantic search,
    with keyword matching as fallback."""
    relevant = []

    # Primary: embedding-based search
    try:
        from tools.embeddings import get_store
        store = get_store()
        if store.count() > 0:
            results = store.search(question, top_k=15)
            for r in results:
                p = WIKI_DIR / r["path"]
                if p.exists() and p not in relevant:
                    relevant.append(p)
    except Exception:
        pass

    # Fallback: keyword matching (if embedding store is empty or fails)
    if not relevant:
        md_links = re.findall(r'\[([^\]]+)\]\(([^)]+)\)', index_content)
        question_lower = question.lower()
        for title, href in md_links:
            title_lower = title.lower()
            has_cjk = any('\u4e00' <= ch <= '\u9fff' for ch in title)
            if has_cjk:
                matched = any(
                    title_lower[j:j+2] in question_lower
                    for j in range(len(title_lower) - 1)
                    if any('\u4e00' <= c <= '\u9fff' for c in title_lower[j:j+2])
                )
            else:
                matched = any(word in question_lower for word in title_lower.split() if len(word) > 2)
            if matched:
                p = WIKI_DIR / href
                if p.exists() and p not in relevant:
                    relevant.append(p)

    # Graph-based expansion: find neighbors of matched pages
    graph_json = REPO_ROOT / "graph" / "graph.json"
    if graph_json.exists() and relevant:
        try:
            graph_data = json.loads(graph_json.read_text())
            page_ids = {p.relative_to(WIKI_DIR).as_posix().replace('.md', '') for p in relevant}
            neighbors = set()
            for edge in graph_data.get('edges', []):
                if edge.get('confidence', 0) >= 0.7:
                    if edge['from'] in page_ids:
                        neighbors.add(edge['to'])
                    elif edge['to'] in page_ids:
                        neighbors.add(edge['from'])
            for nid in neighbors:
                np = WIKI_DIR / f"{nid}.md"
                if np.exists() and np not in relevant:
                    relevant.append(np)
        except (json.JSONDecodeError, KeyError):
            pass

    # Always include overview
    overview = WIKI_DIR / "overview.md"
    if overview.exists() and overview not in relevant:
        relevant.insert(0, overview)
    return relevant[:15]  # cap to avoid context overflow


def append_log(entry: str):
    existing = read_file(LOG_FILE)
    LOG_FILE.write_text(entry.strip() + "\n\n" + existing, encoding="utf-8")


@lru_cache(maxsize=128)
def _execute_query(q_hash: str, index_hash: str, question: str) -> tuple[str, tuple[str, ...], int, int]:
    """Cached query execution. Returns (answer, sources_tuple, tokens_used, pages_matched)."""
    index_content = read_file(INDEX_FILE)

    relevant_pages = find_relevant_pages(question, index_content)

    if not relevant_pages or len(relevant_pages) <= 1:
        print("  selecting relevant pages via API...")
        prompt = load_prompt("query_select_pages", index_content=index_content, question=question)
        raw = get_client().complete([{"role": "user", "content": prompt}], max_tokens=512, use_fast=True).text
        raw = raw.strip()
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        try:
            paths = json.loads(raw)
            relevant_pages = [WIKI_DIR / p for p in paths if (WIKI_DIR / p).exists()]
        except (json.JSONDecodeError, TypeError):
            pass

    pages_context = ""
    for p in relevant_pages:
        rel = p.relative_to(REPO_ROOT)
        pages_context += f"\n\n### {rel}\n{p.read_text(encoding='utf-8')}"

    if not pages_context:
        pages_context = f"\n\n### wiki/index.md\n{index_content}"

    schema = read_file(SCHEMA_FILE)

    print(f"  synthesizing answer from {len(relevant_pages)} pages...")
    language = os.environ.get("IWIKI_LANGUAGE", "zh")
    prompt = load_prompt("query_synthesis", schema=schema, pages_context=pages_context, question=question, language=language)
    response = get_client().complete([{"role": "user", "content": prompt}], max_tokens=4096)
    answer = response.text
    usage = response.usage

    sources = tuple(str(p.relative_to(WIKI_DIR)) for p in relevant_pages)
    total_tokens = (usage.prompt_tokens + usage.completion_tokens) if usage else 0
    return answer, sources, total_tokens, len(relevant_pages)


def query(question: str, save_path: str | None = None) -> QueryResult:
    today = date.today().isoformat()

    index_content = read_file(INDEX_FILE)
    if not index_content:
        raise RuntimeError("Wiki is empty. Ingest some sources first with: python tools/ingest.py <source>")

    index_hash = hashlib.sha256(index_content.encode()).hexdigest()[:16]
    q_hash = hashlib.sha256(question.encode()).hexdigest()

    answer, sources, total_tokens, pages_matched = _execute_query(q_hash, index_hash, question)
    sources_list = list(sources)

    print("\n" + "=" * 60)
    print(answer)
    print("=" * 60)

    # Optionally save answer (not cached — side effects)
    if save_path is not None:
        if save_path == "":
            slug = input("\nSave as (slug, e.g. 'my-analysis'): ").strip()
            if not slug:
                print("Skipping save.")
                return QueryResult(answer=answer, sources=sources_list, tokens_used=total_tokens, pages_matched=pages_matched)
            save_path = f"syntheses/{slug}.md"

        full_save_path = WIKI_DIR / save_path
        frontmatter = f"""---
title: "{question[:80]}"
type: synthesis
tags: []
sources: []
last_updated: {today}
---

"""
        write_file(full_save_path, frontmatter + answer)

        index_content = read_file(INDEX_FILE)
        entry = f"- [{question[:60]}]({save_path}) — synthesis"
        if "## Syntheses" in index_content:
            index_content = index_content.replace("## Syntheses\n", f"## Syntheses\n{entry}\n")
            INDEX_FILE.write_text(index_content, encoding="utf-8")
        print(f"  indexed: {save_path}")

    append_log(f"## [{today}] query | {question[:80]}\n\nSynthesized answer from {pages_matched} pages." +
               (f" Saved to {save_path}." if save_path else ""))

    return QueryResult(answer=answer, sources=sources_list, tokens_used=total_tokens, pages_matched=pages_matched)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Query the LLM Wiki")
    parser.add_argument("question", help="Question to ask the wiki")
    parser.add_argument("--save", nargs="?", const="", default=None,
                        help="Save answer to wiki (optionally specify path)")
    args = parser.parse_args()
    query(args.question, args.save)
