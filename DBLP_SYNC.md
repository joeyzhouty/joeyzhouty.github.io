# DBLP publication sync

The workflow runs on day 1 of each month at 08:00 Singapore time (00:00 UTC; GitHub may delay scheduled jobs). It can also be started through Actions → Sync DBLP last-author publications → Run workflow.

## Eligibility applies to every paper

All homepage entries, including formerly hand-curated papers, must satisfy both rules:

- The actual per-paper published name is exactly **Joey Tianyi Zhou**, and that person is the final listed author. Joey Zhou, Tianyi Zhou and DBLP-disambiguated variants are excluded. A shared DBLP profile is not identity evidence by itself.
- The actual venue is in `data/top_tier_venues.json` (CCF-A or ICORE 2026 A*). Findings, workshops, companion proceedings and preprints do not inherit the parent conference ranking.

The script uses `signatureDblpName`, all author signatures and numeric author ordinals. It cross-checks the complete author count before modifying the page. Missing or inconsistent source data fails the run and leaves the homepage unchanged. It rebuilds the entire publication list, removes ineligible older entries, deduplicates normalized titles and updates the count. Zero eligible papers clears the old list; a missing/empty response never does.

`data/verified_publications.json` contains two source-checked ICML 2026 papers awaiting DBLP proceedings indexing. Each includes the complete author list and public primary-source evidence. These records must pass the same exact-name, last-author and venue checks. Once DBLP contains a proceedings record with that title, the DBLP record takes precedence. This is an indexing supplement, not an eligibility exemption.

## Topic decisions

`data/publication_categories.json` maps normalized paper titles to **Efficient AI**, **Trustworthy AI**, or **Foundation Models & Agents**. It only controls categories; it cannot bypass author or venue eligibility.

New papers with no clear keyword match or a tie are held for the owner's decision. Previously displayed eligible papers retain their category when the new classifier is uncertain. Pending titles appear in the workflow summary and `classification-review` artifact. A pending decision marks the run as needing attention (failed), so GitHub Actions failure notifications can alert the repository owner according to their notification settings. Add the approved category to the JSON and rerun to publish.

```json
{
  "a sample paper title": "Trustworthy AI"
}
```

## Audit and testing

`data/publication-audit.json` records source author lists and decisions for the 2026-10-10 correction (322 previous entries, 39 retained, 283 removed). Subsequent workflow runs upload a fresh audit as an artifact without committing over this initial record. Removed original HTML remains in the initial audit for inspection.

Run `python3 -m unittest discover -s scripts -p 'test_*.py'` to check strict identity, full author order, incomplete responses, child venues, manual entries, supplementary evidence, category review and repeatability. Run `python3 scripts/sync_dblp.py --input complete-dblp-response.json` to reproduce a sync from a saved SPARQL response, or omit `--input` to query DBLP.
