#!/usr/bin/env python3
"""
HackerTools scanner — finds developer tools that HN commenters recommend.

For every tool in SEED, it searches Hacker News comments (via the public
HN Algolia API), keeps only comments that mention the tool in a
recommending way ("I use", "switched to", "recommend", ...), counts
DISTINCT commenters, and keeps links back to the best comments.

Output: tools.json (read by index.html)

Usage:
    python3 scan_tools.py              # full scan
    python3 scan_tools.py --limit 5    # quick test on first 5 tools
    python3 scan_tools.py --min 2      # minimum distinct commenters (default 2)

No API key needed. Standard library only.
"""
import argparse, html, json, re, sys, time, urllib.parse, urllib.request
from datetime import datetime, timezone

API = "https://hn.algolia.com/api/v1/search"
API_DATE = "https://hn.algolia.com/api/v1/search_by_date"  # newest first

# name, category, homepage, aliases (extra spellings), optional "strict" flag
# strict=True -> name is a common English word; require case-sensitive match
SEED = [
    # Editors & IDEs
    ("Neovim", "Editors", "https://neovim.io", ["nvim"]),
    ("VS Code", "Editors", "https://code.visualstudio.com", ["VSCode", "Visual Studio Code"]),
    ("Sublime Text", "Editors", "https://www.sublimetext.com", []),
    ("Emacs", "Editors", "https://www.gnu.org/software/emacs/", []),
    ("Helix", "Editors", "https://helix-editor.com", ["helix editor"], True),
    ("Zed", "Editors", "https://zed.dev", ["zed editor"], True),
    ("JetBrains", "Editors", "https://www.jetbrains.com", ["IntelliJ", "PyCharm"]),
    ("Cursor", "Editors", "https://cursor.com", ["Cursor IDE"], True),
    # Terminals & shell
    ("tmux", "Terminal", "https://github.com/tmux/tmux", []),
    ("fzf", "Terminal", "https://github.com/junegunn/fzf", []),
    ("ripgrep", "Terminal", "https://github.com/BurntSushi/ripgrep", ["rg"]),
    ("zoxide", "Terminal", "https://github.com/ajeetdsouza/zoxide", []),
    ("fish shell", "Terminal", "https://fishshell.com", ["fish"], True),
    ("Oh My Zsh", "Terminal", "https://ohmyz.sh", ["oh-my-zsh"]),
    ("iTerm2", "Terminal", "https://iterm2.com", []),
    ("WezTerm", "Terminal", "https://wezfurlong.org/wezterm/", []),
    ("Ghostty", "Terminal", "https://ghostty.org", []),
    ("Alacritty", "Terminal", "https://alacritty.org", []),
    ("Kitty", "Terminal", "https://sw.kovidgoyal.net/kitty/", ["kitty terminal"], True),
    ("Warp", "Terminal", "https://www.warp.dev", ["Warp terminal"], True),
    ("bat", "Terminal", "https://github.com/sharkdp/bat", ["batcat"], True),
    ("fd", "Terminal", "https://github.com/sharkdp/fd", ["fd-find"], True),
    ("jq", "Terminal", "https://jqlang.github.io/jq/", []),
    ("htop", "Terminal", "https://htop.dev", ["btop"]),
    ("Atuin", "Terminal", "https://atuin.sh", []),
    ("Starship", "Terminal", "https://starship.rs", ["starship prompt"], True),
    # Git
    ("Magit", "Git", "https://magit.vc", []),
    ("lazygit", "Git", "https://github.com/jesseduffield/lazygit", []),
    ("tig", "Git", "https://jonas.github.io/tig/", [], True),
    ("delta", "Git", "https://github.com/dandavison/delta", ["git-delta"], True),
    ("Jujutsu", "Git", "https://github.com/jj-vcs/jj", ["jj vcs"]),
    ("Fork", "Git", "https://git-fork.com", ["Fork git client"], True),
    ("Sourcetree", "Git", "https://www.sourcetreeapp.com", []),
    # Languages tooling / build
    ("uv", "Dev tooling", "https://github.com/astral-sh/uv", ["astral uv"], True),
    ("Ruff", "Dev tooling", "https://github.com/astral-sh/ruff", [], True),
    ("Poetry", "Dev tooling", "https://python-poetry.org", [], True),
    ("pnpm", "Dev tooling", "https://pnpm.io", []),
    ("Bun", "Dev tooling", "https://bun.sh", ["bun.sh"], True),
    ("Deno", "Dev tooling", "https://deno.com", []),
    ("Vite", "Dev tooling", "https://vite.dev", []),
    ("esbuild", "Dev tooling", "https://esbuild.github.io", []),
    ("mise", "Dev tooling", "https://mise.jdx.dev", ["rtx"], True),
    ("asdf", "Dev tooling", "https://asdf-vm.com", []),
    ("direnv", "Dev tooling", "https://direnv.net", []),
    ("Nix", "Dev tooling", "https://nixos.org", ["NixOS", "nix-shell"], True),
    ("just", "Dev tooling", "https://github.com/casey/just", ["justfile"], True),
    ("pre-commit", "Dev tooling", "https://pre-commit.com", []),
    # Containers & infra
    ("Docker", "Infra", "https://www.docker.com", []),
    ("Podman", "Infra", "https://podman.io", []),
    ("OrbStack", "Infra", "https://orbstack.dev", []),
    ("k9s", "Infra", "https://k9scli.io", []),
    ("Terraform", "Infra", "https://www.terraform.io", ["OpenTofu"]),
    ("Ansible", "Infra", "https://www.ansible.com", []),
    ("Tailscale", "Infra", "https://tailscale.com", []),
    ("Caddy", "Infra", "https://caddyserver.com", [], True),
    ("Cloudflare Tunnel", "Infra", "https://www.cloudflare.com/products/tunnel/", ["cloudflared"]),
    ("Coolify", "Infra", "https://coolify.io", []),
    ("Hetzner", "Infra", "https://www.hetzner.com", []),
    ("Fly.io", "Infra", "https://fly.io", []),
    ("Proxmox", "Infra", "https://www.proxmox.com", []),
    ("Syncthing", "Infra", "https://syncthing.net", []),
    # Databases & data
    ("SQLite", "Data", "https://sqlite.org", []),
    ("PostgreSQL", "Data", "https://www.postgresql.org", ["Postgres"]),
    ("DuckDB", "Data", "https://duckdb.org", []),
    ("DBeaver", "Data", "https://dbeaver.io", []),
    ("TablePlus", "Data", "https://tableplus.com", []),
    ("Datasette", "Data", "https://datasette.io", []),
    ("pgcli", "Data", "https://www.pgcli.com", []),
    ("Redis", "Data", "https://redis.io", ["Valkey"]),
    # API & debugging
    ("Postman", "API & debug", "https://www.postman.com", [], True),
    ("Insomnia", "API & debug", "https://insomnia.rest", [], True),
    ("Bruno", "API & debug", "https://www.usebruno.com", ["Bruno API"], True),
    ("HTTPie", "API & debug", "https://httpie.io", []),
    ("mitmproxy", "API & debug", "https://mitmproxy.org", []),
    ("Wireshark", "API & debug", "https://www.wireshark.org", []),
    ("Charles Proxy", "API & debug", "https://www.charlesproxy.com", []),
    ("Sentry", "API & debug", "https://sentry.io", [], True),
    ("Grafana", "API & debug", "https://grafana.com", []),
    # Productivity / notes
    ("Obsidian", "Productivity", "https://obsidian.md", [], True),
    ("Logseq", "Productivity", "https://logseq.com", []),
    ("Org mode", "Productivity", "https://orgmode.org", ["org-mode"]),
    ("Notion", "Productivity", "https://www.notion.so", [], True),
    ("Raycast", "Productivity", "https://www.raycast.com", []),
    ("Alfred", "Productivity", "https://www.alfredapp.com", ["Alfred app"], True),
    ("Rectangle", "Productivity", "https://rectangleapp.com", ["Rectangle app"], True),
    ("AeroSpace", "Productivity", "https://github.com/nikitabobko/AeroSpace", [], True),
    ("Karabiner", "Productivity", "https://karabiner-elements.pqrs.org", ["Karabiner-Elements"]),
    ("Hammerspoon", "Productivity", "https://www.hammerspoon.org", []),
    ("AutoHotkey", "Productivity", "https://www.autohotkey.com", []),
    ("PowerToys", "Productivity", "https://learn.microsoft.com/windows/powertoys/", []),
    ("Excalidraw", "Productivity", "https://excalidraw.com", []),
    ("Anki", "Productivity", "https://apps.ankiweb.net", []),
    ("Bitwarden", "Productivity", "https://bitwarden.com", ["Vaultwarden"]),
    ("1Password", "Productivity", "https://1password.com", []),
    ("KeePassXC", "Productivity", "https://keepassxc.org", ["KeePass"]),
    ("Zotero", "Productivity", "https://www.zotero.org", []),
    ("Calibre", "Productivity", "https://calibre-ebook.com", [], True),
    # Self-hosting & misc
    ("Home Assistant", "Self-hosted", "https://www.home-assistant.io", []),
    ("Pi-hole", "Self-hosted", "https://pi-hole.net", ["pihole"]),
    ("Immich", "Self-hosted", "https://immich.app", []),
    ("Jellyfin", "Self-hosted", "https://jellyfin.org", []),
    ("Nextcloud", "Self-hosted", "https://nextcloud.com", []),
    ("Uptime Kuma", "Self-hosted", "https://github.com/louislam/uptime-kuma", []),
    ("Plausible", "Self-hosted", "https://plausible.io", ["Plausible Analytics"], True),
    ("restic", "Self-hosted", "https://restic.net", ["borgbackup", "Borg backup"]),
    # Media / utilities
    ("ffmpeg", "Utilities", "https://ffmpeg.org", []),
    ("yt-dlp", "Utilities", "https://github.com/yt-dlp/yt-dlp", []),
    ("ImageMagick", "Utilities", "https://imagemagick.org", []),
    ("Pandoc", "Utilities", "https://pandoc.org", []),
    ("OBS", "Utilities", "https://obsproject.com", ["OBS Studio"], True),
    ("VLC", "Utilities", "https://www.videolan.org/vlc/", []),
    ("mpv", "Utilities", "https://mpv.io", []),
    ("Firefox", "Utilities", "https://www.mozilla.org/firefox/", []),
    ("uBlock Origin", "Utilities", "https://ublockorigin.com", ["uBO"]),
    ("Ollama", "Utilities", "https://ollama.com", []),
    ("llama.cpp", "Utilities", "https://github.com/ggml-org/llama.cpp", []),
    ("LM Studio", "Utilities", "https://lmstudio.ai", []),
]

