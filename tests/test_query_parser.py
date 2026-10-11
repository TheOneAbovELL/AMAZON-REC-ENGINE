"""Query understanding and tokenisation. The same fixtures are asserted by tests/js/*.test.mjs."""

import pytest

from src.query_parser import parse_query
from src.text import normalize, stem, tokenize, variant_key


def test_query_fixture_cases(config, query_cases):
    for case in query_cases:
        parsed = parse_query(case["query"], config)
        budget = {"min": parsed.budget.min, "max": parsed.budget.max} if parsed.budget else None
        assert budget == case["budget"], case["query"]
        assert (parsed.intent.id if parsed.intent else None) == case["intent"], case["query"]
        assert parsed.terms == case["terms"], case["query"]
        assert parsed.prefers_low_price == case["prefers_low_price"], case["query"]


def test_text_fixture_cases(config, text_cases):
    phrase_map = config["text"]["phrase_normalizations"]
    for case in text_cases:
        assert tokenize(case["text"], phrase_map) == case["tokens"], case["text"]
        assert variant_key(normalize(case["text"], phrase_map), 3) == case["variant_key"], case["text"]


@pytest.mark.parametrize(
    "query",
    ["RTX 4060 laptop", "i5 12th gen laptop", "32 inch tv", "1.5 ton ac", "5 star fridge", "2 year warranty phone"],
)
def test_model_numbers_and_specs_are_not_budgets(config, query):
    assert parse_query(query, config).budget is None


@pytest.mark.parametrize(
    ("query", "expected_max"),
    [("laptop under 90k", 90000), ("earbuds under ₹1,499", 1499), ("tv under 1.5 lakh", 150000), ("shoes 2k", 2000)],
)
def test_budget_amount_formats(config, query, expected_max):
    assert parse_query(query, config).budget.max == expected_max


def test_budget_phrase_is_removed_from_terms(config):
    parsed = parse_query("bluetooth speaker under 3000", config)
    assert parsed.terms == ["bluetooth", "speaker"]
    assert parsed.search_text == "bluetooth speaker"


def test_head_noun_wins_and_accessory_queries_drop_intent(config):
    assert parse_query("gaming laptop", config).intent.id == "laptop"
    assert parse_query("laptop bag", config).intent.id == "backpack"
    assert parse_query("laptop cooling pad", config).intent is None


def test_stemming_rules():
    assert stem("earbuds") == "earbud"
    assert stem("watches") == "watch"
    assert stem("batteries") == "battery"
    assert stem("glasses") == "glass"
    assert stem("shoes") == "shoe"
    assert stem("tennis") == "tennis"
    assert stem("rtx4060s") == "rtx4060s"  # tokens with digits are left alone


def test_empty_query(config):
    parsed = parse_query("   ", config)
    assert parsed.terms == [] and parsed.intent is None and parsed.budget is None
