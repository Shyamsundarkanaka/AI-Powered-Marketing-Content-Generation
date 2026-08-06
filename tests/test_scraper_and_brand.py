"""Tests for Shopify response parsing, brand validation and the TTS chain.

No network: `scrape_product` is driven with recorded-shape payloads, which is
what the parsing logic actually needs to be correct about.
"""
from __future__ import annotations

import wave

import pytest

from brand.loader import BrandDefinitionError, validate_brand_document
from scraper import shopify
from scraper.shopify import ScrapeError, json_url, scrape_product


class FakeResponse:
    def __init__(self, payload, status_code=200, is_json=True):
        self._payload = payload
        self.status_code = status_code
        self._is_json = is_json

    def json(self):
        if not self._is_json:
            raise ValueError("not json")
        return self._payload


def install_response(monkeypatch, response):
    class FakeSession:
        def get(self, url, timeout=None):
            if isinstance(response, Exception):
                raise response
            return response

    monkeypatch.setattr(shopify, "http_session", lambda: FakeSession())


PRODUCT = {
    "product": {
        "title": "8.5 Off-Road Pro",
        "body_html": (
            "<p>Built for potholes.</p>"
            "<table><tr><td>Range</td><td>45 km</td></tr>"
            "<tr><td>Motor</td><td>700W</td></tr></table>"
            "<p>Ships in a box.</p>"
        ),
        "variants": [
            {"price": "29999.00", "compare_at_price": "34999.00", "available": True},
        ],
        "images": [{"src": "https://cdn/1.jpg"}, {"src": "https://cdn/2.jpg"}, {"no_src": 1}],
    }
}


class TestJsonUrl:
    def test_appends_the_json_suffix(self):
        assert json_url("https://s.com/products/x") == "https://s.com/products/x.json"

    def test_strips_a_trailing_slash(self):
        assert json_url("https://s.com/products/x/") == "https://s.com/products/x.json"

    def test_drops_query_and_fragment(self):
        assert json_url("https://s.com/products/x?v=1#buy") == "https://s.com/products/x.json"

    def test_is_idempotent(self):
        assert json_url("https://s.com/products/x.json") == "https://s.com/products/x.json"

    @pytest.mark.parametrize("url", ["", "not a url", "/products/x"])
    def test_rejects_a_non_absolute_url(self, url):
        with pytest.raises(ScrapeError):
            json_url(url)


class TestScrapeProduct:
    def test_parses_a_full_product(self, monkeypatch):
        install_response(monkeypatch, FakeResponse(PRODUCT))
        data = scrape_product("https://s.com/products/x")

        assert data["title"] == "8.5 Off-Road Pro"
        assert data["price"] == 29999.0
        assert data["compare_at_price"] == 34999.0
        assert data["specs"] == {"Range": "45 km", "Motor": "700W"}
        assert data["image_urls"] == ["https://cdn/1.jpg", "https://cdn/2.jpg"]

    def test_spec_table_text_is_removed_from_the_description(self, monkeypatch):
        install_response(monkeypatch, FakeResponse(PRODUCT))
        description = scrape_product("https://s.com/products/x")["description_text"]
        assert "Built for potholes." in description
        assert "700W" not in description  # would otherwise be duplicated into prose

    def test_picks_the_cheapest_available_variant(self, monkeypatch):
        payload = {"product": dict(PRODUCT["product"])}
        payload["product"]["variants"] = [
            {"price": "99999.00", "available": False},
            {"price": "24999.00", "available": True},
            {"price": "27999.00", "available": True},
        ]
        install_response(monkeypatch, FakeResponse(payload))
        assert scrape_product("https://s.com/products/x")["price"] == 24999.0

    def test_falls_back_when_nothing_is_available(self, monkeypatch):
        payload = {"product": dict(PRODUCT["product"])}
        payload["product"]["variants"] = [{"price": "500.00", "available": False}]
        install_response(monkeypatch, FakeResponse(payload))
        assert scrape_product("https://s.com/products/x")["price"] == 500.0

    def test_unparseable_price_becomes_none_rather_than_failing(self, monkeypatch):
        payload = {"product": dict(PRODUCT["product"])}
        payload["product"]["variants"] = [{"price": "call us"}]
        install_response(monkeypatch, FakeResponse(payload))
        assert scrape_product("https://s.com/products/x")["price"] is None

    def test_missing_images_is_not_fatal(self, monkeypatch):
        payload = {"product": dict(PRODUCT["product"])}
        payload["product"]["images"] = []
        install_response(monkeypatch, FakeResponse(payload))
        assert scrape_product("https://s.com/products/x")["image_urls"] == []

    def test_http_error_raises_scrape_error(self, monkeypatch):
        install_response(monkeypatch, FakeResponse(None, status_code=404))
        with pytest.raises(ScrapeError, match="404"):
            scrape_product("https://s.com/products/x")

    def test_non_json_response_raises_scrape_error(self, monkeypatch):
        install_response(monkeypatch, FakeResponse(None, is_json=False))
        with pytest.raises(ScrapeError, match="did not return JSON"):
            scrape_product("https://s.com/products/x")

    def test_missing_product_object_raises_scrape_error(self, monkeypatch):
        install_response(monkeypatch, FakeResponse({"errors": "Not Found"}))
        with pytest.raises(ScrapeError, match="No usable"):
            scrape_product("https://s.com/products/x")

    def test_connection_error_raises_scrape_error(self, monkeypatch):
        install_response(monkeypatch, ConnectionError("reset"))
        with pytest.raises(ScrapeError, match="failed"):
            scrape_product("https://s.com/products/x")


