#!/usr/bin/env python3
"""Print delivery-relevant image metadata as JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image


def inspect(path: Path) -> dict:
    with Image.open(path) as image:
        image.load()
        report = {
            "path": str(path.resolve()),
            "format": image.format,
            "mode": image.mode,
            "width": image.width,
            "height": image.height,
            "aspect_ratio": round(image.width / image.height, 6),
            "bytes": path.stat().st_size,
            "has_alpha": "A" in image.getbands(),
        }
        if "A" in image.getbands():
            alpha = image.getchannel("A")
            values = list(alpha.getdata())
            total = len(values)
            corners = [
                alpha.getpixel((0, 0)),
                alpha.getpixel((image.width - 1, 0)),
                alpha.getpixel((0, image.height - 1)),
                alpha.getpixel((image.width - 1, image.height - 1)),
            ]
            report.update({
                "transparent_fraction": round(sum(value == 0 for value in values) / total, 6),
                "partial_alpha_fraction": round(sum(0 < value < 255 for value in values) / total, 6),
                "alpha_bbox": alpha.getbbox(),
                "corner_alpha": corners,
            })
        return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    args = parser.parse_args()
    if not args.image.is_file():
        parser.error(f"image does not exist: {args.image}")
    print(json.dumps(inspect(args.image), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
