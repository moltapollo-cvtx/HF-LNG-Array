"""Schema validator tests for site_config.load_site."""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from lib.site_config import load_site, SiteConfigError
from tests._runner import run_tests

FIXTURES = Path(__file__).parent / "fixtures"


def test_valid_loads():
    site = load_site(FIXTURES / "valid-site.yaml")
    assert site.id == "option-test"
    assert site.letter == "T"
    assert site.iso_array.count == 6
    assert len(site.equipment) == 2
    assert site.equipment[1].rotation == 45.0
    assert site.equipment[0].rotation == 0.0


def test_missing_id_fails():
    try:
        load_site(FIXTURES / "bad-missing-id.yaml")
    except SiteConfigError as e:
        assert "site.id" in str(e)
        return
    raise AssertionError("expected SiteConfigError for missing id")


def test_unknown_type_fails():
    try:
        load_site(FIXTURES / "bad-bad-type.yaml")
    except SiteConfigError as e:
        assert "rocket_launcher" in str(e)
        return
    raise AssertionError("expected SiteConfigError for unknown type")


def test_duplicate_id_fails():
    try:
        load_site(FIXTURES / "bad-dup-id.yaml")
    except SiteConfigError as e:
        assert "bogCapture" in str(e).lower() or "duplicate" in str(e).lower()
        return
    raise AssertionError("expected SiteConfigError for duplicate id")


if __name__ == "__main__":
    sys.exit(run_tests({
        "valid loads": test_valid_loads,
        "missing id fails": test_missing_id_fails,
        "unknown type fails": test_unknown_type_fails,
        "duplicate id fails": test_duplicate_id_fails,
    }))
