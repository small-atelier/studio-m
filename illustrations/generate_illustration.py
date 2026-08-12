#!/usr/bin/env python3
"""Generate or edit a concept illustration via the Gemini image model.

Three kinds of input, kept separate:
  - style      how it should look (reusable across pieces), e.g. style_sketch.md
               or style_photoreal.md. Its reference image is found by
               convention at the same path with .md replaced by _ref.png
               (style_sketch.md -> style_sketch_ref.png) and is prepended
               to the reference images.
  - ref        the actual look/shapes to ground the drawing in (repeatable) -
               real renders/photos of the piece being illustrated.
  - prompt     content only: what this specific image should show/compose.
               No style description belongs here - that's the --style file's job.

Mode 1 - generate a new image from style + content refs + content prompt:

    python3 generate_illustration.py generate \\
        --style illustrations/style_sketch.md \\
        --prompt pyramid/illustrations/v5_prompt_pyramid.md \\
        --output pyramid/illustrations/v5_pyramid.png \\
        --ref runes/output/v2_ring_gems/renders/front.png

Mode 2 - edit an existing image in place, instead of re-describing the whole
scene (use this to fix/iterate on one thing at a time):

    python3 generate_illustration.py edit \\
        --image pyramid/illustrations/v4_pyramid.png \\
        --instruction pyramid/illustrations/v5_edit_pyramid.md \\
        --output pyramid/illustrations/v5_pyramid.png

Requires GEMINI_API_KEY in the environment (get one at aistudio.google.com,
free tier, no credit card needed).
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from google import genai
from google.genai import types
from PIL import Image

DEFAULT_MODEL = "gemini-3.1-flash-image"


def _style_ref_path(style_path: str) -> Path | None:
    ref = Path(style_path).with_name(Path(style_path).stem + "_ref.png")
    return ref if ref.exists() else None


def _generate(client: genai.Client, model: str, images: list[Image.Image], prompt_text: str, output: str) -> None:
    response = client.models.generate_content(
        model=model,
        contents=[*images, prompt_text],
        config=types.GenerateContentConfig(response_modalities=["IMAGE"]),
    )
    for part in response.candidates[0].content.parts:
        if part.inline_data is not None:
            with open(output, "wb") as f:
                f.write(part.inline_data.data)
            print(f"Wrote {output}")
            return
    sys.exit("No image returned in response.")


def cmd_generate(args: argparse.Namespace, client: genai.Client) -> None:
    content_text = Path(args.prompt).read_text()
    prompt_text = content_text
    images: list[Image.Image] = []

    if args.style:
        style_text = Path(args.style).read_text()
        prompt_text = f"{style_text}\n\n{content_text}"
        style_ref = _style_ref_path(args.style)
        if style_ref:
            images.append(Image.open(style_ref))

    images.extend(Image.open(p) for p in args.ref)
    _generate(client, args.model, images, prompt_text, args.output)


def cmd_edit(args: argparse.Namespace, client: genai.Client) -> None:
    instruction_text = Path(args.instruction).read_text()
    images = [Image.open(args.image)]

    if args.style:
        style_text = Path(args.style).read_text()
        instruction_text = f"{style_text}\n\n{instruction_text}"
        style_ref = _style_ref_path(args.style)
        if style_ref:
            images.append(Image.open(style_ref))

    images.extend(Image.open(p) for p in args.ref)
    _generate(client, args.model, images, instruction_text, args.output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    sub = parser.add_subparsers(dest="mode", required=True)

    gen = sub.add_parser("generate", help="Generate a new image from a style + content refs + content prompt")
    gen.add_argument("--style", help="Path to a reusable style .md file (optional)")
    gen.add_argument("--prompt", required=True, help="Path to a content-only prompt .md file")
    gen.add_argument("--output", required=True)
    gen.add_argument("--ref", action="append", default=[], help="Actual-look reference image path (repeatable)")

    ed = sub.add_parser("edit", help="Edit an existing image in place with a short instruction")
    ed.add_argument("--image", required=True, help="Path to the existing image to edit")
    ed.add_argument("--style", help="Path to a reusable style .md file (optional)")
    ed.add_argument("--instruction", required=True, help="Path to a short edit-instruction .md file")
    ed.add_argument("--output", required=True)
    ed.add_argument("--ref", action="append", default=[], help="Extra reference image path (repeatable)")

    args = parser.parse_args()

    if not os.environ.get("GEMINI_API_KEY"):
        sys.exit("GEMINI_API_KEY is not set in the environment.")

    client = genai.Client()
    if args.mode == "generate":
        cmd_generate(args, client)
    else:
        cmd_edit(args, client)


if __name__ == "__main__":
    main()
