"""Unit tests for the shopping log-block parsers in posthog_shopping_capture."""

from __future__ import annotations

import sys
from pathlib import Path

HOOKS_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HOOKS_DIR))

import posthog_shopping_capture as hook  # noqa: E402


ADVISE_LOG_SAMPLE = """\
## office-chair — advise

_Generated 2026-05-12 10:33. Caveman log._

- slug: office-chair
- top_pick: "Featherlite Optima Plus" | https://featherlite.in/optima-plus
- retailer: amazon.in
- best_card: SBI Rupay Debit Card
- list_price: 15999
- effective_price: 13499
- alts: ["Wakefit Ergo X", "Green Soul Vienna"]
- values_winner: user-friendly
- recco_path: .shopping/reccos/office-chair/

## cookware-set — advise

_Generated 2026-05-12 11:05. Caveman log._

- slug: cookware-set
- top_pick: "Hawkins Futura Hard Anodised 5-Piece" | https://hawkinscookers.com/futura-set
- retailer: flipkart.com
- best_card: Flipkart Axis Bank Credit Card
- list_price: 5999
- effective_price: 5399
- alts: ["Prestige Omega Deluxe", "Vinod Platinum"]
- values_winner: value
- recco_path: .shopping/reccos/cookware-set/
"""


RECCOS_LOG_SAMPLE = """\
## broad — reccos

_Generated 2026-05-12 09:00. Caveman log._

- topic: broad
- count: 4
- slugs: ["chess-set", "monitor-27in", "tanpura-electronic", "running-shoes-trail"]
- tags: ["interest-match", "gap", "interest-match", "upgrade"]
- top_reason: "Charter pillar #11 chess explored Feb 2026, no quality set yet"

## kitchen — reccos

_Generated 2026-05-12 09:30. Caveman log._

- topic: kitchen
- count: 3
- slugs: ["cookware-set", "knife-chef", "wok-carbon-steel"]
- tags: ["gap", "gap", "interest-match"]
- top_reason: "Cookware deferred 6+ weeks in W20 patterns; charter prioritises home"
"""


def test_parse_advise_returns_latest_block(tmp_path):
    log = tmp_path / "shopping-advise-log.md"
    log.write_text(ADVISE_LOG_SAMPLE, encoding="utf-8")
    result = hook._parse_advise_log(str(log))
    assert result["slug"] == "cookware-set"
    assert result["top_pick"].startswith("Hawkins Futura Hard Anodised")
    assert "hawkinscookers.com" in result["top_pick"]
    assert result["retailer"] == "flipkart.com"
    assert result["best_card"] == "Flipkart Axis Bank Credit Card"
    assert result["list_price"] == 5999
    assert result["effective_price"] == 5399
    assert result["alts"] == ["Prestige Omega Deluxe", "Vinod Platinum"]
    assert result["values_winner"] == "value"
    assert result["recco_path"] == ".shopping/reccos/cookware-set/"


def test_parse_advise_handles_missing_file(tmp_path):
    log = tmp_path / "missing.md"
    result = hook._parse_advise_log(str(log))
    assert result["slug"] == ""
    assert result["list_price"] == 0
    assert result["alts"] == []


def test_parse_advise_handles_empty_log(tmp_path):
    log = tmp_path / "shopping-advise-log.md"
    log.write_text("# nothing here\n", encoding="utf-8")
    result = hook._parse_advise_log(str(log))
    assert result["slug"] == ""


def test_parse_reccos_returns_latest_block(tmp_path):
    log = tmp_path / "shopping-reccos-log.md"
    log.write_text(RECCOS_LOG_SAMPLE, encoding="utf-8")
    result = hook._parse_reccos_log(str(log))
    assert result["topic"] == "kitchen"
    assert result["count"] == 3
    assert result["slugs"] == ["cookware-set", "knife-chef", "wok-carbon-steel"]
    assert result["tags"] == ["gap", "gap", "interest-match"]
    assert "Cookware deferred" in result["top_reason"]


def test_parse_reccos_empty_list(tmp_path):
    log = tmp_path / "shopping-reccos-log.md"
    log.write_text(
        "## broad — reccos\n\n"
        "- topic: broad\n"
        "- count: 0\n"
        "- slugs: []\n"
        "- tags: []\n"
        "- top_reason: \"\"\n",
        encoding="utf-8",
    )
    result = hook._parse_reccos_log(str(log))
    assert result["topic"] == "broad"
    assert result["count"] == 0
    assert result["slugs"] == []
    assert result["tags"] == []


def test_grab_int_zero_when_missing():
    block = "- topic: foo\n- count: 0\n"
    assert hook._grab_int(block, "missing") == 0
    assert hook._grab_int(block, "count") == 0


def test_grab_string_strips_quotes():
    block = '- top_reason: "quoted value"\n'
    assert hook._grab_string(block, "top_reason") == "quoted value"


def test_grab_list_returns_items():
    block = '- slugs: ["a", "b", "c"]\n'
    assert hook._grab_list(block, "slugs") == ["a", "b", "c"]


def test_grab_list_empty():
    block = "- slugs: []\n"
    assert hook._grab_list(block, "slugs") == []
