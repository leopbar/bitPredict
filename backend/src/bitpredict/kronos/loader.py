"""Kronos model loader with in-memory cache per variant."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

KRONOS_PATH = Path("/app/data/kronos")
CONTEXT_LENGTH = 512

# Cache keyed by variant name (e.g. "small", "base")
_cache: dict[str, object] = {}


def get_predictor(model_variant: str):
    """Load and cache the KronosPredictor for the given variant.

    First call downloads/loads the model (~seconds for small, ~30s for base).
    Subsequent calls return the cached instance immediately.
    """
    if model_variant in _cache:
        return _cache[model_variant]

    if not KRONOS_PATH.exists():
        raise RuntimeError(
            f"Kronos model not found at {KRONOS_PATH}. "
            "Run: docker compose exec -u root backend python scripts/kronos_setup.py"
        )

    if str(KRONOS_PATH) not in sys.path:
        sys.path.insert(0, str(KRONOS_PATH))

    logger.info("Loading Kronos-%s from %s", model_variant, KRONOS_PATH)
    from model import Kronos, KronosPredictor, KronosTokenizer  # type: ignore[import]

    tokenizer = KronosTokenizer.from_pretrained("NeoQuasar/Kronos-Tokenizer-base")
    model = Kronos.from_pretrained(f"NeoQuasar/Kronos-{model_variant}")
    predictor = KronosPredictor(model, tokenizer, max_context=CONTEXT_LENGTH)

    _cache[model_variant] = predictor
    logger.info("Kronos-%s loaded and cached", model_variant)
    return predictor
