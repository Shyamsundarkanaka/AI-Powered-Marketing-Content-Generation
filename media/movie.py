"""Renders a branded vertical marketing video from a video plan and product photos.

Design notes, because the shape of this module is deliberate:

**Everything visual comes from `brand.yaml`.** Colours, fonts, safe areas, Ken
Burns amounts, transition length, card durations — all read at render time.
There is no hard-coded hex value below. Changing the brand changes the film.

**The whole video is one `VideoClip` with a hand-written frame function.**
The obvious alternative — a stack of MoviePy effects and `concatenate_videoclips`
— gives up control of exactly the things that make short-form video read as
professional rather than as a slideshow: eased (not linear) camera movement,
text that stays pinned while the image behind it moves, and dissolves that
blend at a known curve. Owning the timeline makes those exact, deterministic and
testable, and costs one clearly-written `frame_at()`.

**Text is rendered with Pillow, not MoviePy's `TextClip`.** That avoids the
ImageMagick/font-discovery failure modes entirely, and buys letter-spacing,
drop shadows, wrapped measurement and rounded pill backgrounds — none of which
`TextClip` does well.

**Per-scene work is done once.** Each scene bakes a high-resolution background
canvas and a static text overlay up front; per frame the renderer only crops,
resizes and alpha-composites. That is what keeps a 30-second 1080x1920 render in
the tens of seconds rather than the minutes.

Standalone use:

    python -m media.movie --product-id 5 --out output/demo.mp4
"""
from __future__ import annotations

import hashlib
import logging
import math
import os
import wave
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from brand.loader import Brand, hex_to_rgba, load_brand
from config.http import http_session
from media import voice
from config.settings import (
    ASSET_CACHE_DIR,
    HTTP_TIMEOUT_SECONDS,
    VIDEO_ASPECT,
    VIDEO_FPS,
    VIDEO_RENDER_THREADS,
)

logger = logging.getLogger(__name__)

# --- constants ---------------------------------------------------------------

ASPECT_PRESETS: dict[str, tuple[int, int]] = {
    "vertical": (1080, 1920),
    "square": (1080, 1080),
    "landscape": (1920, 1080),
}

FONT_SEARCH_DIRS = (
    Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts",
    Path("/usr/share/fonts"),
    Path("/usr/local/share/fonts"),
    Path("/Library/Fonts"),
    Path("/System/Library/Fonts"),
    Path.home() / ".fonts",
)

MIN_SCENE_SECONDS = 1.2
PILL_HEIGHT = 100          # tall enough for an accent label above a display value
AUDIO_TOLERANCE_SECONDS = 0.05


# --- geometry helpers --------------------------------------------------------

def ease_in_out_cubic(p: float) -> float:
    """Smooth acceleration and deceleration.

    Linear interpolation is what makes a Ken Burns move read as a zoom artifact;
    easing is what makes it read as a camera.
    """
    p = min(max(p, 0.0), 1.0)
    return 4 * p * p * p if p < 0.5 else 1 - pow(-2 * p + 2, 3) / 2


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def cover_box(src: tuple[int, int], dst: tuple[int, int]) -> tuple[int, int]:
    """Size that fills `dst` entirely, preserving aspect (may overflow)."""
    scale = max(dst[0] / src[0], dst[1] / src[1])
    return (max(int(round(src[0] * scale)), dst[0]), max(int(round(src[1] * scale)), dst[1]))


def contain_box(src: tuple[int, int], dst: tuple[int, int]) -> tuple[int, int]:
    """Size that fits inside `dst`, preserving aspect."""
    scale = min(dst[0] / src[0], dst[1] / src[1])
    return (max(int(round(src[0] * scale)), 1), max(int(round(src[1] * scale)), 1))


# --- product cutout ----------------------------------------------------------

WHITE_MIN_CHANNEL = 232      # a background pixel is bright...
WHITE_MAX_SPREAD = 24        # ...and close to neutral
CUTOUT_MASK_WIDTH = 256      # flood fill runs at this width, then upscales
CUTOUT_MAX_ITERATIONS = 600
CUTOUT_MIN_COVERAGE = 0.02   # below this the image probably isn't a catalog shot
CUTOUT_MAX_COVERAGE = 0.93   # above this we'd be erasing the product itself


