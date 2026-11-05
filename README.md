# HackerTools

Developer tools that Hacker News commenters actually recommend, ranked by how many **different people** vouched for them. Every tool links back to the comments.

Inspired by Karpathy's HackerTube (videos), and by [HackerBooks](https://hackerbooks.org) (books).

## How it works
1. `scan_tools.py` searches HN comments for ~120 dev tools via the public HN Algolia API.
2. A comment counts only if it names the tool **and** uses a recommendation phrase ("I use", "switched to", "recommend", "daily driver"…).
3. It counts **distinct commenters**, keeps links to their comments, and writes `tools.json`.
4. `index.html` is a static page that reads `tools.json`: search, categories, trending sort.

## Run it
```bash
python3 scan_tools.py --limit 5   # quick test
python3 scan_tools.py             # full scan (~20–40 min)
python3 -m http.server 8000       # open http://localhost:8000
```
No API key, standard library only.

## Deploy
Push to GitHub, enable Pages. `.github/workflows/refresh.yml` re-scans every Monday.

## Add a tool
Add a line to `SEED` in `scan_tools.py`: `(name, category, homepage, [aliases])`.
Add `True` as a 5th value when the name is a common word (Zed, Warp, Bun) so matching is case-sensitive.

## Caveats
Mentions are a signal, not a verdict. A recommendation phrase near a tool name usually means praise, but not always. Wrong match? Open an issue.
