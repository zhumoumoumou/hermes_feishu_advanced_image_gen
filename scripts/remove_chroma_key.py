#!/usr/bin/env python3
"""Remove a flat chroma-key background and write an RGBA image."""

from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageFilter


RGB = tuple[int, int, int]


def parse_hex_color(value: str) -> RGB:
    value = value.strip().lstrip("#")
    if len(value) != 6:
        raise argparse.ArgumentTypeError("key color must use RRGGBB format")
    try:
        return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]
    except ValueError as exc:
        raise argparse.ArgumentTypeError("key color must use hexadecimal digits") from exc


def border_pixels(image: Image.Image) -> Iterable[RGB]:
    rgb = image.convert("RGB")
    width, height = rgb.size
    x_step = max(1, width // 100)
    y_step = max(1, height // 100)
    for x in range(0, width, x_step):
        yield rgb.getpixel((x, 0))
        yield rgb.getpixel((x, height - 1))
    for y in range(0, height, y_step):
        yield rgb.getpixel((0, y))
        yield rgb.getpixel((width - 1, y))


def detect_border_key(image: Image.Image) -> RGB:
    samples = list(border_pixels(image))
    if not samples:
        raise ValueError("cannot sample an empty image")
    return tuple(int(statistics.median(channel)) for channel in zip(*samples))  # type: ignore[return-value]


def color_distance(pixel: RGB, key: RGB) -> float:
    return math.sqrt(sum((pixel[index] - key[index]) ** 2 for index in range(3)))


def despill_pixel(pixel: RGB, key: RGB, matte: float) -> RGB:
    channels = list(pixel)
    key_min = min(key)
    key_max = max(key)
    spill_channels = {
        index
        for index, value in enumerate(key)
        if value >= key_max - 32 and value - key_min >= 64
    }
    clean_channels = [channels[index] for index in range(3) if index not in spill_channels]
    neutral = max(clean_channels) if clean_channels else min(channels)
    for index in spill_channels:
        spill = max(0, channels[index] - neutral)
        channels[index] = round(channels[index] - spill * (1.0 - matte))
    return tuple(channels)  # type: ignore[return-value]


def remove_key(
    source: Image.Image,
    key: RGB,
    transparent_threshold: float,
    opaque_threshold: float,
    soft_matte: bool,
    despill: bool,
    edge_contract: int,
) -> Image.Image:
    if opaque_threshold <= transparent_threshold:
        raise ValueError("opaque threshold must exceed transparent threshold")

    rgba = source.convert("RGBA")
    output: list[tuple[int, int, int, int]] = []
    for red, green, blue, original_alpha in rgba.getdata():
        rgb = (red, green, blue)
        distance = color_distance(rgb, key)
        if soft_matte:
            matte = max(0.0, min(1.0, (distance - transparent_threshold) / (opaque_threshold - transparent_threshold)))
        else:
            matte = 0.0 if distance <= transparent_threshold else 1.0
        alpha = min(original_alpha, round(255 * matte))
        if despill and alpha < 255:
            rgb = despill_pixel(rgb, key, matte)
        output.append((*rgb, alpha))

    result = Image.new("RGBA", rgba.size)
    result.putdata(output)
    if edge_contract > 0:
        alpha = result.getchannel("A").filter(ImageFilter.MinFilter(edge_contract * 2 + 1))
        result.putalpha(alpha)
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    key_group = parser.add_mutually_exclusive_group()
    key_group.add_argument("--key", type=parse_hex_color)
    key_group.add_argument("--auto-key", choices=["border"])
    parser.add_argument("--soft-matte", action="store_true")
    parser.add_argument("--transparent-threshold", type=float, default=12.0)
    parser.add_argument("--opaque-threshold", type=float, default=220.0)
    parser.add_argument("--despill", action="store_true")
    parser.add_argument("--edge-contract", type=int, default=0)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.edge_contract < 0:
        raise SystemExit("--edge-contract must be non-negative")
    with Image.open(args.input) as source:
        key = args.key or detect_border_key(source)
        result = remove_key(
            source,
            key,
            args.transparent_threshold,
            args.opaque_threshold,
            args.soft_matte,
            args.despill,
            args.edge_contract,
        )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    result.save(args.out)
    alpha = result.getchannel("A")
    transparent = sum(value == 0 for value in alpha.getdata())
    total = result.width * result.height
    print(json.dumps({
        "output": str(args.out.resolve()),
        "size": [result.width, result.height],
        "key": "#" + "".join(f"{channel:02x}" for channel in key),
        "transparent_fraction": round(transparent / total, 6),
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
