"""Tests for graph/schemas.py.

Two things are being checked throughout: that a bad payload is *rejected* with
a message a model could act on, and that a merely-untidy payload is *normalized*
rather than rejected — spending a second API call to add a `#` would be a waste.
"""
from __future__ import annotations

import pytest

from graph import schemas
from graph.llm import SchemaError


def _beats(word_count: int = 14) -> list[dict[str, str]]:
    """Five well-formed beats, long enough to land in the brand duration window."""
    line = " ".join(["word"] * word_count)
    beats = [
        {"beat": name, "line": line, "on_screen": "label"}
        for name in ("hook", "problem", "product_reveal", "proof", "cta")
    ]
    beats[0]["line"] = "A short punchy hook"  # respects hook_max_words
    return beats


def _brief(**overrides):
    payload = {
        "objective": "Drive product page visits",
        "target_persona": "urban-commuter",
        "key_message": "It handles the last three kilometres",
        "proof_points": [
            {"claim": "45 km range", "source": "specs"},
            {"claim": "₹24,999", "source": "price"},
            {"claim": "8.5 inch tyres", "source": "specs"},
        ],
        "channels": ["Instagram Reels"],
        "success_metric": "CTR to the product page",
    }
    payload.update(overrides)
    return payload


def _scenes(count: int = 5):
    scenes = [{"kind": "feature", "image_index": i, "duration_seconds": 4} for i in range(count)]
    scenes[0]["kind"] = "title"
    scenes[-1]["kind"] = "cta"
    return scenes


class TestCampaignBrief:
    def test_accepts_a_valid_brief(self, brand):
        result = schemas.campaign_brief(_brief())
        assert result["target_persona"] == "urban-commuter"
        assert len(result["proof_points"]) == 3

    def test_rejects_an_unknown_persona(self, brand):
        with pytest.raises(SchemaError, match="urban-commuter"):
            schemas.campaign_brief(_brief(target_persona="cto-of-a-bank"))

    def test_rejects_too_few_proof_points(self, brand):
        with pytest.raises(SchemaError, match="at least 3"):
            schemas.campaign_brief(_brief(proof_points=[{"claim": "one", "source": "specs"}]))

    def test_normalizes_bare_string_proof_points(self, brand):
        result = schemas.campaign_brief(_brief(proof_points=["a", "b", "c"]))
        assert result["proof_points"][0] == {"claim": "a", "source": "unattributed"}

    def test_rejects_a_missing_key(self, brand):
        payload = _brief()
        del payload["success_metric"]
        with pytest.raises(SchemaError, match="success_metric"):
            schemas.campaign_brief(payload)

    def test_rejects_a_non_object(self, brand):
        with pytest.raises(SchemaError):
            schemas.campaign_brief(["not", "an", "object"])


class TestScript:
    def test_accepts_and_measures_a_valid_script(self, brand):
        result = schemas.script({"title": "Ride", "beats": _beats(word_count=20)})
        low, high = brand.content_rules["script"]["duration_seconds"]
        assert low * 0.85 <= result["estimated_duration_seconds"] <= high * 1.2
        assert result["word_count"] > 0

    def test_duration_is_recomputed_not_trusted(self, brand):
        # The model's own estimate is ignored: the word count is the fact, and
        # the voiceover and video timing are both built from it.
        result = schemas.script(
            {"title": "Ride", "beats": _beats(word_count=20), "estimated_duration_seconds": 999}
        )
        assert result["estimated_duration_seconds"] < 100

    def test_rejects_a_script_that_is_far_too_short(self, brand):
        beats = [
            {"beat": name, "line": "two words"}
            for name in ("hook", "problem", "product_reveal", "proof", "cta")
        ]
        with pytest.raises(SchemaError, match="longer"):
            schemas.script({"title": "t", "beats": beats})

    def test_rejects_a_script_that_is_far_too_long(self, brand):
        with pytest.raises(SchemaError, match="shorter"):
            schemas.script({"title": "t", "beats": _beats(word_count=60)})

    def test_rejects_wrong_beat_names(self, brand):
        beats = _beats()
        beats[1]["beat"] = "intro"
        with pytest.raises(SchemaError, match="in this order"):
            schemas.script({"title": "t", "beats": beats})

    def test_rejects_a_missing_beat(self, brand):
        with pytest.raises(SchemaError, match="exactly 5"):
            schemas.script({"title": "t", "beats": _beats()[:4]})

    def test_rejects_an_overlong_hook(self, brand):
        beats = _beats()
        beats[0]["line"] = " ".join(["word"] * 30)
        with pytest.raises(SchemaError, match="hook"):
            schemas.script({"title": "t", "beats": beats})

    def test_rejects_an_empty_line(self, brand):
        beats = _beats()
        beats[2]["line"] = "   "
        with pytest.raises(SchemaError, match="empty"):
            schemas.script({"title": "t", "beats": beats})

    def test_normalizes_beat_name_spacing_and_case(self, brand):
        beats = _beats(word_count=20)
        beats[2]["beat"] = "Product Reveal"
        assert schemas.script({"title": "t", "beats": beats})["beats"][2]["beat"] == "product_reveal"


