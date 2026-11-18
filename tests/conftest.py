import gzip
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"
FILES = {
    "torvik": "torvik_2027_team_results.csv.gz",
    "haslametrics": "haslametrics_ratings.xml.gz",
    "espn_bpi": "espn_bpi.json.gz",
    "teamrankings": "teamrankings_predictive.html.gz",
    "warrennolan": "warrennolan_2027_net.html.gz",
    "cbbd": "cbbd_adjusted_2027.json.gz",
    "bracketmatrix": "bracketmatrix.html.gz",
    "ncaa_net": "ncaa_net.html.gz",  # saved before the first 2026-27 NET: last season's final
}


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture(scope="session")
def raw():
    """raw[source] -> decompressed bytes of the saved download."""
    return {name: gzip.decompress((FIXTURES / f).read_bytes()) for name, f in FILES.items()}
