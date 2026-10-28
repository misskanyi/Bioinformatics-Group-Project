"""Headless smoke tests of every dashboard page (Streamlit AppTest)."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parent.parent
pytestmark = pytest.mark.skipif(not (ROOT / "outputs/explorer/organisms/protein_organisms.csv").exists(),
                                reason="pipeline outputs not generated")

PAGE = """
import sys
sys.path.insert(0, {root!r}); sys.path.insert(0, {app!r})
import streamlit_app as m
m.{fn}()
"""


def run_page(fn):
    at = AppTest.from_string(PAGE.format(root=str(ROOT), app=str(ROOT / "app"), fn=fn), default_timeout=180)
    return at.run()


@pytest.mark.parametrize("fn", ["page_search", "page_clusters", "page_temperature", "page_overview"])
def test_page_renders(fn):
    at = run_page(fn)
    assert not at.exception, [e.value for e in at.exception]


def test_search_valid_and_invalid():
    at = run_page("page_search")
    at.selectbox[0].select_index(1).run()
    at.button[0].click().run()
    assert not at.exception
    assert at.dataframe, "results table missing"
    assert any("promising candidate" in s.value for s in at.success)
    at.text_area[0].input("ACGTACGTACGTACGTACGTACGTACGTACGTACGT").run()
    at.button[0].click().run()
    assert any("DNA" in e.value for e in at.error)
