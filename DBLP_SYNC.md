# DBLP publication sync

GitHub Actions queries Joey Tianyi Zhou's DBLP author record (`123/5110`) through DBLP's SPARQL endpoint on the first day of each month at 08:00 Singapore time. Run it manually from the repository's **Actions** tab by choosing **Sync DBLP last-author publications** → **Run workflow**.

The workflow imports DBLP records where Joey is the final listed author, merges publications into the generated block in `index.html`, and preserves the hand-curated entries already on the page. It deduplicates by normalized title and updates the displayed publication count. The generated entries appear between `DBLP_AUTO_START` and `DBLP_AUTO_END` markers.

Topic categories are assigned from title and venue keywords by `scripts/sync_dblp.py`. To override a category, add the normalized lowercase title as a key in `data/publication_categories.json` and use one of `Efficient AI`, `Trustworthy AI`, or `Foundation Models & Agents` as the value. For example:

```json
{
  "a sample paper title": "Trustworthy AI"
}
```
