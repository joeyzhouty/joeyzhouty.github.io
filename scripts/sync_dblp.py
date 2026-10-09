#!/usr/bin/env python3
"""Merge last-author publications from Joey Tianyi Zhou's DBLP profile."""

from __future__ import annotations

import html
import json
import re
import sys
import time
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "index.html"
OVERRIDES = ROOT / "data" / "publication_categories.json"
REVIEW = ROOT / "data" / "classification-review.json"
TOP_TIER_VENUES = ROOT / "data" / "top_tier_venues.json"
DBLP_ENDPOINT = "https://sparql.dblp.org/sparql"
DBLP_AUTHOR = "https://dblp.org/pid/123/5110"
START = "<!-- DBLP_AUTO_START -->"
END = "<!-- DBLP_AUTO_END -->"
AUTHOR_NAMES = {"joey tianyi zhou", "joey zhou", "tianyi zhou 0007"}


class TextOnly(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def plain_text(value: str) -> str:
    parser = TextOnly()
    parser.feed(value)
    return html.unescape(" ".join("".join(parser.parts).split()))


def key_title(value: str) -> str:
    value = plain_text(value).replace("↗", "")
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def top_tier_venue_keys(data: dict) -> set[str]:
    return {
        key_venue(value)
        for group in ("ccf_a", "icore_2026_a_star")
        for value in data.get(group, [])
    }


def key_venue(value: str) -> str:
    value = re.sub(r"\s*\([^)]*\)", " ", value)
    value = re.sub(r"\b(?:19|20)\d{2}\b", " ", value)
    return key_title(value)


def classify(title: str, venue: str, overrides: dict) -> tuple[int | None, str | None]:
    override = overrides.get(key_title(title))
    categories = {"efficient ai": 0, "trustworthy ai": 1, "foundation models & agents": 2}
    if isinstance(override, int) and override in (0, 1, 2):
        return override, None
    if isinstance(override, str) and override.casefold() in categories:
        return categories[override.casefold()], None

    text = f"{title} {venue}".casefold()
    scores = {
        0: ("efficient", "efficiency", "compression", "condensation", "distillation", "pruning", "coreset", "data selection", "training-free", "low-rank", "energy-aware"),
        1: ("trustworthy", "robust", "backdoor", "poison", "attack", "adversarial", "bias", "fairness", "explainab", "interpretab", "uncertainty", "privacy", "security", "trusted"),
        2: ("agent", "large language model", "language model", "foundation model", "vision-language", "multimodal", "generative", "reasoning", "transformer"),
    }
    hits = {category: sum(term in text for term in terms) for category, terms in scores.items()}
    highest = max(hits.values())
    if highest == 0:
        return None, "No category keywords matched."
    winners = [category for category, score in hits.items() if score == highest]
    if len(winners) != 1:
        return None, "Keyword scores tied across categories."
    return winners[0], None


def fetch_records():
    query = f'''PREFIX dblp: <https://dblp.org/rdf/schema#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
SELECT ?paper ?title ?year ?venue ?ordinal ?authorName WHERE {{
  ?paper dblp:hasSignature ?lastSig ; dblp:title ?title ; dblp:yearOfPublication ?year .
  ?lastSig rdf:type dblp:AuthorSignature ; dblp:signatureCreator <{DBLP_AUTHOR}> ; dblp:signatureOrdinal ?lastOrdinal .
  FILTER NOT EXISTS {{
    ?paper dblp:hasSignature ?otherSig .
    ?otherSig rdf:type dblp:AuthorSignature ; dblp:signatureOrdinal ?later .
    FILTER(?later > ?lastOrdinal)
  }}
  ?paper dblp:hasSignature ?sig .
  ?sig rdf:type dblp:AuthorSignature ; dblp:signatureCreator ?creator ; dblp:signatureOrdinal ?ordinal .
  FILTER(?ordinal <= ?lastOrdinal)
  ?creator rdfs:label ?authorName .
  OPTIONAL {{ ?paper dblp:publishedInStream ?stream . ?stream dblp:primaryStreamTitle ?venue }}
}}
ORDER BY DESC(?year) ?paper ?ordinal'''
    request = urllib.request.Request(
        DBLP_ENDPOINT,
        data=query.encode("utf-8"),
        headers={
            "Accept": "application/sparql-results+json",
            "Content-Type": "application/sparql-query",
            "User-Agent": "JoeyHomepageDBLPSync/1.0 (https://joeyzhouty.github.io/)",
        },
        method="POST",
    )
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                payload = response.read()
            rows = json.loads(payload).get("results", {}).get("bindings", [])
            if not rows:
                raise RuntimeError("DBLP returned no records; leaving homepage unchanged.")
            return rows
        except (urllib.error.URLError, TimeoutError) as exc:
            if attempt == 3:
                raise RuntimeError(f"Could not fetch DBLP after 4 attempts: {exc}") from exc
            time.sleep(3 * (attempt + 1))


def collect(rows, overrides, existing_titles, existing_auto_categories, existing_auto_titles, top_tier_venues):
    grouped = {}
    for row in rows:
        paper = row.get("paper", {}).get("value", "")
        if not paper:
            continue
        item = grouped.setdefault(paper, {"authors": {}})
        for field in ("title", "year", "venue"):
            if row.get(field, {}).get("value"):
                item[field] = row[field]["value"]
        if row.get("authorName", {}).get("value") and row.get("ordinal", {}).get("value"):
            item["authors"][int(row["ordinal"]["value"])] = row["authorName"]["value"]
    records = []
    seen = set(existing_titles)
    for url, item in grouped.items():
        authors = [item["authors"][number] for number in sorted(item["authors"])]
        title = item.get("title", "")
        year = item.get("year", "")
        venue = item.get("venue", "")
        normalized_title = key_title(title)
        if not title or not authors or authors[-1].casefold().strip() not in AUTHOR_NAMES or normalized_title in seen:
            continue
        seen.add(normalized_title)
        if normalized_title not in existing_auto_titles and key_venue(venue) not in top_tier_venues:
            records.append({
                "title": title, "year": year or "Preprint", "venue": venue,
                "url": url, "authors": authors, "needs_review": True,
                "review_reason": "Venue is not on the CCF-A / ICORE 2026 A* allowlist; held out of the homepage.",
                "review_type": "venue",
            })
            continue
        category, review_reason = classify(title, venue, overrides)
        if review_reason and normalized_title in existing_auto_categories:
            category, review_reason = existing_auto_categories[normalized_title], None
        record = {
            "title": title, "year": year or "Preprint", "venue": venue,
            "url": url, "authors": authors,
            "category": category,
        }
        if review_reason:
            record["review_reason"] = review_reason
            record["choices"] = [
                "Efficient AI", "Trustworthy AI", "Foundation Models & Agents"
            ]
            records.append({**record, "needs_review": True})
        else:
            records.append(record)
    records.sort(key=lambda item: int(item["year"]) if item["year"].isdigit() else 0, reverse=True)
    return records


def render(record):
    esc = lambda value: html.escape(value, quote=True)
    if record["url"]:
        title = f'<a href="{esc(record["url"])}">{esc(record["title"])} <span aria-hidden="true">↗</span></a>'
    else:
        title = esc(record["title"])
    author_text = ", ".join(esc(name) for name in record["authors"][:-1])
    if author_text:
        author_text += ", "
    author_text += f'<strong>{esc(record["authors"][-1])}</strong>'
    venue = f"in {record['venue']} {record['year']}".strip() if record["venue"] else record["year"]
    return (f'<article class="paper" data-category="{record["category"]}" data-dblp="{DBLP_AUTHOR}">'
            f'<div class="paper-year">{esc(record["year"])}</div><div><h3>{title}</h3>'
            f'<p class="authors">{author_text}</p><p class="venue">{esc(venue)}</p></div></article>')


def current_manual_titles(paper_list):
    without_auto = re.sub(
        re.escape(START) + r".*?" + re.escape(END) + r"\s*",
        "", paper_list, flags=re.S,
    )
    return {key_title(match) for match in re.findall(r"<h3\b[^>]*>(.*?)</h3>", without_auto, flags=re.I | re.S)}


def remove_auto_blocks(paper_list):
    return re.sub(
        re.escape(START) + r".*?" + re.escape(END) + r"\s*",
        "", paper_list, flags=re.S,
    )


def existing_auto_categories(paper_list):
    if START not in paper_list or END not in paper_list:
        return {}
    block = paper_list.split(START, 1)[1].split(END, 1)[0]
    result = {}
    for article in re.findall(r'<article\b[^>]*data-category="([012])"[^>]*>(.*?)</article>', block, flags=re.I | re.S):
        category, body = article
        title = re.search(r"<h3\b[^>]*>(.*?)</h3>", body, flags=re.I | re.S)
        if title:
            result[key_title(title.group(1))] = int(category)
    return result


def existing_auto_titles(paper_list):
    return set(existing_auto_categories(paper_list))


def main():
    page = PAGE.read_text(encoding="utf-8")
    if page.count('class="paper-list"') != 1:
        raise RuntimeError("Expected exactly one publication list; leaving homepage unchanged.")
    match = re.search(r'(<div\s+class="paper-list"\s*>)(.*?)(</div>\s*<p\s+id="empty")', page, re.I | re.S)
    if not match:
        raise RuntimeError("Could not locate publication list; leaving homepage unchanged.")
    paper_list = match.group(2)
    overrides = json.loads(OVERRIDES.read_text(encoding="utf-8")) if OVERRIDES.exists() else {}
    venue_data = json.loads(TOP_TIER_VENUES.read_text(encoding="utf-8")) if TOP_TIER_VENUES.exists() else {}
    top_tier_venues = top_tier_venue_keys(venue_data)
    manual_papers = remove_auto_blocks(paper_list)
    records = collect(
        fetch_records(), overrides, current_manual_titles(paper_list),
        existing_auto_categories(paper_list), existing_auto_titles(paper_list), top_tier_venues,
    )
    pending = [record for record in records if record.get("needs_review")]
    published_records = [record for record in records if not record.get("needs_review")]
    REVIEW.parent.mkdir(parents=True, exist_ok=True)
    REVIEW.write_text(json.dumps(pending, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    generated = "\n".join(render(record) for record in published_records)
    replacement = match.group(1) + "\n" + START + "\n" + generated + "\n" + END + "\n" + manual_papers + match.group(3)
    updated = page[:match.start()] + replacement + page[match.end():]
    publication_count = len(re.findall(r'<article\b[^>]*class="paper"', updated))
    updated = re.sub(r'(<p class="result-count"[^>]*>).*?(</p>)', lambda m: f'{m.group(1)}{publication_count} publications{m.group(2)}', updated, count=1)
    if published_records or START not in page:
        PAGE.write_text(updated, encoding="utf-8")
    print(f"DBLP top-tier publications in generated block: {len(published_records)}")
    print(f"Publications awaiting category review: {len(pending)}")
    if pending:
        print("\nUncertain publications:")
        for record in pending:
            print(f'- {record["title"]} ({record["year"]})')


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"DBLP sync failed: {error}", file=sys.stderr)
        raise