def cutout_product(image: Image.Image) -> Optional[Image.Image]:
    """Knock the white studio backdrop out of a catalogue product shot.

    Shopify product photography is shot on pure white. Pasted as a rectangle it
    reads as a sticker slapped onto the frame, and it destroys contrast for any
    text beneath it. Removing it lets the product float on the branded
    background, which is the single biggest visual difference in the render.

    The white must be *background* white, not white that belongs to the product
    (these boards have white graffiti prints). So instead of thresholding
    globally, the white region connected to the image border is flood-filled —
    at 1/4 scale, because the mask edge gets feathered anyway and a full-res
    flood fill in Python is far too slow.

    Returns an RGBA image, or None when the heuristic doesn't apply.
    """
    rgb = np.asarray(image.convert("RGB"), dtype=np.int16)
    is_white = (rgb.min(axis=2) >= WHITE_MIN_CHANNEL) & (
        (rgb.max(axis=2) - rgb.min(axis=2)) <= WHITE_MAX_SPREAD
    )
    if is_white.mean() < CUTOUT_MIN_COVERAGE or is_white.mean() > CUTOUT_MAX_COVERAGE:
        return None

    height, width = is_white.shape
    scale = max(width // CUTOUT_MASK_WIDTH, 1)
    small = np.asarray(
        Image.fromarray((is_white * 255).astype(np.uint8)).resize(
            (max(width // scale, 8), max(height // scale, 8)), Image.NEAREST
        )
    ) > 127

    # Seed from every border pixel that is white, then grow while staying white.
    reached = np.zeros_like(small)
    reached[0, :] = small[0, :]
    reached[-1, :] = small[-1, :]
    reached[:, 0] = small[:, 0]
    reached[:, -1] = small[:, -1]
    if not reached.any():
        return None

    for _ in range(CUTOUT_MAX_ITERATIONS):
        grown = reached.copy()
        grown[1:, :] |= reached[:-1, :]
        grown[:-1, :] |= reached[1:, :]
        grown[:, 1:] |= reached[:, :-1]
        grown[:, :-1] |= reached[:, 1:]
        grown &= small
        if grown.sum() == reached.sum():
            break
        reached = grown

    background = Image.fromarray((reached * 255).astype(np.uint8)).resize(
        (width, height), Image.BILINEAR
    )
    alpha = Image.eval(background, lambda v: 255 - v).filter(ImageFilter.GaussianBlur(1.6))

    if np.asarray(alpha).mean() < 12:  # nothing survived — don't return an empty frame
        return None

    cut = image.convert("RGBA")
    cut.putalpha(alpha)
    return cut.crop(cut.getbbox() or (0, 0, width, height))


# --- fonts -------------------------------------------------------------------

class FontBook:
    """Resolves brand font roles to real font files, with a working fallback.

    A missing font must never fail a render — the worst acceptable outcome is a
    slightly different typeface, so the candidate chain ends at Pillow's bundled
    default.
    """

    def __init__(self, brand: Brand) -> None:
        self._brand = brand
        self._cache: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}
        self._resolved: dict[str, Optional[Path]] = {}

    def _resolve_path(self, role: str) -> Optional[Path]:
        if role in self._resolved:
            return self._resolved[role]

        found: Optional[Path] = None
        for candidate in self._brand.font_candidates(role):
            direct = Path(candidate)
            if direct.is_file():
                found = direct
                break
            for directory in FONT_SEARCH_DIRS:
                if not directory.is_dir():
                    continue
                probe = directory / candidate
                if probe.is_file():
                    found = probe
                    break
                # Linux nests fonts a few levels deep under the family name.
                match = next(directory.rglob(candidate), None)
                if match is not None:
                    found = match
                    break
            if found:
                break

        if found is None:
            logger.warning(
                "No font file found for role %r (tried %s); falling back to the Pillow default.",
                role,
                ", ".join(self._brand.font_candidates(role)),
            )
        self._resolved[role] = found
        return found

    def get(self, role: str, size: int) -> ImageFont.FreeTypeFont:
        key = (role, size)
        if key not in self._cache:
            path = self._resolve_path(role)
            if path is not None:
                self._cache[key] = ImageFont.truetype(str(path), size)
            else:
                self._cache[key] = ImageFont.load_default(size=size)
        return self._cache[key]

    def tracking(self, role: str) -> int:
        return self._brand.tracking(role)


# --- text drawing ------------------------------------------------------------

def text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, tracking: int) -> float:
    """Measured width of tracked text.

    Measured the same way `draw_tracked_text` draws it — character by character.
    Measuring the whole string in one call would include kerning pairs that the
    per-character draw never applies, so the measurement would come out narrower
    than the result and pills would overflow their backgrounds.
    """
    if not text:
        return 0.0
    if tracking == 0:
        return draw.textlength(text, font=font)
    return sum(draw.textlength(char, font=font) for char in text) + tracking * (len(text) - 1)


def draw_tracked_text(
    draw: ImageDraw.ImageDraw,
    xy: tuple[float, float],
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: tuple[int, int, int, int],
    tracking: int = 0,
    shadow: Optional[tuple[int, int, int, int]] = None,
    shadow_offset: tuple[int, int] = (0, 3),
) -> None:
    """Draw text with letter-spacing and an optional drop shadow.

    Pillow has no tracking support, so characters are placed individually. The
    shadow is what keeps display type legible over the lighter parts of product
    photography, which is shot on white.
    """
    if not text:
        return

    def _run(origin: tuple[float, float], colour: tuple[int, int, int, int]) -> None:
        x, y = origin
        if tracking == 0:
            draw.text((x, y), text, font=font, fill=colour)
            return
        for char in text:
            draw.text((x, y), char, font=font, fill=colour)
            x += draw.textlength(char, font=font) + tracking

    if shadow is not None:
        _run((xy[0] + shadow_offset[0], xy[1] + shadow_offset[1]), shadow)
    _run(xy, fill)


def wrap_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    max_width: float,
    tracking: int = 0,
    max_lines: int = 3,
) -> list[str]:
    """Greedy word wrap against measured width, truncating with an ellipsis."""
    words = (text or "").split()
    if not words:
        return []

    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        probe = f"{current} {word}"
        if text_width(draw, probe, font, tracking) <= max_width:
            current = probe
        else:
            lines.append(current)
            current = word
            if len(lines) == max_lines:
                break
    if len(lines) < max_lines:
        lines.append(current)

    if len(lines) == max_lines:
        consumed = sum(len(line.split()) for line in lines)
        if consumed < len(words):
            last = lines[-1]
            while last and text_width(draw, last + "…", font, tracking) > max_width:
                last = last.rsplit(" ", 1)[0] if " " in last else last[:-1]
            lines[-1] = last + "…"
    return lines


