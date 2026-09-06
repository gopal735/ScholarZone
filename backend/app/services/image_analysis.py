"""Lightweight PIL-based image content analysis.

Provides actual image inspection heuristics to differentiate content photographs
from UI assets, logos, and placeholders. Designed to be fast and deterministic.

Classification:
- content_photo: likely a photographic content image (students, campus, events)
- graphic: vector/illustration with moderate complexity
- logo_like: simple geometric shapes, few colors, high contrast
- ui_asset: tiny, low-complexity, or sprite-like
- unknown: insufficient evidence

All analysis is performed on a downscaled 64x64 thumbnail to minimize memory
and CPU usage while preserving classification-relevant statistics.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from typing import Literal

import httpx
from PIL import Image

ImageClassification = Literal[
    "content_photo",
    "graphic",
    "logo_like",
    "ui_asset",
    "unknown",
]

_THUMB_SIZE = 64
_MIN_PHOTO_COLORS = 128
_MIN_GRAPHIC_COLORS = 32
_MAX_UI_COLORS = 16
_MIN_EDGE_DENSITY_PHOTO = 0.08
_MAX_UI_EDGE_DENSITY = 0.03
_MIN_FILE_SIZE_PHOTO = 10_000
_MAX_FILE_SIZE_UI = 3_000


@dataclass
class ImageAnalysisResult:
    """Result of lightweight image content analysis."""

    file_size_bytes: int | None = None
    width: int | None = None
    height: int | None = None
    mode: str | None = None
    format: str | None = None
    unique_colors: int | None = None
    edge_density: float | None = None
    color_variance: float | None = None
    classification: ImageClassification = "unknown"
    is_likely_photo: bool = False
    is_likely_logo: bool = False
    is_likely_ui: bool = False
    analysis_error: str | None = None


def analyze_image(
    image_url: str,
    timeout: float = 30.0,
    content_length: int | None = None,
    content: bytes | None = None,
) -> ImageAnalysisResult:
    """Analyze an image for content classification.

    If content bytes are provided, skips the HTTP fetch and analyzes directly.
    Otherwise, fetches the image from the URL.
    """
    result = ImageAnalysisResult(file_size_bytes=content_length)

    if content_length is not None and content_length < 100:
        result.classification = "ui_asset"
        result.is_likely_ui = True
        result.analysis_error = "tiny file size"
        return result

    if content is None:
        try:
            headers = {"User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )}
            with httpx.stream(
                "GET",
                image_url,
                headers=headers,
                timeout=timeout,
                follow_redirects=True,
            ) as response:
                if response.status_code != 200:
                    result.analysis_error = f"HTTP {response.status_code}"
                    return result
                content = response.read()
        except Exception as exc:
            result.analysis_error = str(exc)
            return result

    if not content:
        result.analysis_error = "empty response"
        return result

    result.file_size_bytes = len(content)

    if len(content) < _MIN_FILE_SIZE_PHOTO and result.file_size_bytes < _MAX_FILE_SIZE_UI:
        result.classification = "ui_asset"
        result.is_likely_ui = True
        result.analysis_error = "tiny file size"
        return result

    try:
        img = Image.open(io.BytesIO(content))
        result.width = img.width
        result.height = img.height
        result.mode = img.mode
        result.format = img.format

        if img.width < 1 or img.height < 1:
            result.analysis_error = "invalid dimensions"
            return result

        thumb = img.convert("RGB")
        thumb.thumbnail((_THUMB_SIZE, _THUMB_SIZE), Image.Resampling.LANCZOS)

        pixels = list(thumb.getdata())
        unique_colors = len(set(pixels))
        result.unique_colors = unique_colors

        variance = _color_variance(pixels)
        result.color_variance = variance

        edges = _edge_density(thumb)
        result.edge_density = edges

        result.classification = _classify(result)
        result.is_likely_photo = result.classification == "content_photo"
        result.is_likely_logo = result.classification == "logo_like"
        result.is_likely_ui = result.classification == "ui_asset"

    except Exception as exc:
        result.analysis_error = str(exc)

    return result


def _color_variance(pixels: list[tuple[int, int, int]]) -> float:
    """Calculate average per-channel variance across sampled pixels."""
    if not pixels:
        return 0.0
    n = len(pixels)
    r_sum = sum(p[0] for p in pixels)
    g_sum = sum(p[1] for p in pixels)
    b_sum = sum(p[2] for p in pixels)
    r_mean = r_sum / n
    g_mean = g_sum / n
    b_mean = b_sum / n
    r_var = sum((p[0] - r_mean) ** 2 for p in pixels) / n
    g_var = sum((p[1] - g_mean) ** 2 for p in pixels) / n
    b_var = sum((p[2] - b_mean) ** 2 for p in pixels) / n
    return (r_var + g_var + b_var) / 3.0


def _edge_density(img: Image.Image) -> float:
    """Estimate edge density using simple horizontal + vertical gradient."""
    w, h = img.size
    if w < 2 or h < 2:
        return 0.0
    pixels = list(img.getdata())
    idx = lambda x, y: y * w + x
    edges = 0
    total = 0
    for y in range(h - 1):
        for x in range(w - 1):
            p = pixels[idx(x, y)]
            pr = pixels[idx(x + 1, y)]
            pd = pixels[idx(x, y + 1)]
            dr = abs(p[0] - pr[0]) + abs(p[1] - pr[1]) + abs(p[2] - pr[2])
            dd = abs(p[0] - pd[0]) + abs(p[1] - pd[1]) + abs(p[2] - pd[2])
            if dr > 30 or dd > 30:
                edges += 1
            total += 1
    return edges / total if total > 0 else 0.0


def _classify(result: ImageAnalysisResult) -> ImageClassification:
    """Classify image based on collected heuristics."""
    size = result.file_size_bytes or 0
    colors = result.unique_colors or 0
    edges = result.edge_density or 0.0
    variance = result.color_variance or 0.0

    if size < 500:
        return "ui_asset"

    if colors <= _MAX_UI_COLORS and edges < _MAX_UI_EDGE_DENSITY:
        return "ui_asset"

    if colors <= _MIN_GRAPHIC_COLORS and variance < 500:
        return "logo_like"

    if colors >= _MIN_PHOTO_COLORS and variance > 2000 and edges >= _MIN_EDGE_DENSITY_PHOTO:
        return "content_photo"

    if colors >= _MIN_GRAPHIC_COLORS and variance > 1000:
        return "graphic"

    if colors <= _MIN_GRAPHIC_COLORS:
        return "logo_like"

    return "unknown"
