"""Brand system: the single source of truth for voice, audience and visual identity.

`brand.yaml` is the machine-readable definition; the markdown files next to it
carry the rationale. Everything that needs brand data goes through
`brand.loader.load_brand()` so there is exactly one parse and one cache.
"""
from brand.loader import Brand, load_brand

__all__ = ["Brand", "load_brand"]