def line_height(font: ImageFont.FreeTypeFont, leading: float = 1.18) -> int:
    ascent, descent = font.getmetrics()
    return int(round((ascent + descent) * leading))


# --- image sourcing ----------------------------------------------------------

class ImageLibrary:
    """Fetches and caches product photography by URL.

    Downloads land in `ASSET_CACHE_DIR` keyed by URL hash, so re-rendering a
    version (or rendering v2 after a rejection) costs no network at all.
    """

    def __init__(self, urls: Sequence[str], cache_dir: Path = ASSET_CACHE_DIR) -> None:
        self._urls = list(urls)
        self._cache_dir = Path(cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._loaded: dict[int, Optional[Image.Image]] = {}
        self.warnings: list[str] = []

    def __len__(self) -> int:
        return len(self._urls)

    def _cache_path(self, url: str) -> Path:
        digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:20]
        suffix = Path(url.split("?", 1)[0]).suffix or ".jpg"
        return self._cache_dir / f"{digest}{suffix}"

    def _download(self, url: str) -> Optional[Path]:
        path = self._cache_path(url)
        if path.exists() and path.stat().st_size > 0:
            return path
        try:
            response = http_session().get(url, timeout=HTTP_TIMEOUT_SECONDS)
            response.raise_for_status()
            # Write via a temp file so an interrupted download can never leave a
            # truncated image in the cache, where it would be served forever.
            scratch = path.with_suffix(path.suffix + ".part")
            scratch.write_bytes(response.content)
            scratch.replace(path)
            logger.info("Cached product image %s", path.name)
            return path
        except Exception as exc:  # noqa: BLE001 — a missing image degrades, never fails
            self.warnings.append(f"Could not fetch image {url}: {exc}")
            logger.warning("Image fetch failed for %s: %s", url, exc)
            return None

    def get(self, index: int) -> Optional[Image.Image]:
        """Load image `index`, wrapping out-of-range indices onto real ones."""
        if not self._urls:
            return None
        index = int(index) % len(self._urls)
        if index in self._loaded:
            return self._loaded[index]

        image: Optional[Image.Image] = None
        path = self._download(self._urls[index])
        if path is not None:
            try:
                image = Image.open(path).convert("RGB")
            except Exception as exc:  # noqa: BLE001
                self.warnings.append(f"Could not decode image {path.name}: {exc}")
                logger.warning("Image decode failed for %s: %s", path, exc)
        self._loaded[index] = image
        return image


# --- scenes ------------------------------------------------------------------

@dataclass
class Scene:
    """One shot: a still, a camera move, and a static text overlay."""

    kind: str                       # title | feature | spec | cta
    duration: float
    headline: str = ""
    subline: str = ""
    image_index: int = 0
    spec_pills: list[dict[str, str]] = field(default_factory=list)
    pan_direction: int = 1          # +1 / -1, alternated so the film doesn't drift
    beat: str = ""                  # script beat this scene narrates, e.g. "hook"

    @classmethod
    def from_plan(cls, raw: dict[str, Any], order: int, brand: Brand) -> "Scene":
        kind = str(raw.get("kind", "feature")).lower()
        if kind not in ("title", "feature", "spec", "cta"):
            kind = "feature"
        try:
            duration = float(raw.get("duration_seconds") or 0)
        except (TypeError, ValueError):
            duration = 0.0
        if duration < MIN_SCENE_SECONDS:
            duration = float(
                brand.video["title_card_seconds"] if kind == "title"
                else brand.video["cta_card_seconds"] if kind == "cta"
                else 4.5
            )
        pills = [
            {"label": str(p.get("label", "")), "value": str(p.get("value", ""))}
            for p in (raw.get("spec_pills") or [])
            if isinstance(p, dict)
        ][:3]
        try:
            image_index = int(raw.get("image_index") or 0)
        except (TypeError, ValueError):
            image_index = 0
        return cls(
            kind=kind,
            duration=duration,
            headline=str(raw.get("headline") or ""),
            subline=str(raw.get("subline") or ""),
            image_index=image_index,
            spec_pills=pills,
            pan_direction=1 if order % 2 == 0 else -1,
            beat=str(raw.get("beat") or "").strip(),
        )


