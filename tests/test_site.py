"""Guards for the deploy step that versions asset URLs (cache-busting)."""

from ncaambb import PROJECT_ROOT

SITE = PROJECT_ROOT / "site"


def test_pages_reference_assets_the_way_the_deploy_step_expects():
    # .github/workflows/update.yml rewrites exactly these strings
    index = (SITE / "index.html").read_text(encoding="utf-8")
    assert index.count('href="styles.css"') == 1 and index.count('src="app.js"') == 1
    guide = (SITE / "guide.html").read_text(encoding="utf-8")
    assert guide.count('href="styles.css"') == 1


def test_workflow_versions_the_assets():
    workflow = (PROJECT_ROOT / ".github" / "workflows" / "update.yml").read_text(encoding="utf-8")
    step = workflow.index("Version asset URLs")
    assert step < workflow.index("Upload site")
    assert "site/index.html site/guide.html" in workflow