class TestBrandValidation:
    def test_the_shipped_brand_file_is_valid(self, brand):
        validate_brand_document(brand.raw)

    def test_a_missing_section_is_reported(self, brand):
        broken = {key: value for key, value in brand.raw.items() if key != "compliance"}
        with pytest.raises(BrandDefinitionError, match="compliance"):
            validate_brand_document(broken)

    def test_all_problems_are_reported_at_once(self, brand):
        broken = {key: value for key, value in brand.raw.items()
                  if key not in ("compliance", "visual")}
        with pytest.raises(BrandDefinitionError) as excinfo:
            validate_brand_document(broken)
        assert "compliance" in str(excinfo.value)
        assert "visual" in str(excinfo.value)

    def test_an_inverted_range_is_rejected(self, brand):
        import copy

        broken = copy.deepcopy(brand.raw)
        broken["content_rules"]["script"]["duration_seconds"] = [40, 10]
        with pytest.raises(BrandDefinitionError, match="low <= high"):
            validate_brand_document(broken)

    def test_a_persona_missing_an_id_is_rejected(self, brand):
        import copy

        broken = copy.deepcopy(brand.raw)
        del broken["audience"]["personas"][0]["id"]
        with pytest.raises(BrandDefinitionError, match="personas"):
            validate_brand_document(broken)

    def test_a_non_mapping_is_rejected(self):
        with pytest.raises(BrandDefinitionError):
            validate_brand_document(["not", "a", "brand"])


class TestVoiceover:
    def test_silence_is_written_at_the_requested_length(self, tmp_path):
        from media.voice import write_silence

        path = tmp_path / "v.wav"
        write_silence(path, 3.0)
        with wave.open(str(path), "rb") as handle:
            assert handle.getnframes() / handle.getframerate() == pytest.approx(3.0, abs=0.01)

    def test_spoken_text_joins_only_the_lines(self):
        from media.voice import spoken_text_from_script

        script = {"beats": [
            {"line": "First line.", "on_screen": "IGNORED"},
            {"line": "Second line.", "on_screen": "ALSO IGNORED"},
        ]}
        assert spoken_text_from_script(script) == "First line. Second line."

    def test_duration_prefers_the_scripts_measured_estimate(self, brand):
        from media.voice import estimate_duration

        assert estimate_duration("two words", {"estimated_duration_seconds": 27.5}) == 27.5

    def test_duration_falls_back_to_the_brand_speaking_rate(self, brand):
        from media.voice import estimate_duration

        wps = brand.content_rules["script"]["words_per_second"]
        assert estimate_duration(" ".join(["word"] * 24), None) == pytest.approx(24 / wps)

    def test_falls_back_to_silence_when_every_engine_fails(self, tmp_path, monkeypatch):
        from media import voice

        monkeypatch.setattr(voice, "configured_engines", lambda: ["piper"])
        monkeypatch.setattr(
            voice, "ENGINES",
            {"piper": lambda text, path: (_ for _ in ()).throw(voice.TTSUnavailable("no model"))},
        )
        result = voice.generate_voiceover(
            {"beats": [{"line": "hello"}], "estimated_duration_seconds": 5.0}, tmp_path / "v.wav"
        )
        assert result.is_silent
        assert result.engine == voice.SILENCE
        assert result.path.exists()
        assert any("no model" in warning for warning in result.warnings)

    def test_a_working_engine_is_used_and_reported(self, tmp_path, monkeypatch):
        from media import voice

        def fake_engine(text, path):
            voice.write_silence(path, 2.0)  # stand-in for real synthesis

        monkeypatch.setattr(voice, "configured_engines", lambda: ["fake"])
        monkeypatch.setattr(voice, "ENGINES", {"fake": fake_engine})
        result = voice.generate_voiceover({"beats": [{"line": "hi"}]}, tmp_path / "v.wav")

        assert result.engine == "fake"
        assert not result.is_silent
        assert result.duration_seconds == pytest.approx(2.0, abs=0.05)

    def test_a_failing_engine_leaves_no_partial_file_behind(self, tmp_path, monkeypatch):
        from media import voice

        def broken_engine(text, path):
            path.write_bytes(b"")  # truncated output
            raise RuntimeError("crashed mid-write")

        def good_engine(text, path):
            voice.write_silence(path, 1.5)

        monkeypatch.setattr(voice, "configured_engines", lambda: ["broken", "good"])
        monkeypatch.setattr(voice, "ENGINES", {"broken": broken_engine, "good": good_engine})
        result = voice.generate_voiceover({"beats": [{"line": "hi"}]}, tmp_path / "v.wav")

        assert result.engine == "good"
        assert list(tmp_path.glob("*.partial.wav")) == []

    def test_no_spoken_lines_yields_silence(self, tmp_path):
        from media import voice

        result = voice.generate_voiceover({"beats": []}, tmp_path / "v.wav")
        assert result.is_silent