class SceneRenderer:
    """Bakes one scene's background canvas and text overlay, then serves frames.

    The background is built at `zoom_end` resolution so that every frame is a
    *downscale* of the source — cropping into an oversampled canvas is why the
    zoom stays sharp instead of going soft at the end of the move.
    """

    def __init__(self, scene: Scene, ctx: "RenderContext") -> None:
        self.scene = scene
        self.ctx = ctx
        zoom_end = float(ctx.brand.video["ken_burns"]["zoom_end"])
        self.base_size = (
            int(math.ceil(ctx.width * zoom_end)),
            int(math.ceil(ctx.height * zoom_end)),
        )
        self._background = self._build_background()
        self._overlay = self._build_overlay()

    # -- background ----------------------------------------------------------

    def _build_background(self) -> Image.Image:
        width, height = self.base_size
        canvas = Image.new("RGB", (width, height), self.ctx.color("ink"))
        image = self.ctx.images.get(self.scene.image_index)

        if image is None:
            canvas = self._brand_gradient((width, height))
        else:
            # Two layers. A heavily blurred, darkened cover-fit crop fills the
            # frame edge to edge so there is never a letterbox; the product
            # itself sits on top, cut out of its white studio backdrop where
            # possible so it reads as an object in the frame rather than a
            # pasted rectangle.
            canvas.paste(self._backdrop(image, (width, height)), (0, 0))

            cut = cutout_product(image)
            hero_source = cut if cut is not None else image
            # The hero must clear the text block. Text is laid out upward from
            # the bottom safe edge, so capping the hero at 54% of frame height
            # from 13% down leaves the lower third free for copy even when the
            # product is a tall one (a scooter rather than a board).
            hero_box = (
                int(width * (0.96 if cut is not None else 0.90)),
                int(height * 0.54),
            )
            hero = hero_source.resize(contain_box(hero_source.size, hero_box), Image.LANCZOS)
            position = ((width - hero.width) // 2, int(height * 0.13))
            if cut is not None:
                shadow = self._contact_shadow(hero, position, (width, height))
                canvas.paste(shadow, (0, 0), shadow)   # mask=shadow, or its alpha is ignored
                canvas.paste(hero, position, hero)
            else:
                canvas.paste(hero, position)

        scrim = self._scrim((width, height))
        canvas.paste(scrim, (0, 0), scrim)
        return canvas

    def _backdrop(self, image: Image.Image, size: tuple[int, int]) -> Image.Image:
        width, height = size
        filled = image.resize(cover_box(image.size, size), Image.LANCZOS)
        left = (filled.width - width) // 2
        top = (filled.height - height) // 2
        filled = filled.crop((left, top, left + width, top + height))
        filled = filled.filter(ImageFilter.GaussianBlur(radius=max(width // 24, 14)))
        return Image.blend(filled, Image.new("RGB", size, self.ctx.color("ink")), 0.45)

    def _contact_shadow(
        self, hero: Image.Image, position: tuple[int, int], size: tuple[int, int]
    ) -> Image.Image:
        """A soft drop shadow under the cut-out product, so it sits in the frame.

        Without it a cutout looks like it is hovering in front of a photograph
        of somewhere else, which is exactly what it is.
        """
        layer = Image.new("RGBA", size, (0, 0, 0, 0))
        shadow = Image.new("RGBA", hero.size, (0, 0, 0, 0))
        shadow.putalpha(hero.getchannel("A").point(lambda v: int(v * 0.55)))
        layer.paste(shadow, (position[0], position[1] + int(size[1] * 0.012)), shadow)
        return layer.filter(ImageFilter.GaussianBlur(radius=max(size[0] // 45, 10)))

    def _brand_gradient(self, size: tuple[int, int]) -> Image.Image:
        """Fallback background when no usable photography exists."""
        width, height = size
        ink = self.ctx.color("ink")
        surface = self.ctx.color("surface")
        ramp = Image.new("RGB", (1, height))
        pixels = ramp.load()
        for y in range(height):
            t = y / max(height - 1, 1)
            pixels[0, y] = tuple(int(round(lerp(surface[i], ink[i], t))) for i in range(3))
        return ramp.resize((width, height), Image.BILINEAR)

    def _scrim(self, size: tuple[int, int]) -> Image.Image:
        """Bottom-up darkening so text always has contrast beneath it."""
        width, height = size
        top_rgba = hex_to_rgba(self.ctx.brand.visual["gradient_scrim"][1], 0)
        bottom_rgba = hex_to_rgba(self.ctx.brand.visual["gradient_scrim"][0], 220)
        ramp = Image.new("RGBA", (1, height))
        pixels = ramp.load()
        start = int(height * 0.50)
        for y in range(height):
            if y < start:
                pixels[0, y] = (*top_rgba[:3], 0)
                continue
            t = ease_in_out_cubic((y - start) / max(height - start - 1, 1))
            pixels[0, y] = (
                *bottom_rgba[:3],
                int(round(lerp(top_rgba[3], bottom_rgba[3], t))),
            )
        return ramp.resize((width, height), Image.BILINEAR)

    # -- overlay -------------------------------------------------------------

    def _build_overlay(self) -> Image.Image:
        ctx = self.ctx
        overlay = Image.new("RGBA", (ctx.width, ctx.height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        if self.scene.kind in ("title", "cta"):
            self._draw_wordmark(draw)
        self._draw_text_block(draw)
        return overlay

    def _draw_wordmark(self, draw: ImageDraw.ImageDraw) -> None:
        ctx = self.ctx
        font = ctx.fonts.get("display", ctx.scaled(34))
        draw_tracked_text(
            draw,
            (ctx.box_left, ctx.box_top),
            ctx.brand.visual["logo"]["wordmark"].upper(),
            font,
            (*ctx.color("paper"), 255),
            tracking=ctx.scaled(6),
            shadow=(0, 0, 0, 150),
        )

    def _draw_text_block(self, draw: ImageDraw.ImageDraw) -> None:
        """Lay the headline, subline and pills out from the bottom of the safe box up."""
        ctx = self.ctx
        scene = self.scene
        max_width = ctx.box_right - ctx.box_left

        is_hero = scene.kind in ("title", "cta")
        headline_font = ctx.fonts.get("display", ctx.scaled(96 if is_hero else 78))
        subline_font = ctx.fonts.get("body", ctx.scaled(42))
        tracking = ctx.fonts.tracking("display")

        headline = (scene.headline or "").strip()
        if ctx.brand.visual["typography"]["display"]["case"] == "upper":
            headline = headline.upper()
        headline_lines = wrap_text(draw, headline, headline_font, max_width, tracking, max_lines=3)
        subline_lines = wrap_text(
            draw, (scene.subline or "").strip(), subline_font, max_width, 0, max_lines=2
        )

        headline_lh = line_height(headline_font)
        subline_lh = line_height(subline_font)
        pill_height = ctx.scaled(PILL_HEIGHT) if scene.spec_pills else 0
        gap = ctx.scaled(22)

        block_height = (
            len(headline_lines) * headline_lh
            + (gap + len(subline_lines) * subline_lh if subline_lines else 0)
            + (gap + pill_height if pill_height else 0)
        )
        y = ctx.box_bottom - ctx.scaled(28) - block_height

        # An accent rule above the headline gives the block a hard edge to sit on.
        rule_y = y - ctx.scaled(28)
        draw.rectangle(
            [ctx.box_left, rule_y, ctx.box_left + ctx.scaled(96), rule_y + ctx.scaled(6)],
            fill=(*ctx.color("accent"), 255),
        )

        headline_colour = ctx.color("primary") if scene.kind == "cta" else ctx.color("paper")
        for line in headline_lines:
            draw_tracked_text(
                draw, (ctx.box_left, y), line, headline_font, (*headline_colour, 255),
                tracking=tracking, shadow=(0, 0, 0, 170), shadow_offset=(0, ctx.scaled(4)),
            )
            y += headline_lh

        if subline_lines:
            y += gap
            for line in subline_lines:
                draw_tracked_text(
                    draw, (ctx.box_left, y), line, subline_font,
                    (*ctx.color("muted" if scene.kind != "title" else "paper"), 255),
                    shadow=(0, 0, 0, 140), shadow_offset=(0, ctx.scaled(2)),
                )
                y += subline_lh

        if scene.spec_pills:
            self._draw_spec_pills(draw, y + gap)

        if scene.kind == "cta":
            self._draw_cta_chip(draw, rule_y - ctx.scaled(30))

    def _draw_spec_pills(self, draw: ImageDraw.ImageDraw, y: float) -> None:
        ctx = self.ctx
        label_font = ctx.fonts.get("body", ctx.scaled(24))
        value_font = ctx.fonts.get("display", ctx.scaled(36))
        pad_x, pad_y = ctx.scaled(22), ctx.scaled(16)
        radius = ctx.scaled(16)
        height = ctx.scaled(PILL_HEIGHT)
        x = ctx.box_left

        for pill in self.scene.spec_pills:
            label = pill["label"].upper()[:22]
            value = pill["value"][:20]
            width = int(
                max(
                    text_width(draw, label, label_font, 1),
                    text_width(draw, value, value_font, ctx.fonts.tracking("display")),
                )
                + pad_x * 2
            )
            if x + width > ctx.box_right:
                break
            draw.rounded_rectangle(
                [x, y, x + width, y + height], radius=radius, fill=(*ctx.color("surface"), 236)
            )
            draw_tracked_text(
                draw, (x + pad_x, y + pad_y), label, label_font,
                (*ctx.color("accent"), 255), tracking=1,
            )
            draw_tracked_text(
                draw, (x + pad_x, y + pad_y + ctx.scaled(30)), value, value_font,
                (*ctx.color("paper"), 255), tracking=ctx.fonts.tracking("display"),
            )
            x += width + ctx.scaled(16)

    def _draw_cta_chip(self, draw: ImageDraw.ImageDraw, baseline_y: float) -> None:
        ctx = self.ctx
        font = ctx.fonts.get("display", ctx.scaled(34))
        label = "TAP TO EXPLORE"
        tracking = ctx.scaled(4)
        width = int(text_width(draw, label, font, tracking) + ctx.scaled(56))
        height = ctx.scaled(72)
        y = baseline_y - height
        draw.rounded_rectangle(
            [ctx.box_left, y, ctx.box_left + width, y + height],
            radius=height // 2,
            fill=(*ctx.color("primary"), 255),
        )
        draw_tracked_text(
            draw,
            (ctx.box_left + ctx.scaled(28), y + ctx.scaled(18)),
            label, font, (*ctx.color("ink"), 255), tracking=tracking,
        )

    # -- frames --------------------------------------------------------------

    def frame_at(self, local_t: float) -> Image.Image:
        """The composited RGB frame at `local_t` seconds into this scene."""
        ctx = self.ctx
        kb = ctx.brand.video["ken_burns"]
        progress = ease_in_out_cubic(local_t / max(self.scene.duration, 1e-6))

        zoom_start, zoom_end = float(kb["zoom_start"]), float(kb["zoom_end"])
        zoom = lerp(zoom_start, zoom_end, progress)

        base_w, base_h = self.base_size
        crop_w = base_w * (zoom_start / zoom)
        crop_h = base_h * (zoom_start / zoom)

        pan = float(kb["max_pan_px"]) * ctx.scale * self.scene.pan_direction
        centre_x = base_w / 2 + pan * (progress - 0.5) * 2
        centre_y = base_h / 2 + pan * 0.35 * (progress - 0.5) * 2

        half_w, half_h = crop_w / 2, crop_h / 2
        centre_x = min(max(centre_x, half_w), base_w - half_w)
        centre_y = min(max(centre_y, half_h), base_h - half_h)

        window = self._background.crop(
            (
                int(round(centre_x - half_w)),
                int(round(centre_y - half_h)),
                int(round(centre_x + half_w)),
                int(round(centre_y + half_h)),
            )
        ).resize((ctx.width, ctx.height), Image.BICUBIC)

        window = window.convert("RGBA")
        window.alpha_composite(self._overlay)
        return window.convert("RGB")


# --- render context ----------------------------------------------------------

class RenderContext:
    """Resolved output geometry, palette, fonts and image sources for one render."""

    def __init__(self, brand: Brand, images: ImageLibrary, aspect: str) -> None:
        self.brand = brand
        self.images = images
        self.fonts = FontBook(brand)
        self.width, self.height = ASPECT_PRESETS.get(aspect, ASPECT_PRESETS["vertical"])

        # Brand safe areas are authored against the vertical 1080x1920 frame;
        # scale them for any other aspect so the layout stays proportional.
        self.scale = self.width / ASPECT_PRESETS["vertical"][0]

        safe = brand.video["safe_area"]
        self.box_left = self.scaled(safe["left"])
        self.box_right = self.width - self.scaled(safe["right"])
        self.box_top = self.scaled(safe["top"])
        self.box_bottom = self.height - self.scaled(safe["bottom"])

    def scaled(self, value: float) -> int:
        return max(int(round(value * self.scale)), 1)

    def color(self, token: str) -> tuple[int, int, int]:
        return self.brand.color(token)


# --- timeline ----------------------------------------------------------------

class Timeline:
    """Sequences scenes with overlapping cross-dissolves and draws the progress bar."""

    def __init__(self, scenes: Sequence[SceneRenderer], ctx: RenderContext, transition: float) -> None:
        self.scenes = list(scenes)
        self.ctx = ctx
        # A transition can never eat more than a third of its shorter neighbour,
        # or a short CTA card would be dissolving for its whole life.
        shortest = min((s.scene.duration for s in self.scenes), default=1.0)
        self.transition = max(min(transition, shortest / 3.0), 0.0)

        self.starts: list[float] = []
        cursor = 0.0
        for index, renderer in enumerate(self.scenes):
            self.starts.append(cursor)
            cursor += renderer.scene.duration - (self.transition if index < len(self.scenes) - 1 else 0)
        self.duration = max(cursor, 0.1)

    def _active(self, t: float) -> list[tuple[SceneRenderer, float, float]]:
        """Scenes covering time `t`, as (renderer, local_t, weight)."""
        hits: list[tuple[SceneRenderer, float, float]] = []
        for renderer, start in zip(self.scenes, self.starts):
            end = start + renderer.scene.duration
            if start - 1e-6 <= t < end:
                hits.append((renderer, t - start, 1.0))
        if not hits:
            # Past the end (float rounding on the final frame): hold the last scene.
            last = self.scenes[-1]
            return [(last, last.scene.duration, 1.0)]
        return hits

    def frame(self, t: float) -> np.ndarray:
        active = self._active(t)

        if len(active) == 1 or self.transition <= 0:
            renderer, local_t, _ = active[0]
            image = renderer.frame_at(local_t)
        else:
            outgoing, out_t, _ = active[0]
            incoming, in_t, _ = active[1]
            alpha = ease_in_out_cubic(min(in_t / self.transition, 1.0))
            image = Image.blend(outgoing.frame_at(out_t), incoming.frame_at(in_t), alpha)

        frame = np.asarray(image, dtype=np.uint8).copy()
        self._draw_progress(frame, t)
        return frame

    def _draw_progress(self, frame: np.ndarray, t: float) -> None:
        """A thin bar along the bottom of the safe area.

        Cheap, and it measurably holds attention — the viewer can see the end
        coming instead of guessing whether to swipe.
        """
        ctx = self.ctx
        height = ctx.scaled(6)
        y0 = ctx.box_bottom + ctx.scaled(16)
        y1 = min(y0 + height, ctx.height)
        x0, x1 = ctx.box_left, ctx.box_right
        filled = x0 + int((x1 - x0) * min(max(t / self.duration, 0.0), 1.0))

        frame[y0:y1, x0:x1] = np.array(ctx.color("surface"), dtype=np.uint8)
        if filled > x0:
            frame[y0:y1, x0:filled] = np.array(ctx.color("primary"), dtype=np.uint8)


# --- public API --------------------------------------------------------------

@dataclass
class RenderResult:
    path: Path
    duration_seconds: float
    width: int
    height: int
    fps: int
    scene_count: int
    has_audio: bool
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "file_path": str(self.path),
            "duration_seconds": round(self.duration_seconds, 2),
            "resolution": f"{self.width}x{self.height}",
            "fps": self.fps,
            "scene_count": self.scene_count,
            "has_audio": self.has_audio,
            "warnings": self.warnings,
        }


def _conform_audio(audio_path: Path, duration: float, warnings: list[str]):
    """Trim or pad the voiceover so it exactly matches the video length."""
    from moviepy import AudioFileClip

    audio = AudioFileClip(str(audio_path))
    if audio.duration > duration + AUDIO_TOLERANCE_SECONDS:
        return audio.subclipped(0, duration)
    if audio.duration < duration - AUDIO_TOLERANCE_SECONDS:
        from moviepy import AudioArrayClip, concatenate_audioclips

        gap = duration - audio.duration
        channels = getattr(audio, "nchannels", 1) or 1
        rate = int(audio.fps or 44100)
        silence = AudioArrayClip(np.zeros((int(gap * rate), channels)), fps=rate)
        warnings.append(f"Voiceover was {gap:.1f}s shorter than the video; padded with silence.")
        return concatenate_audioclips([audio, silence])
    return audio


def _wav_duration_seconds(path: Path) -> Optional[float]:
    """The voiceover's real duration, or None if it can't be read."""
    try:
        return voice.wav_duration_seconds(path)
    except (OSError, wave.Error, voice.TTSUnavailable) as exc:
        logger.warning("Could not read voiceover duration from %s: %s", path, exc)
        return None


def scale_scenes_to_audio(scenes: list[Scene], target_duration: float, transition: float) -> None:
    """Stretch/compress every scene's duration so the timeline lands on `target_duration`.

    The video plan's scene durations are only ever an estimate of how long the
    script *will* take to speak (the `words_per_second` heuristic). Real TTS
    rarely matches that estimate exactly — Piper spoke a measured 25.8s script
    in 19.6s in testing. Rather than padding/trimming the *audio* to
    fit a guessed-at video length (which either freezes on a dead frame or
    chops off narration), the scenes are rescaled to fit the *real* narration
    length, so every frame of the video is proportionally aligned to the
    audio actually being played. Mutates `scenes` in place.
    """
    if not scenes or target_duration <= 0:
        return
    n = len(scenes)
    overlap = transition * (n - 1) if n > 1 else 0.0
    planned = sum(s.duration for s in scenes) - overlap
    if planned <= 0:
        return

    factor = (target_duration + overlap) / (planned + overlap)
    for scene in scenes:
        scene.duration = max(scene.duration * factor, MIN_SCENE_SECONDS)

    # The floor above (and the fixed, unscaled transition overlap) means the
    # scaled total can drift a little from the target; absorb that drift into
    # the last scene so the timeline lands on the audio's duration exactly.
    achieved = sum(s.duration for s in scenes) - overlap
    residual = target_duration - achieved
    scenes[-1].duration = max(scenes[-1].duration + residual, MIN_SCENE_SECONDS)


def scale_scenes_to_beats(scenes: list[Scene], beat_durations: dict[str, float], transition: float) -> bool:
    """Rescale each scene against its own beat's real spoken duration.

    `scale_scenes_to_audio` applies one stretch factor to the whole video, so
    it only guarantees the *total* length matches the narration — mid-video,
    a scene can still show beat N while the audio has already moved on to
    beat N+1, because ElevenLabs doesn't speak every beat proportionally
    faster/slower by the same ratio. This instead groups scenes by the beat
    they narrate (the video plan gives one scene per beat, occasionally more)
    and scales each group only against that beat's measured audio, so a scene
    change lines up with the words actually being spoken at that moment.

    Returns False (making no changes) if the scenes' `beat` values don't
    cover the plan cleanly — e.g. beats missing from `beat_durations`, or one
    beat's scenes split up by scenes of another beat — so the caller can fall
    back to `scale_scenes_to_audio`.
    """
    if not scenes or not beat_durations:
        return False

    groups: list[tuple[str, list[Scene]]] = []
    for scene in scenes:
        if groups and groups[-1][0] == scene.beat:
            groups[-1][1].append(scene)
        else:
            groups.append((scene.beat, [scene]))

    if any(beat not in beat_durations for beat, _ in groups):
        return False

    for beat, group in groups:
        target = beat_durations[beat]
        overlap = transition * (len(group) - 1) if len(group) > 1 else 0.0
        planned = sum(s.duration for s in group) - overlap
        if planned <= 0 or target <= 0:
            continue
        factor = (target + overlap) / (planned + overlap)
        for scene in group:
            scene.duration = max(scene.duration * factor, MIN_SCENE_SECONDS)
        achieved = sum(s.duration for s in group) - overlap
        residual = target - achieved
        group[-1].duration = max(group[-1].duration + residual, MIN_SCENE_SECONDS)
    return True


def build_scenes(video_plan: dict[str, Any], brand: Brand) -> list[Scene]:
    """Plan JSON -> validated scenes, with a usable fallback if the plan is empty."""
    raw_scenes: Iterable[dict[str, Any]] = video_plan.get("scenes") or []
    scenes = [
        Scene.from_plan(raw, order, brand)
        for order, raw in enumerate(raw_scenes)
        if isinstance(raw, dict)
    ]
    if not scenes:
        scenes = [
            Scene(kind="title", duration=brand.video["title_card_seconds"],
                  headline=brand.raw["brand"]["name"], subline=brand.raw["brand"]["one_liner"]),
            Scene(kind="cta", duration=brand.video["cta_card_seconds"],
                  headline="Ride it home", subline=brand.raw["brand"]["website"], pan_direction=-1),
        ]
    return scenes


def render_video(
    *,
    video_plan: dict[str, Any],
    image_urls: Sequence[str],
    output_path: Path,
    voiceover_path: Optional[Path] = None,
    beat_durations: Optional[dict[str, float]] = None,
    brand: Optional[Brand] = None,
    aspect: Optional[str] = None,
    fps: Optional[int] = None,
) -> RenderResult:
    """Render the video described by `video_plan` and write it to `output_path`.

    `beat_durations` (beat name -> real spoken seconds, from ElevenLabs/etc via
    `voice.generate_voiceover`) drives per-scene timing when available, so each
    scene's on-screen time matches the words spoken during it rather than only
    the video's total length matching the audio's total length.
    """
    from moviepy import VideoClip

    brand = brand or load_brand()
    aspect = aspect or brand.video.get("aspect") or VIDEO_ASPECT
    fps = int(fps or brand.video.get("fps") or VIDEO_FPS)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    images = ImageLibrary(image_urls)
    ctx = RenderContext(brand, images, aspect)
    scenes = build_scenes(video_plan, brand)
    transition_seconds = float(brand.video["transition_seconds"])

    warnings = list(images.warnings)
    voiceover_exists = bool(voiceover_path) and Path(voiceover_path).exists()
    audio_duration = _wav_duration_seconds(Path(voiceover_path)) if voiceover_exists else None

    scaled_per_beat = bool(beat_durations) and scale_scenes_to_beats(scenes, beat_durations, transition_seconds)
    if not scaled_per_beat:
        if audio_duration:
            scale_scenes_to_audio(scenes, audio_duration, transition_seconds)
        elif voiceover_exists:
            warnings.append("Could not read voiceover duration; scene timing follows the video plan only.")

    logger.info(
        "Rendering %d scenes at %dx%d/%dfps from %d source image(s)",
        len(scenes), ctx.width, ctx.height, fps, len(images),
    )
    renderers = [SceneRenderer(scene, ctx) for scene in scenes]
    timeline = Timeline(renderers, ctx, transition_seconds)
    clip = VideoClip(frame_function=timeline.frame, duration=timeline.duration)
    audio_clip = None

    if voiceover_exists:
        try:
            audio_clip = _conform_audio(Path(voiceover_path), timeline.duration, warnings)
            clip = clip.with_audio(audio_clip)
        except Exception as exc:  # noqa: BLE001 — silent video beats no video
            warnings.append(f"Could not attach voiceover: {exc}")
            logger.warning("Voiceover attach failed: %s", exc)

    try:
        clip.write_videofile(
            str(output_path),
            fps=fps,
            codec="libx264",
            audio_codec="aac" if audio_clip is not None else None,
            audio=audio_clip is not None,
            preset="medium",
            threads=VIDEO_RENDER_THREADS,
            pixel_format="yuv420p",   # required for playback on iOS/Safari/most players
            logger=None,
        )
    finally:
        clip.close()
        if audio_clip is not None:
            audio_clip.close()

    logger.info("Wrote %s (%.1fs)", output_path, timeline.duration)
    return RenderResult(
        path=output_path,
        duration_seconds=timeline.duration,
        width=ctx.width,
        height=ctx.height,
        fps=fps,
        scene_count=len(scenes),
        has_audio=audio_clip is not None,
        warnings=warnings,
    )


def main() -> None:
    """Re-render a video from a plan a pipeline run already produced.

        python -m media.movie --plan output/8-5-off-road-pro/v1/video_plan.json

    Useful when iterating on the renderer itself: it exercises every code path
    the pipeline does — real plan, real photography, real voiceover if one sits
    beside the plan — without spending a single model call.
    """
    import argparse
    import json

    from config.logging_setup import configure_logging
    from database.repository import get_scraped_data

    parser = argparse.ArgumentParser(description=main.__doc__)
    parser.add_argument("--plan", type=Path, required=True, help="Path to a video_plan.json")
    parser.add_argument(
        "--product-id",
        type=int,
        help="Product whose scraped images to render with. Defaults to the "
        "product_id recorded in the plan directory's _meta.json.",
    )
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--aspect", choices=sorted(ASPECT_PRESETS), default=None)
    args = parser.parse_args()

    configure_logging()

    if not args.plan.is_file():
        raise SystemExit(f"No video plan at {args.plan}")
    plan = json.loads(args.plan.read_text(encoding="utf-8"))

    product_id = args.product_id
    meta_path = args.plan.parent / "_meta.json"
    if product_id is None and meta_path.is_file():
        product_id = json.loads(meta_path.read_text(encoding="utf-8")).get("product_id")
    if product_id is None:
        raise SystemExit("Could not determine the product; pass --product-id.")

    scraped = get_scraped_data(product_id)
    if scraped is None:
        raise SystemExit(f"Product {product_id} has not been scraped yet.")

    voiceover_path = args.plan.parent / "voiceover.wav"
    result = render_video(
        video_plan=plan,
        image_urls=scraped.image_urls,
        output_path=args.out or (args.plan.parent / "video.mp4"),
        voiceover_path=voiceover_path if voiceover_path.is_file() else None,
        aspect=args.aspect,
    )
    print(f"Rendered {result.path} — {result.duration_seconds:.1f}s, {result.scene_count} scenes")
    for warning in result.warnings:
        print(f"  warning: {warning}")


if __name__ == "__main__":
    main()