class TestCaption:
    def test_accepts_a_valid_caption(self, brand):
        result = schemas.caption(
            {"caption": "Short opener\n\nBody copy here.", "first_line": "x", "cta": "Shop now"}
        )
        assert result["char_count"] == len(result["caption"])

    def test_first_line_is_derived_from_the_caption_not_the_claim(self, brand):
        result = schemas.caption(
            {"caption": "Real opener\n\nBody.", "first_line": "something else", "cta": "Go"}
        )
        assert result["first_line"] == "Real opener"

    def test_rejects_hashtags_in_the_caption(self, brand):
        with pytest.raises(SchemaError, match="hashtags"):
            schemas.caption({"caption": "Nice board #radboards", "cta": "Go"})

    def test_rejects_an_overlong_first_line(self, brand):
        limit = brand.content_rules["caption"]["first_line_max_chars"]
        with pytest.raises(SchemaError, match="first line"):
            schemas.caption({"caption": "x" * (limit + 5) + "\nbody", "cta": "Go"})

    def test_rejects_an_overlong_caption(self, brand):
        limit = brand.content_rules["caption"]["max_chars"]
        with pytest.raises(SchemaError, match="characters"):
            schemas.caption({"caption": "word " * limit, "cta": "Go"})

    def test_requires_a_cta_when_the_brand_does(self, brand):
        assert brand.content_rules["caption"]["cta_required"] is True
        with pytest.raises(SchemaError, match="cta"):
            schemas.caption({"caption": "Opener\n\nBody."})


class TestHashtags:
    def test_normalizes_case_spacing_and_missing_hash(self, brand):
        result = schemas.hashtags(
            {"hashtags": ["#Ride To Work", "HOVERboard", "#last-mile", "#a", "#b", "#c", "#d", "#e"]}
        )
        assert "#ridetowork" in result["hashtags"]
        assert "#hoverboard" in result["hashtags"]
        assert "#lastmile" in result["hashtags"]

    def test_always_include_is_added_when_missing(self, brand):
        required = brand.content_rules["hashtags"]["always_include"][0]
        result = schemas.hashtags({"hashtags": [f"#t{i}" for i in range(9)]})
        assert result["hashtags"][0] == required

    def test_banned_tags_are_dropped(self, brand):
        result = schemas.hashtags({"hashtags": ["#viral", "#trending"] + [f"#t{i}" for i in range(9)]})
        assert "#viral" not in result["hashtags"]
        assert "#trending" not in result["hashtags"]

    def test_duplicates_are_dropped(self, brand):
        result = schemas.hashtags({"hashtags": ["#same"] * 4 + [f"#t{i}" for i in range(8)]})
        assert result["hashtags"].count("#same") == 1

    def test_count_is_capped_at_the_brand_maximum(self, brand):
        high = brand.content_rules["hashtags"]["count"][1]
        result = schemas.hashtags({"hashtags": [f"#t{i}" for i in range(40)]})
        assert len(result["hashtags"]) == high

    def test_rejects_too_few_usable_tags(self, brand):
        with pytest.raises(SchemaError, match="must contain"):
            schemas.hashtags({"hashtags": ["#one", "#two"]})


class TestVideoPlan:
    def test_accepts_a_valid_plan(self, brand):
        result = schemas.video_plan({"scenes": _scenes()}, image_count=4)
        assert len(result["scenes"]) == 5
        assert result["total_duration_seconds"] == pytest.approx(20.0)

    def test_image_index_wraps_instead_of_failing(self, brand):
        result = schemas.video_plan({"scenes": _scenes()}, image_count=2)
        assert all(0 <= scene["image_index"] < 2 for scene in result["scenes"])

    def test_image_index_is_zero_when_there_are_no_images(self, brand):
        result = schemas.video_plan({"scenes": _scenes()}, image_count=0)
        assert all(scene["image_index"] == 0 for scene in result["scenes"])

    def test_unknown_kind_falls_back_to_feature(self, brand):
        scenes = _scenes()
        scenes[2]["kind"] = "montage"
        result = schemas.video_plan({"scenes": scenes}, image_count=3)
        assert result["scenes"][2]["kind"] == "feature"

    def test_numeric_strings_are_parsed(self, brand):
        scenes = _scenes()
        scenes[1]["duration_seconds"] = "4.5 seconds"
        result = schemas.video_plan({"scenes": scenes}, image_count=3)
        assert result["scenes"][1]["duration_seconds"] == 4.5

    def test_rejects_a_plan_not_starting_with_a_title(self, brand):
        scenes = _scenes()
        scenes[0]["kind"] = "feature"
        with pytest.raises(SchemaError, match="title"):
            schemas.video_plan({"scenes": scenes}, image_count=3)

    def test_rejects_a_plan_not_ending_with_a_cta(self, brand):
        scenes = _scenes()
        scenes[-1]["kind"] = "feature"
        with pytest.raises(SchemaError, match="cta"):
            schemas.video_plan({"scenes": scenes}, image_count=3)

    def test_rejects_too_few_scenes(self, brand):
        with pytest.raises(SchemaError, match="scene objects"):
            schemas.video_plan({"scenes": _scenes(2)}, image_count=3)

    def test_malformed_spec_pills_are_dropped_not_fatal(self, brand):
        scenes = _scenes()
        scenes[2]["spec_pills"] = [{"label": "Range", "value": "45 km"}, {"oops": 1}, "nope"]
        result = schemas.video_plan({"scenes": scenes}, image_count=3)
        assert result["scenes"][2]["spec_pills"] == [{"label": "Range", "value": "45 km"}]

    def test_spec_pills_are_capped(self, brand):
        scenes = _scenes()
        scenes[2]["spec_pills"] = [{"label": f"l{i}", "value": f"v{i}"} for i in range(9)]
        result = schemas.video_plan({"scenes": scenes}, image_count=3)
        assert len(result["scenes"][2]["spec_pills"]) == schemas.MAX_SPEC_PILLS

    def test_beat_names_fill_in_from_the_script(self, brand):
        beats = ["hook", "problem", "product_reveal", "proof", "cta"]
        result = schemas.video_plan({"scenes": _scenes()}, image_count=3, beats=beats)
        assert [scene["beat"] for scene in result["scenes"]] == beats
