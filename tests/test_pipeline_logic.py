"""Tests for pipeline logic that isn't a model call: feedback scoping, revision
context, timing maths and scene building.

The stale-feedback case below is a regression test for a real bug: a rejection
was previously re-applied to every subsequent run of that product forever,
because the code looked for "the newest Rejected version" rather than "the
current version, if it was rejected".
"""
from __future__ import annotations

import json

import pytest

from graph import nodes


class TestScopeExpansion:
    def test_no_selection_means_regenerate_everything(self):
        assert nodes._expand_scope(set()) is None

    def test_selecting_everything_means_regenerate_everything(self):
        assert nodes._expand_scope(set(nodes.NODE_KEYS)) is None

    def test_a_leaf_node_cascades_to_nothing(self):
        assert nodes._expand_scope({"caption"}) == {"caption"}

    def test_script_cascades_to_its_consumers(self):
        # caption, hashtags and video_plan all embed the script in their prompt,
        # so regenerating the script without them would pair new narration with
        # copy written against the old one.
        assert nodes._expand_scope({"script"}) == {"script", "caption", "hashtags", "video_plan"}

    def test_campaign_brief_cascades_to_all(self):
        assert nodes._expand_scope({"campaign_brief"}) is None

    def test_two_leaves_stay_two_leaves(self):
        assert nodes._expand_scope({"caption", "hashtags"}) == {"caption", "hashtags"}


class TestCarryForward:
    def _state(self, scope, carry):
        return {"revision": {"scope": scope, "carry_forward": carry}}

    def test_in_scope_nodes_are_regenerated(self):
        state = self._state({"caption"}, {"caption": {"caption": "old"}})
        assert nodes._carried_forward_payload(state, "caption") is None

    def test_out_of_scope_nodes_are_reused(self):
        state = self._state({"caption"}, {"hashtags": {"hashtags": ["#a"]}})
        carried = nodes._carried_forward_payload(state, "hashtags")
        assert carried["hashtags"] == ["#a"]
        assert carried["_source"] == nodes.SOURCE_CARRIED

    def test_full_scope_regenerates_everything(self):
        state = self._state(None, {"hashtags": {"hashtags": ["#a"]}})
        assert nodes._carried_forward_payload(state, "hashtags") is None

    def test_nothing_to_carry_falls_through_to_generation(self):
        state = self._state({"caption"}, {})
        assert nodes._carried_forward_payload(state, "hashtags") is None

    def test_no_revision_falls_through_to_generation(self):
        assert nodes._carried_forward_payload({}, "hashtags") is None


class TestRevisionContext:
    """`_load_revision_context` must only act on the *current* version."""

    def _make_version(self, tmp_path, product_id, number, status, feedback=None, scope=None):
        from database.repository import create_version, update_version_status

        version = create_version(product_id, None)
        directory = tmp_path / f"v{number}"
        directory.mkdir(exist_ok=True)
        (directory / nodes.META_FILENAME).write_text(
            json.dumps({"content": {"caption": {"caption": f"copy for v{number}"}}}),
            encoding="utf-8",
        )
        from database.connection import connection_scope

        with connection_scope() as conn:
            conn.execute(
                "UPDATE versions SET output_dir = ? WHERE id = ?", (str(directory), version.id)
            )
        if status != "Review":
            update_version_status(version.id, status, feedback, scope)
        return version

    def test_no_versions_means_no_revision(self, temp_db):
        from database.repository import create_product

        product = create_product("Board", "https://example.com/products/board")
        assert nodes._load_revision_context(product.id) is None

    def test_a_rejected_current_version_drives_the_next_run(self, temp_db, tmp_path):
        from database.repository import create_product

        product = create_product("Board", "https://example.com/products/board")
        self._make_version(tmp_path, product.id, 1, "Rejected", "Caption is too corporate", "caption")

        context = nodes._load_revision_context(product.id)
        assert context["feedback"] == "Caption is too corporate"
        assert context["scope"] == {"caption"}
        assert context["carry_forward"]["caption"]["caption"] == "copy for v1"

    def test_an_approved_current_version_carries_no_feedback(self, temp_db, tmp_path):
        from database.repository import create_product

        product = create_product("Board", "https://example.com/products/board")
        self._make_version(tmp_path, product.id, 1, "Approved")
        assert nodes._load_revision_context(product.id) is None

    def test_an_already_answered_rejection_is_not_reapplied(self, temp_db, tmp_path):
        """Regression: v1 rejected, v2 generated in response. A third run must
        not rewrite to v1's feedback all over again."""
        from database.repository import create_product

        product = create_product("Board", "https://example.com/products/board")
        self._make_version(tmp_path, product.id, 1, "Rejected", "Too corporate", "caption")
        self._make_version(tmp_path, product.id, 2, "Review")

        assert nodes._load_revision_context(product.id) is None

    def test_the_most_recent_rejection_wins(self, temp_db, tmp_path):
        from database.repository import create_product

        product = create_product("Board", "https://example.com/products/board")
        self._make_version(tmp_path, product.id, 1, "Rejected", "First complaint", "caption")
        self._make_version(tmp_path, product.id, 2, "Rejected", "Second complaint", "hashtags")

        context = nodes._load_revision_context(product.id)
        assert context["feedback"] == "Second complaint"
        assert context["scope"] == {"hashtags"}


