"""Unit tests for yt_analyst.cli utility functions."""

import math
import pytest

from yt_analyst.cli import (
    parse_frontmatter,
    render_frontmatter,
    slugify,
    normalize_channel_input,
    count_syllables,
    flesch_kincaid_grade,
    cosine_similarity,
    tokenize,
    infer_format,
    _fk_label,
    _dominant_address,
    _formality_label,
)


# ─── parse_frontmatter ────────────────────────────────────────────────────────

def test_parse_frontmatter_basic():
    text = "---\ntitle: Hello\ncount: 3\n---\n\nBody text here."
    meta, body = parse_frontmatter(text)
    assert meta == {"title": "Hello", "count": 3}
    assert "Body text here." in body


def test_parse_frontmatter_no_frontmatter():
    text = "Just a plain body."
    meta, body = parse_frontmatter(text)
    assert meta == {}
    assert body == text


def test_parse_frontmatter_empty_meta():
    text = "---\n---\n\nBody."
    meta, body = parse_frontmatter(text)
    assert meta == {}
    assert "Body." in body


def test_parse_frontmatter_list_value():
    text = "---\nvideos:\n  - id: abc\n    status: pending\n---\n\nBody."
    meta, body = parse_frontmatter(text)
    assert meta["videos"][0]["id"] == "abc"


# ─── render_frontmatter ───────────────────────────────────────────────────────

def test_render_roundtrip():
    meta = {"title": "Test", "count": 42}
    body = "Some content."
    rendered = render_frontmatter(meta, body)
    meta2, body2 = parse_frontmatter(rendered)
    assert meta2["title"] == "Test"
    assert meta2["count"] == 42
    assert "Some content." in body2


def test_render_preserves_unicode():
    meta = {"subject": "Isabelle Plante", "channel": "Sage Éducation"}
    body = "Voilà le contenu."
    rendered = render_frontmatter(meta, body)
    meta2, _ = parse_frontmatter(rendered)
    assert meta2["channel"] == "Sage Éducation"


# ─── slugify ─────────────────────────────────────────────────────────────────

def test_slugify_basic():
    assert slugify("Sage AI Labs") == "sage-ai-labs"


def test_slugify_special_chars():
    assert slugify("Hello, World! (2025)") == "hello-world-2025"


def test_slugify_multiple_spaces():
    assert slugify("Too  Many   Spaces") == "too-many-spaces"


def test_slugify_leading_trailing():
    assert slugify("  --trimmed-- ") == "trimmed"


# ─── normalize_channel_input ──────────────────────────────────────────────────

def test_normalize_handle():
    url = normalize_channel_input("@SageAILabs")
    assert url == "https://www.youtube.com/@SageAILabs"


def test_normalize_channel_id():
    cid = "UC" + "a" * 22
    url = normalize_channel_input(cid)
    assert "channel" in url
    assert cid in url


def test_normalize_full_url_passthrough():
    url = "https://www.youtube.com/@example"
    assert normalize_channel_input(url) == url


def test_normalize_bare_name():
    url = normalize_channel_input("SomeName")
    assert url == "https://www.youtube.com/@SomeName"


# ─── count_syllables ─────────────────────────────────────────────────────────

def test_syllables_minimum_one():
    assert count_syllables("by") >= 1
    assert count_syllables("the") >= 1


def test_syllables_longer_words():
    assert count_syllables("education") >= 3
    assert count_syllables("implementation") >= 4


def test_syllables_single_vowel():
    assert count_syllables("cat") == 1


# ─── flesch_kincaid_grade ────────────────────────────────────────────────────

def test_fk_returns_float():
    text = "The cat sat on the mat. The dog ran fast."
    grade = flesch_kincaid_grade(text)
    assert isinstance(grade, float)


def test_fk_empty_text():
    assert flesch_kincaid_grade("") == 0.0


def test_fk_complex_higher_than_simple():
    simple = "I like dogs. Dogs are fun. Fun is good."
    complex_ = (
        "The systematic implementation of pedagogical methodologies "
        "necessitates comprehensive evaluation frameworks. "
        "Longitudinal studies demonstrate significant epistemological implications."
    )
    assert flesch_kincaid_grade(complex_) > flesch_kincaid_grade(simple)


# ─── cosine_similarity ───────────────────────────────────────────────────────

def test_cosine_identical():
    v = {"cat": 3, "dog": 2}
    assert cosine_similarity(v, v) == pytest.approx(1.0)


def test_cosine_disjoint():
    a = {"cat": 1}
    b = {"dog": 1}
    assert cosine_similarity(a, b) == 0.0


def test_cosine_partial():
    a = {"cat": 2, "dog": 1}
    b = {"cat": 1, "fish": 3}
    sim = cosine_similarity(a, b)
    assert 0.0 < sim < 1.0


def test_cosine_empty():
    assert cosine_similarity({}, {"cat": 1}) == 0.0


# ─── tokenize ────────────────────────────────────────────────────────────────

def test_tokenize_removes_stop_words():
    tokens = tokenize("the cat sat on a mat")
    assert "the" not in tokens
    assert "a" not in tokens
    assert "on" not in tokens


def test_tokenize_keeps_content_words():
    tokens = tokenize("education transforms communities")
    assert "education" in tokens
    assert "transforms" in tokens
    assert "communities" in tokens


# ─── infer_format ────────────────────────────────────────────────────────────

def test_infer_presentation():
    assert infer_format("GESA 2025 Presentation by Isabelle") == "presentation"


def test_infer_tutorial():
    assert infer_format("How to build a Sage.is agent") == "tutorial"


def test_infer_unknown():
    assert infer_format("Random video title with no keywords") == "unknown"


# ─── Label helpers ───────────────────────────────────────────────────────────

def test_fk_labels():
    assert _fk_label(4.0) == "very accessible"
    assert _fk_label(7.5) == "accessible"
    assert _fk_label(10.0) == "standard"
    assert _fk_label(13.0) == "college-level"
    assert _fk_label(17.0) == "graduate-level"


def test_dominant_address_you():
    assert "direct" in _dominant_address(100, 10, 5)


def test_dominant_address_we():
    assert "inclusive" in _dominant_address(5, 80, 3)


def test_dominant_address_one():
    assert "authoritative" in _dominant_address(1, 2, 50)


def test_formality_labels():
    assert _formality_label(0, 1000) == "conversational"
    assert _formality_label(20, 1000) == "moderately formal"
    assert _formality_label(50, 1000) == "formal"
