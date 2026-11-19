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
    for anchor in ("rankings-table", "story-cards-and-trends", "team-page", "offense-vs-defense", "conferences",
                   "bracket", "header-badges"):
        assert f'id="{anchor}"' in html


def test_lists_after_a_text_line_render_as_lists():
    html = build_guide.render(build_guide.README.read_text(encoding="utf-8"))
    assert "\n- " not in html  # no literal markdown bullets left in the page
    md = "**Heading:**\n- one\n- two\n"
    assert build_guide.loosen_lists(md) == "**Heading:**\n\n- one\n- two\n"