# A mention only counts if the comment sounds like a recommendation / real use.
CUE = re.compile(
    r"\b(i use|i've used|i have used|i'?ve been using|been using|we use|i switched to|switched to|"
    r"recommend|highly recommend|can't live without|cannot live without|swear by|love|favou?rite|"
    r"daily driver|go-to|my go to|game changer|life saver|lifesaver|check out|try|give .{0,20} a try|"
    r"best tool|use it every day|use it daily)\b", re.I)

# Negative mentions never count.
NEG = re.compile(
    r"\b(never use|never used|never using|have not used|haven't used|stopped using|stop using|switched (away )?from|moved away from|"
    r"gave up on|uninstalled|ditched|got rid of|avoid|moved back to|went back to|switching back to|switched back to|migrate (away|somewhere else)|"
    r"lost (my )?trust|trust in)\b", re.I)

# Threads that list tools as job requirements, not recommendations.
SKIP_STORY = re.compile(r"who is hiring|who wants to be hired|freelancer\? seeking", re.I)

# Ambiguous names: the comment must also contain one of these context words.
CONTEXT = {
    "AeroSpace": r"tiling|window manager|macos|yabai|i3|workspace",
    "Alfred": r"alfred ?app|launcher|spotlight|raycast|workflow|macos|hotkey",
    "asdf": r"version manager|asdf install|tool-versions|asdf plugin|mise|nvm|pyenv|rbenv",
    "fd": r"find|ripgrep|\brg\b|fd-find|sharkdp|fzf",
    "bat": r"\bcat\b|syntax highlight|batcat|sharkdp|\bpager\b|\bless\b|\bfd\b|ripgrep",
    "delta": r"\bgit\b|\bdiffs?\b|\bpager\b|git-delta",
    "fish shell": r"\bshell\b|\bzsh\b|\bbash\b|terminal|prompt|fisher|config\.fish",
    "Fork": r"\bgit\b|client|sourcetree|gitkraken",
    "Cursor": r"\bide\b|editor|vs ?code|copilot|ai",
    "Caddy": r"nginx|reverse proxy|https|server|certificate|caddyfile",
    "Calibre": r"e-?book|epub|kindle|kobo|library",
    "Bruno": r"postman|insomnia|\bapi\b|http|request",
}
CONTEXT = {k: re.compile(v, re.I) for k, v in CONTEXT.items()}