class TestSceneTiming:
    """`scale_scenes_to_audio` fits the picture to the real narration length."""

    def _scenes(self, durations):
        from media.movie import Scene

        return [Scene(kind="feature", duration=d) for d in durations]

    def test_scenes_are_stretched_to_match_longer_audio(self):
        from media.movie import scale_scenes_to_audio

        scenes = self._scenes([4.0, 4.0, 4.0])
        scale_scenes_to_audio(scenes, target_duration=24.0, transition=0.0)
        assert sum(s.duration for s in scenes) == pytest.approx(24.0)

    def test_scenes_are_compressed_to_match_shorter_audio(self):
        from media.movie import scale_scenes_to_audio

        scenes = self._scenes([10.0, 10.0, 10.0])
        scale_scenes_to_audio(scenes, target_duration=15.0, transition=0.0)
        assert sum(s.duration for s in scenes) == pytest.approx(15.0)

    def test_transition_overlap_is_accounted_for(self):
        from media.movie import scale_scenes_to_audio

        scenes = self._scenes([5.0, 5.0, 5.0])
        transition = 0.5
        scale_scenes_to_audio(scenes, target_duration=18.0, transition=transition)
        timeline = sum(s.duration for s in scenes) - transition * (len(scenes) - 1)
        assert timeline == pytest.approx(18.0)

    def test_no_scenes_is_a_no_op(self):
        from media.movie import scale_scenes_to_audio

        scale_scenes_to_audio([], target_duration=10.0, transition=0.5)  # must not raise

    def test_a_zero_target_is_ignored(self):
        from media.movie import scale_scenes_to_audio

        scenes = self._scenes([4.0, 4.0])
        scale_scenes_to_audio(scenes, target_duration=0.0, transition=0.0)
        assert [s.duration for s in scenes] == [4.0, 4.0]

    def test_scenes_never_go_below_the_minimum(self):
        from media.movie import MIN_SCENE_SECONDS, scale_scenes_to_audio

        scenes = self._scenes([10.0] * 6)
        scale_scenes_to_audio(scenes, target_duration=2.0, transition=0.0)
        assert all(s.duration >= MIN_SCENE_SECONDS for s in scenes)


class TestBuildScenes:
    def test_an_empty_plan_still_yields_a_renderable_film(self, brand):
        from media.movie import build_scenes

        scenes = build_scenes({"scenes": []}, brand)
        assert [s.kind for s in scenes] == ["title", "cta"]

    def test_pan_direction_alternates(self, brand):
        from media.movie import build_scenes

        plan = {"scenes": [{"kind": "feature", "duration_seconds": 4} for _ in range(4)]}
        directions = [s.pan_direction for s in build_scenes(plan, brand)]
        assert directions == [1, -1, 1, -1]

    def test_non_dict_entries_are_skipped(self, brand):
        from media.movie import build_scenes

        plan = {"scenes": [{"kind": "title", "duration_seconds": 3}, "junk", None]}
        assert len(build_scenes(plan, brand)) == 1
