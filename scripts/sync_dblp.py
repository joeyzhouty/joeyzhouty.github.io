#!/usr/bin/env python3
"""Rebuild publications from complete DBLP signatures, using strict eligibility."""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "index.html"
OVERRIDES = ROOT / "data/publication_categories.json"
REVIEW = ROOT / "data/classification-review.json"
AUDIT = ROOT / "data/publication-audit.json"
VERIFIED = ROOT / "data/verified_publications.json"
TOP_TIER_VENUES = ROOT / "data/top_tier_venues.json"
DBLP_ENDPOINT = "https://sparql.dblp.org/sparql"
DBLP_AUTHOR = "https://dblp.org/pid/123/5110"
AUTHOR_NAME = "Joey Tianyi Zhou"
START = "<!-- DBLP_AUTO_START -->"
END = "<!-- DBLP_AUTO_END -->"

class TextOnly(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
    def handle_data(self, data):
        self.parts.append(data)

def plain_text(value):
    parser = TextOnly()
    parser.feed(value)
    return html.unescape(" ".join("".join(parser.parts).split()))

def key_title(value):
    value = unicodedata.normalize("NFKC", plain_text(value)).replace("↗", "")
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()

def key_venue(value):
    value = re.sub(r"\s*\([^)]*\)", " ", value)
    value = re.sub(r"\b(?:19|20)\d{2}\b", " ", value)
    return key_title(value)

def top_tier_venue_keys(data):
    return {key_venue(v) for group in ("ccf_a", "icore_2026_a_star") for v in data.get(group, [])}

# The profile is only a candidate source. Use each paper's signatureDblpName,
# never the creator's canonical label (which merges different published names).
# Fetch ALL signatures: no last-author/ordinal filters in SPARQL.
QUERY = """PREFIX dblp: <https://dblp.org/rdf/schema#>
SELECT DISTINCT ?paper ?title ?year ?venue ?stream ?sig ?ordinal ?authorName ?creator ?creatorCount ?book WHERE {
  { SELECT DISTINCT ?paper WHERE {
      ?paper dblp:hasSignature ?mine .
      ?mine dblp:signatureCreator <https://dblp.org/pid/123/5110> .
  } }
  ?paper dblp:title ?title ; dblp:yearOfPublication ?year ; dblp:hasSignature ?sig .
  ?sig a dblp:AuthorSignature .
  OPTIONAL { ?sig dblp:signatureOrdinal ?ordinal }
  OPTIONAL { ?sig dblp:signatureDblpName ?authorName }
  OPTIONAL { ?sig dblp:signatureCreator ?creator }
  OPTIONAL { ?paper dblp:numberOfCreators ?creatorCount }
  OPTIONAL { ?paper dblp:publishedInBook ?book }
  OPTIONAL { ?paper dblp:publishedInStream ?stream . ?stream dblp:primaryStreamTitle ?venue }
}
ORDER BY ?paper ?ordinal"""

def fetch_records():
    request = urllib.request.Request(DBLP_ENDPOINT, data=QUERY.encode(), headers={
        "Accept": "application/sparql-results+json",
        "Content-Type": "application/sparql-query",
        "User-Agent": "JoeyHomepageDBLPSync/2.0 (https://joeyzhouty.github.io/)",
    }, method="POST")
    for attempt in range(4):
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                rows = json.load(response)["results"]["bindings"]
            if not rows:
                raise RuntimeError("DBLP returned no records; leaving homepage unchanged.")
            return rows
        except (urllib.error.URLError, TimeoutError):
            if attempt == 3:
                raise
            time.sleep(3 * (attempt + 1))


def group_records(rows):
    if not rows:
        raise ValueError("Empty source; leaving homepage unchanged.")
    grouped = {}
    for row in rows:
        v = {k: x["value"] for k, x in row.items()}
        if not all(v.get(k) for k in ("paper", "title", "year", "sig")):
            raise ValueError("Incomplete source metadata; leaving homepage unchanged.")
        r = grouped.setdefault(v["paper"], {"url": v["paper"], "titles": set(), "years": set(), "signatures": {}, "venues": set(), "books": set(), "counts": set()})
        r["titles"].add(v["title"]); r["years"].add(v["year"])
        if v.get("venue"): r["venues"].add(v["venue"])
        if v.get("book"): r["books"].add(v["book"])
        if v.get("creatorCount"): r["counts"].add(int(v["creatorCount"]))
        signature = (v.get("ordinal", ""), v.get("authorName", ""), v.get("creator", ""))
        if v["sig"] in r["signatures"] and r["signatures"][v["sig"]] != signature:
            raise ValueError("Conflicting signature metadata; leaving homepage unchanged.")
        r["signatures"][v["sig"]] = signature
    result = []
    for r in grouped.values():
        sigs = list(r.pop("signatures").values())
        counts = r.pop("counts")
        titles, years = r.pop("titles"), r.pop("years")
        if len(titles) != 1 or len(years) != 1:
            raise ValueError("Conflicting publication metadata; leaving homepage unchanged.")
        r["title"], r["year"] = next(iter(titles)), next(iter(years))
        # Missing names, ordinals, gaps, duplicate ordinals, and truncated responses
        # must never turn an earlier author into an apparent final author.
        ordinals = [int(s[0]) for s in sigs if s[0].isdigit()]
        if (len(ordinals) != len(sigs) or sorted(ordinals) != list(range(1, len(sigs)+1))
                or any(not s[1] for s in sigs) or counts != {len(sigs)}):
            raise ValueError(f"Incomplete author list for {r['url']}; leaving homepage unchanged.")
        sigs.sort(key=lambda s: int(s[0]))
        r["authors"] = [s[1] for s in sigs]
        r["author_ids"] = [s[2] for s in sigs]
        r["venues"], r["books"] = sorted(r["venues"]), sorted(r["books"])
        result.append(r)
    return result


def author_role(r):
    matches = [i for i, name in enumerate(r["authors"]) if name == AUTHOR_NAME and
               (r.get("source") == "verified_primary_sources" or r["author_ids"][i] == DBLP_AUTHOR)]
    if matches == [0]:
        return "first"
    if matches == [len(r["authors"]) - 1]:
        return "last"
    return None


def author_reason(r):
    matches = [i for i, name in enumerate(r["authors"]) if name == AUTHOR_NAME and
               (r.get("source") == "verified_primary_sources" or r["author_ids"][i] == DBLP_AUTHOR)]
    if not matches:
        return "identity: no exact Joey Tianyi Zhou signature linked to the verified profile"
    if not author_role(r):
        return "author_order: Joey Tianyi Zhou is neither the first nor the final author"
    return None


def published_venue(r, allowed):
    if author_role(r) != "first":
        return eligible_venue(r, allowed)
    # First-author articles have no ranking restriction, but must have a formal
    # conference/journal record. CoRR, theses and informal records are excluded.
    if r.get("source") == "verified_primary_sources" or "/rec/conf/" in r["url"]:
        return next(iter(r["books"]), None)
    if "/rec/journals/" in r["url"] and "/rec/journals/corr/" not in r["url"]:
        return next(iter(r["venues"]), None)
    return None


def eligible_venue(r, allowed):
    if "/rec/conf/" in r["url"] or r.get("source") == "verified_primary_sources":
        # A parent ACL/EMNLP/MM stream also contains Findings and workshops.
        # Only match the actual proceedings/book, never inherit its parent rank.
        for book in r["books"]:
            if re.search(r"findings|workshop|companion|demo|short papers|student|tutorial|@", book, re.I):
                continue
            name = re.sub(r"\s*\(\d+\)$", "", book).strip()
            if key_title(name) in allowed:
                return name
            if name == "IJCAI/ECAI" and key_title("IJCAI") in allowed:
                return name
        return None
    if "/rec/journals/corr/" in r["url"] or "/rec/journals/" not in r["url"]:
        return None
    return next((v for v in r["venues"] if key_venue(v) in allowed), None)

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


def display_author(name):
    # Presentation only: eligibility always uses the unmodified DBLP signature.
    return re.sub(r"\s+(?:\(disambiguation\)|[0-9]{4,})$", "", name).strip()


def render(record):
    esc = lambda value: html.escape(value, quote=True)
    if record["url"]:
        title = f'<a href="{esc(record["url"])}">{esc(record["title"])} <span aria-hidden="true">↗</span></a>'
    else:
        title = esc(record["title"])
    author_text = ", ".join(
        f"<strong>{esc(display_author(name))}</strong>" if name == AUTHOR_NAME else esc(display_author(name))
        for name in record["authors"])
    venue = f"in {record['venue']} {record['year']}".strip() if record["venue"] else record["year"]
    return (f'<article class="paper" data-category="{record["category"]}" data-source="{esc(record.get("source", "dblp"))}">'
            f'<div class="paper-year">{esc(record["year"])}</div><div><h3>{title}</h3>'
            f'<p class="authors">{author_text}</p><p class="venue">{esc(venue)}</p></div></article>')



def current_articles(page):
    articles = []
    for raw in re.findall(r'<article\b[^>]*class="paper"[^>]*>.*?</article>', page, re.S):
        title = re.search(r"<h3\b[^>]*>(.*?)</h3>", raw, re.S)
        category = re.search(r'data-category="([012])"', raw)
        if title and category:
            articles.append({"title": plain_text(title[1]).replace("↗", "").strip(),
                             "category": int(category[1]), "html": raw})
    return articles


def verified_records(items, indexed):
    # Supplements bridge DBLP indexing delays, with inspectable primary evidence.
    # Once proceedings appear in DBLP, the complete indexed record takes precedence.
    indexed_titles = {key_title(r["title"]) for r in indexed if "/rec/conf/" in r["url"]}
    records = []
    for item in items:
        if (not all(item.get(k) for k in ("title", "year", "url", "authors", "venue", "sources", "verified_on"))
                or not isinstance(item["authors"], list)
                or any(not isinstance(a, str) or not a.strip() for a in item["authors"])
                or any(not u.startswith("https://") for u in item["sources"])):
            raise ValueError("Invalid verified publication evidence; leaving homepage unchanged.")
        if key_title(item["title"]) not in indexed_titles:
            records.append({**item, "source": "verified_primary_sources", "books": [item["venue"]],
                            "venues": [item["venue"]], "author_ids": [""] * len(item["authors"])})
    return records


def rebuild(page, rows, overrides, venue_data, verified=()):
    match = re.search(r'(<div\s+class="paper-list"\s*>)(.*?)(</div>\s*<p\s+id="empty")', page, re.S)
    if not match or page.count('class="paper-list"') != 1:
        raise ValueError("Expected exactly one publication list; leaving homepage unchanged.")
    old = current_articles(match[2])
    old_categories = {key_title(a["title"]): a["category"] for a in old}
    allowed = top_tier_venue_keys(venue_data)
    if not allowed:
        raise ValueError("Missing venue allowlist; leaving homepage unchanged.")
    records = group_records(rows)
    source_count = len(records)
    records += verified_records(verified, records)
    decisions, candidates, pending = [], [], []
    for r in records:
        reason = author_reason(r)
        venue = published_venue(r, allowed)
        r = {**r, "author_role": author_role(r)}
        if not reason and not venue:
            reason = ("venue: first-author record is not a verified formal conference/journal publication" if author_role(r) == "first" else "venue: last-author publication is not in the CCF-A / CORE A* allowlist (Findings, workshops and preprints excluded)")
        if reason:
            decisions.append({**r, "decision": "excluded", "reason": reason})
            continue
        category, uncertainty = classify(r["title"], venue, overrides)
        if uncertainty and key_title(r["title"]) in old_categories:
            category, uncertainty = old_categories[key_title(r["title"])], None
        r = {**r, "venue": venue, "category": category}
        if uncertainty:
            review = {**r, "needs_review": True, "review_type": "category", "review_reason": uncertainty,
                      "choices": ["Efficient AI", "Trustworthy AI", "Foundation Models & Agents"]}
            pending.append(review)
            decisions.append({**r, "decision": "held_for_review", "reason": uncertainty})
        else:
            candidates.append(r)
            decisions.append({**r, "decision": "eligible"})
    candidates.sort(key=lambda r: (-int(r["year"]), r["title"], r["url"]))
    published, seen = [], set()
    for r in candidates:
        key = key_title(r["title"])
        if key not in seen:
            published.append(r); seen.add(key)
    removed = []
    by_title = {}
    for r in decisions:
        by_title.setdefault(key_title(r["title"]), []).append(r)
    for a in old:
        key = key_title(a["title"])
        if key not in seen:
            matches = by_title.get(key, [])
            removed.append({"title": a["title"], "previous_html": a["html"],
                            "source_records": matches,
                            "reason": "; ".join(sorted({r.get("reason", r["decision"]) for r in matches})) if matches else "unverified: no exact DBLP title match; retained in audit for manual verification"})
    generated = "\n".join(render(r) for r in published)
    replacement = match[1] + "\n" + START + "\n" + generated + "\n" + END + "\n" + match[3]
    updated = page[:match.start()] + replacement + page[match.end():]
    updated = re.sub(r'(<p class="result-count"[^>]*>).*?(</p>)', lambda m: f'{m[1]}{len(published)} publications{m[2]}', updated, count=1)
    audit = {"source": DBLP_ENDPOINT, "author": DBLP_AUTHOR, "required_name": AUTHOR_NAME,
             "policy": "Exact per-publication signature; first-author formal articles at any venue OR final-author CCF-A / CORE A* articles; no CoRR",
             "source_publications": source_count, "verified_supplements": len(records) - source_count, "previous_count": len(old), "published_count": len(published),
             "removed": removed, "published": published, "decisions": decisions}
    return updated, pending, audit


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, help="Previously downloaded complete DBLP SPARQL JSON (for a reproducible audit)")
    args = parser.parse_args()
    rows = json.loads(args.input.read_text())["results"]["bindings"] if args.input else fetch_records()
    page = PAGE.read_text()
    updated, pending, audit = rebuild(page, rows, json.loads(OVERRIDES.read_text()), json.loads(TOP_TIER_VENUES.read_text()), json.loads(VERIFIED.read_text()) if VERIFIED.exists() else [])
    REVIEW.parent.mkdir(parents=True, exist_ok=True)
    REVIEW.write_text(json.dumps(pending, ensure_ascii=False, indent=2) + "\n")
    AUDIT.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n")
    # A valid source with zero eligible results must remove stale entries too.
    PAGE.write_text(updated)
    print(f"Source publications checked: {audit['source_publications']}")
    print(f"Published: {audit['published_count']}; removed/held: {len(audit['removed'])}; category review: {len(pending)}")

if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"DBLP sync failed: {error}", file=sys.stderr)
        raise
