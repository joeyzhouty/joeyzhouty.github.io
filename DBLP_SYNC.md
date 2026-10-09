# DBLP publication sync

GitHub Actions queries Joey Tianyi Zhou's DBLP author record (`123/5110`) through DBLP's SPARQL endpoint on the first day of each month at 08:00 Singapore time. Run it manually from the repository's **Actions** tab by choosing **Sync DBLP last-author publications** → **Run workflow**.

The workflow imports DBLP records where Joey is the final listed author, merges publications into the generated block in `index.html`, and preserves the hand-curated entries already on the page. It deduplicates by normalized title and updates the displayed publication count. The generated entries appear between `DBLP_AUTO_START` and `DBLP_AUTO_END` markers.

New DBLP entries are added only when their venue matches the allowlist in `data/top_tier_venues.json`: the CCF seventh-edition 2026 A list or ICORE 2026 A* conference list. New papers at other or unrecognized venues are not published automatically. Unrecognized venues appear in the workflow review summary/artifact so they can be checked; if a venue qualifies, add its official name to the relevant list and rerun. Existing homepage entries are preserved when this rule is introduced.

Topic categories are assigned from title and venue keywords by `scripts/sync_dblp.py`. If the title and venue contain no category keywords, or the keyword scores tie, the script treats the classification as uncertain. New uncertain papers are held out of the homepage until they are reviewed; papers already on the homepage keep their current category. The monthly workflow lists uncertain titles in its run summary and saves their details as the `classification-review` artifact.

After checking that workflow run, add the normalized lowercase title as a key in `data/publication_categories.json` and use one of `Efficient AI`, `Trustworthy AI`, or `Foundation Models & Agents` as the value. Then rerun the workflow to publish it. For example:

```json
{
  "a sample paper title": "Trustworthy AI"
}
```
