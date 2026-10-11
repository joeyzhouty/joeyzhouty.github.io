# DBLP publication sync

The workflow runs on day 1 of each month at 08:00 Singapore time (00:00 UTC; GitHub may delay scheduled jobs). It can also be started through Actions → Sync all formally published DBLP publications → Run workflow.

## Eligibility applies to every paper

All homepage entries, including formerly hand-curated papers, require the actual per-paper published name **Joey Tianyi Zhou**. Joey Zhou, Tianyi Zhou and DBLP-disambiguated variants are excluded. A shared DBLP profile is not identity evidence by itself.

All author positions are eligible: first, middle, last and single author. There is no CCF/CORE or other venue ranking restriction. Formally published conference and journal records, including Findings, published workshops and editorials, are eligible. CoRR preprints, theses and informal records are excluded. The actual per-publication name and linked profile must both match; unrelated names on a shared author profile remain excluded.

Displayed author order is unchanged, and only Joey Tianyi Zhou is highlighted.

Displayed author names omit DBLP numeric disambiguators and `(disambiguation)` suffixes. These are removed only when rendering; identity and author-order validation always use the original signatures. CoRR preprints from every year are excluded.

The script uses `signatureDblpName`, all author signatures and numeric author ordinals. It cross-checks the complete author count before modifying the page. Missing or inconsistent source data fails the run and leaves the homepage unchanged. It rebuilds the entire publication list, removes ineligible older entries, deduplicates normalized titles and updates the count. Zero eligible papers clears the old list; a missing/empty response never does.

`data/verified_publications.json` contains two source-checked ICML 2026 papers awaiting DBLP proceedings indexing. Each includes the complete author list and public primary-source evidence. These records must pass the same exact-name, author-position and publication-status checks. Once DBLP contains a proceedings record with that title, the DBLP record takes precedence. This is an indexing supplement, not an eligibility exemption.

## Topic decisions

`data/publication_categories.json` maps normalized paper titles to **Efficient AI**, **Trustworthy AI**, **Foundation Models & Agents**, or **Others**. Categories never bypass author or formal-publication eligibility. Owner-confirmed choices take priority over automated decisions.

The GitHub workflow checks DBLP on day 1 at 08:00 Singapore time. A companion Codex task in the original conversation runs monthly at 08:30 Singapore time, retrieves fresh source data when necessary, and handles papers whose title classifier was uncertain. It reads publisher/proceedings abstracts, author-hosted papers or the matching manuscript, rather than guessing from titles. It records source links, short reasons, confidence and the classification date in `data/publication_category_evidence.json` and saves decisions in the category JSON before rebuilding and publishing the page. No per-paper owner approval is required under the current policy.

Choose the primary research contribution, not every technique named in the paper:

- **Efficient AI:** computing, training, inference, energy, memory or data/annotation efficiency.
- **Trustworthy AI:** security, privacy, adversarial robustness, bias/fairness, uncertainty, explainability, anomaly detection or forgery detection.
- **Foundation Models & Agents:** general pretrained/foundation models, language or generative models, general multimodal models, agents or agent reasoning.
- **Others:** specialized applications outside the three themes, ambiguous contributions, or papers whose abstract/text could not be read reliably. Record whether this is a topic decision or an evidence-access fallback.

A task-specific Transformer or routine adversarial training does not alone establish a foundation-model or safety contribution. Explicit owner decisions remain unchanged. Already displayed eligible papers keep their existing category when a future title classifier is uncertain. New uncertain items appear in `classification-review.json` temporarily until the monthly agent finishes its pass; this is staging, not a request for manual decisions. Publishing the agent's overrides empties that queue.

```json
{
  "a sample paper title": "Others"
}
```

## Audit and testing

`data/publication-audit.json` records source author lists and decisions for the initial 2026-10-10 last-author-only correction (322 previous entries, 39 retained, 283 removed); it is a historical audit, predating the later first-author expansion. Subsequent workflow runs upload a fresh audit as an artifact without committing over this initial record. Removed original HTML remains in the initial audit for inspection.

Run `python3 -m unittest discover -s scripts -p 'test_*.py'` to check strict identity, full author order, incomplete responses, child venues, manual entries, supplementary evidence, category review and repeatability. Run `python3 scripts/sync_dblp.py --input complete-dblp-response.json` to reproduce a sync from a saved SPARQL response, or omit `--input` to query DBLP.

On 2026-10-11 the all-author audit identified 231 formally published records. The initial 124 pending entries are now processed using 22 explicit owner selections and 102 agent abstract/topic decisions. The complete decision evidence is in `data/publication_category_evidence.json`. All 231 entries are displayed: 72 Efficient AI, 58 Trustworthy AI, 44 Foundation Models & Agents, and 57 Others. Of the 102 agent-reviewed entries, 11 were conservatively assigned to Others because a reliable abstract/text could not be retrieved. The workflow commits both the homepage and the current review file, then explicitly requests a GitHub Pages rebuild; each run also uploads a fresh audit artifact. `data/top_tier_venues.json` is historical and no longer used by the sync.
