import pytest

from ncaambb.tools import build_guide

pytest.importorskip("markdown")


def test_guide_matches_readme():
    """site/guide.html must be rebuilt whenever the README's guide changes."""
    expected = build_guide.render(build_guide.README.read_text(encoding="utf-8"))
    assert build_guide.GUIDE.read_text(encoding="utf-8") == expected, (
        "run: python -m ncaambb.tools.build_guide"
    )


def test_guide_has_the_sections_the_help_links_use():
    html = build_guide.GUIDE.read_text(encoding="utf-8")
    for anchor in ("rankings-table", "team-page", "offense-vs-defense", "conferences", "bracket", "header-badges"):
        assert f'id="{anchor}"' in html