# Tool named right after one of these is the loser of a comparison ("better than X", "replaced X").
LOSER = re.compile(r"(than|as good as|replaced|replacing|instead of|over|from|vs\.?|versus|after giving|after trying)[\s\w+/-]{0,12}$", re.I)

NEAR = 120  # cue must sit within this many characters of the tool name


STRONG = re.compile(r"\b(i use|i've been using|i love|love it|daily driver|highly recommend|i recommend|"
    r"switched to|can't live without|swear by|my favou?rite|use it (every day|daily))\b", re.I)


def quote_score(text, rx):
    """How clearly the comment recommends the tool: a strong cue right next to the name scores highest."""
    best = 0
    for m in rx.finditer(text):
        win = text[max(0, m.start() - 60): m.end() + 60]
        if STRONG.search(win):
            best = max(best, 2)
        elif CUE.search(win):
            best = max(best, 1)
    return best


def recommends(text, rx):
    """True if some mention of the tool has a recommendation cue nearby and no negative cue."""
    for m in rx.finditer(text):
        if LOSER.search(text[max(0, m.start() - 30): m.start()]):
            continue
        win = text[max(0, m.start() - NEAR): m.end() + NEAR]
        if CUE.search(win) and not NEG.search(win):
            return True
    return False

TAG = re.compile(r"<[^>]+>")


