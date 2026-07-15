---
name: prompt-generic-image
description: Build a provider-neutral, production-ready image prompt and confirmation packet. Use after the advanced image wizard selects Hermes Native or any model without a dedicated prompt skill, especially for text-to-image, image editing, reference-image, exact-text, multi-variant, or delivery-sensitive requests.
---

# Generic Image Prompt

Do not generate an image. Refine the request, then return a draft for
`advanced_image_wizard(action="draft")`.

## Discuss only material gaps

Ask concise questions only when the answer changes the result:

- final asset and audience;
- subject, setting, composition, camera, lighting, palette, and medium;
- exact text, including case, punctuation, and line breaks;
- role of every input image: edit target, identity, style, composition, or insert source;
- edit invariants and prohibited changes;
- aspect ratio, variant axis, acceptance criteria, and destination.

Do not invent brands, slogans, characters, events, or positional constraints. For a simple
request, make reasonable visual assumptions and present them for confirmation instead of
starting a long interview.

## Compose the draft

Use only relevant fields:

```text
Asset/use: <purpose>
Primary request: <core intent>
Inputs: <Image 1: role; Image 2: role>
Subject and setting: <content>
Composition/camera: <framing and negative space>
Style/medium: <visual language>
Lighting/color/material: <finish>
Text verbatim: "<exact text>"
Keep unchanged: <edit invariants>
Avoid: <hard negatives>
```

Keep one final asset per generation. Put variant differences in `variant_instructions`, not in
one collage prompt. Repeat edit invariants explicitly.

## Return the confirmation packet

Return:

1. final prompt;
2. input-image roles;
3. aspect ratio and variants;
4. QA profile and acceptance criteria;
5. exact text and destination;
6. unresolved assumptions, if any.

Ask the user to approve or revise this packet. Only after approval should the agent call the
wizard's `draft`, show its normalized confirmation summary, and then call `confirm`.
