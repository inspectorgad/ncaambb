"""Build site/guide.html from the README's "Reading the dashboard" section.

    python -m ncaambb.tools.build_guide          # rewrite site/guide.html
    python -m ncaambb.tools.build_guide --check  # exit 1 if it is out of date

The README is the single source of the explanations; edit it, then run
this. A test fails if guide.html no longer matches the README.
Needs the `markdown` package (in the dev extras).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from .. import PROJECT_ROOT

README = PROJECT_ROOT / "README.md"
GUIDE = PROJECT_ROOT / "site" / "guide.html"
START, END = "## Reading the dashboard", "## Setup"

TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Dashboard Guide</title>
  <meta name="description" content="What every column, card and badge on the D1 Composite Rankings dashboard means.">
  <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'><circle cx='16' cy='16' r='14' fill='%23eb6834'/><path d='M2 16h28M16 2v28M6 6c6 6 6 14 0 20M26 6c-6 6-6 14 0 20' stroke='%23111' stroke-width='2' fill='none'/></svg>">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@600;700&display=swap">
  <link rel="stylesheet" href="styles.css">
  <script>
    try {{ const t = localStorage.getItem("theme"); if (t) document.documentElement.dataset.theme = t; }} catch (e) {{}}
  </script>
</head>
<body>
  <!-- Generated from README.md by `python -m ncaambb.tools.build_guide`. Edit the README, not this file. -->
  <header class="top">
    <div class="wrap">
      <div class="top-row">
        <h1><a href="./">D1 Composite Rankings</a></h1>
        <span class="updated">Dashboard guide</span>
      </div>
    </div>
  </header>
  <main class="wrap guide">
    <a class="back" href="./">← Back to rankings</a>
    <nav class="guide-nav" aria-label="Sections">
{nav}
    </nav>
{cards}
    <p class="legend-note"><a href="./">← Back to rankings</a></p>
  </main>
</body>
</html>
"""


def loosen_lists(md: str) -> str:
    """Insert a blank line before a list that directly follows a text line.

    GitHub renders such lists, but Python-Markdown needs the blank line.
    """
    out: list[str] = []
    for line in md.split("\n"):
        is_item = re.match(r"\s*([-*+]|\d+\.)\s", line) is not None
        prev = out[-1] if out else ""
        prev_is_item = re.match(r"\s*([-*+]|\d+\.)\s", prev) is not None
        if is_item and prev.strip() and not prev_is_item and not prev.lstrip().startswith("|"):
            out.append("")
        out.append(line)
    return "\n".join(out)


def slugify(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")


def render(readme_text: str) -> str:
    import markdown  # dev dependency

    try:
        section = readme_text.split(START, 1)[1].split(END, 1)[0]
    except IndexError:
        raise SystemExit(f"README is missing the '{START}' or '{END}' heading")
    nav, cards = [], []
    for part in re.split(r"(?m)^### ", section)[1:]:
        title, body = part.split("\n", 1)
        title = title.strip()
        slug = slugify(title)
        html = markdown.markdown(loosen_lists(body), extensions=["tables"])
        html = html.replace("<table>", '<div class="plain-wrap"><table class="plain guide-table">')
        html = html.replace("</table>", "</table></div>")
        nav.append(f'      <a href="#{slug}">{title}</a>')
        cards.append(f'<section class="card guide-card" id="{slug}">\n<h2>{title}</h2>\n{html}\n</section>')
    return TEMPLATE.format(nav="\n".join(nav), cards="\n".join(cards))


def main(argv: list[str]) -> int:
    page = render(README.read_text(encoding="utf-8"))
    if "--check" in argv:
        current = GUIDE.read_text(encoding="utf-8") if GUIDE.exists() else ""
        if current != page:
            print("site/guide.html is out of date: run python -m ncaambb.tools.build_guide")
            return 1
        return 0
    GUIDE.write_text(page, encoding="utf-8")
    print(f"wrote {GUIDE}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