def clean(text):
    return html.unescape(TAG.sub(" ", text or "")).replace(" ", " ")


def name_regex(names, strict):
    parts = [re.escape(n) for n in names]
    pat = r"(?<![\w./-])(" + "|".join(parts) + r")(?![\w-])"
    return re.compile(pat, 0 if strict else re.I)


def fetch(params, retries=4, api=API):
    url = api + "?" + urllib.parse.urlencode(params)
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "HackerTools/1.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception as e:  # rate limit / network blip
            wait = 2 ** i
            print(f"   retry in {wait}s ({e})", file=sys.stderr)
            time.sleep(wait)
    return {"hits": [], "nbPages": 0}


def snippet(text, rx, width=220):
    m = rx.search(text)
    if not m:
        return text[:width].strip()
    start = max(0, m.start() - width // 2)
    s = text[start:start + width].strip()
    return ("…" if start > 0 else "") + s + ("…" if start + width < len(text) else "")


def scan_tool(entry, pages):
    name, cat, url, aliases = entry[:4]
    strict = len(entry) > 4 and entry[4]
    names = [name] + aliases
    rx = name_regex(names, strict)
    authors, comments = set(), []
    seen = set()
    # Relevance search alone skews to old threads (Emacs, Docker stuck in 2015),
    # so also pull the newest comments for every name.
    for query, api in [(q, a) for q in names for a in (API, API_DATE)]:
        for page in range(pages):
            data = fetch({"query": f'"{query}"', "tags": "comment",
                          "hitsPerPage": 1000, "page": page}, api=api)
            hits = data.get("hits", [])
            for h in hits:
                cid = h.get("objectID")
                if cid in seen:
                    continue
                seen.add(cid)
                text = clean(h.get("comment_text"))
                if SKIP_STORY.search(h.get("story_title") or ""):
                    continue
                ctx = CONTEXT.get(name)
                if ctx and not ctx.search(text):
                    continue
                if not recommends(text, rx):
                    continue
                author = h.get("author")
                if not author:
                    continue
                first_from_author = author not in authors
                authors.add(author)
                if first_from_author:
                    comments.append({
                        "id": cid,
                        "author": author,
                        "date": (h.get("created_at") or "")[:10],
                        "points": h.get("points") or 0,
                        "story": h.get("story_title") or "",
                        "story_id": h.get("story_id"),
                        "snippet": snippet(text, rx),
                        "score": quote_score(text, rx),
                    })
            if page + 1 >= data.get("nbPages", 0):
                break
            time.sleep(0.25)
    years = sorted({c["date"][:4] for c in comments if c["date"]})
    return {
        "name": name,
        "category": cat,
        "url": url,
        "commenters": len(authors),
        "first_year": years[0] if years else None,
        "last_year": years[-1] if years else None,
        "recent": sum(1 for c in comments if c["date"] >= str(datetime.now().year - 1)),
        # Clearest recommendations first, newest within each level; score is only for sorting.
        "comments": [{k: v for k, v in c.items() if k != "score"}
                     for c in sorted(comments, key=lambda c: (c["score"], c["date"]), reverse=True)[:12]],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--min", type=int, default=2)
    ap.add_argument("--pages", type=int, default=3, help="pages of 1000 comments per name")
    ap.add_argument("--out", default="tools.json")
    ap.add_argument("--only", default="", help="comma-separated tool names to scan")
    a = ap.parse_args()

    seed = SEED[: a.limit] if a.limit else SEED
    if a.only:
        want = {n.strip().lower() for n in a.only.split(",")}
        seed = [e for e in SEED if e[0].lower() in want]
    tools = []
    for i, entry in enumerate(seed, 1):
        print(f"[{i}/{len(seed)}] {entry[0]}", file=sys.stderr)
        t = scan_tool(entry, a.pages)
        if t["commenters"] >= a.min:
            tools.append(t)
        print(f"   {t['commenters']} distinct commenters", file=sys.stderr)

    tools.sort(key=lambda t: t["commenters"], reverse=True)
    out = {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ"),
        "source": "Hacker News comments via hn.algolia.com",
        "min_commenters": a.min,
        "tools": tools,
    }
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(f"wrote {len(tools)} tools -> {a.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
