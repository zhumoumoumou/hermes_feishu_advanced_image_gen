---
name: prompt-seedream-5-lite
description: Refine and confirm provider-neutral Seedream 5 Lite prompts for reasoning-led creation, current-information visuals with optional online search, knowledge and office graphics, style transfer, intent-aware editing, multi-subject scenes, references, and coherent image sets. Use after the advanced image wizard selects any supplier's Seedream 5 Lite model.
---

# Seedream 5 Lite Prompt

Apply the same semantic prompt method across suppliers. Supplier choice affects transport,
credentials, quotas, and errors, not how the scene is described.

Follow the official Seedream 4.0–5.0 prompt guide, then optimize for Lite's officially highlighted
strengths: deep multimodal reasoning, world knowledge, optional real-time retrieval, information
visualization, style transfer, intent-aware editing, and complex multi-subject instructions. Do not
call generation tools; prepare a confirmed prompt packet for the wizard.

## Start with the minimum complete scene

Write concise, coherent natural language in this order:

```text
subject + action + environment + application + visual treatment
```

Add precise style, color, lighting, composition, camera, material, and finish only when they help
control the result. Name the application, such as a poster, logo, product hero, infographic, or
storyboard. Avoid disconnected keyword piles, repeated adjectives, and ornate wording that hides
the primary instruction.

Put every exact visible string in double quotes and state whether additional text is forbidden.
For knowledge-dense graphics, use correct professional terms and define the visualization type,
information hierarchy, layout, and style.

## Exploit Lite strengths deliberately

### Preserve intent instead of over-writing it

Lite is officially positioned to infer intent from concise or ambiguous instructions. Start from
the user's goal and make assumptions explicit instead of burying it under ornamental prompt prose.
Clarify ambiguity that would materially change the output; otherwise propose a compact draft and
let the user approve the inferred direction.

### Separate current facts from visual instructions

For weather, prices, rankings, recent events, or other time-sensitive content, ask for the target
date, locale, unit, and freshness requirement. Put the exact facts or queries in a distinct data
block and the layout/style in a visual block. Request the supplier's online-search tool only when
the selected model entry supports it. Never invent current values, and do not imply that retrieval
is active merely because the model family supports it.

### Encode reasoning and knowledge tasks

For educational, scientific, office, or information graphics, state the governing facts,
relationships, formulas, spatial logic, labels, and expected visualization. Ask the model to render
the correct result, not to display hidden reasoning. Mark every factual assertion that still needs
external verification.

### Use references for style and transformation logic

For style transfer, identify the visual attributes to extract—palette, brushwork, texture, light,
or graphic language—and prohibit content transfer. For transformation-by-example, describe the
change from Image 1 to Image 2, apply the same change to Image 3, and lock all unrelated content.

### Bound complex multi-subject scenes

Assign each subject a position and unique attributes such as count, letter, time, material, and
color. The official showcase demonstrates a nine-subject grid, but that is evidence of a use case,
not a hard API limit. Verify supplier limits and add per-subject acceptance checks.

## Respect Lite's quality boundary

ByteDance describes Lite as a smaller model with remaining room in structural stability, realism,
and aesthetics. Do not assume that “Lite” means faster or cheaper; those are supplier properties.
For high-stakes photorealism, portrait finish, dense professional layouts, multilingual production,
or complex annotation-driven edits, recommend Pro when available. If Lite remains selected, tighten
structure, identity, realism, text, and layout acceptance criteria and plan targeted retries.

## Select the task pattern

### Text to image

Lead with the main subject, action, and setting. For simple scenes, prefer a short precise prompt.
For complex scenes, enumerate concrete elements and their spatial relationships instead of adding
generic quality words.

### Image editing

Name the target and operation explicitly: add, delete, replace, or modify. Couple each change with
what must remain unchanged, and avoid ambiguous pronouns.

```text
Change only: turn the blue sofa in Image 1 into dark green velvet.
Keep unchanged: the room layout, people, wall art, camera, crop, perspective,
lighting, shadows, and every unmentioned region.
```

If arrows, boxes, or scribbles mark a region, explain what each marker means and whether it should
be removed from the result. For sketches, floor plans, and UI prototypes, follow text annotations
and explicitly preserve layout, positions, and structure.

### Reference and multi-image input

For a reference image, state both the features to extract or preserve and the desired output scene.
For multiple images, number them and assign one clear operation or role to each.

```text
Image 1 is the edit target; preserve its layout and product geometry.
Image 2 supplies the character identity only.
Image 3 supplies the watercolor style only; do not copy its person, text, or logo.
```

### Multi-image output

Say “a series”, “a set”, or “a group of images” and give the exact count. Lock shared characters,
products, style, palette, and continuity, then list what changes in each image. Use this pattern for
storyboards, comics, IP products, product sets, and emoji packs.

## Discuss and confirm

Ask one compact group of questions at a time:

1. outcome, application, and exact image count;
2. numbered image roles and requested operation;
3. subject, action, environment, and spatial relationships;
4. style, composition, camera, light, color, and material;
5. exact quoted text;
6. invariants, exclusions, and measurable acceptance criteria.

If the request is already concrete, summarize assumptions and proceed to confirmation. Return:

- final prompt;
- image-role map and edit invariants;
- aspect ratio, image count, and variant instructions;
- exact rendered text;
- QA profile and acceptance criteria;
- capability assumptions to verify against the selected supplier/model entry.

Ask the user to approve or revise the packet. Never interpret silence as confirmation.

Sources:

- [ByteDance Seed: Seedream 5.0 Lite](https://seed.bytedance.com/zh/seedream5_0_lite)
- [ByteDance Seed: Seedream 5.0 Lite release](https://seed.bytedance.com/zh/blog/%E6%80%9D%E8%80%83-%E6%9B%B4%E6%B7%B1-%E7%94%9F%E6%88%90%E6%9B%B4%E5%87%86-seedream-5-0-lite-%E5%8F%91%E5%B8%83)
- [Volcengine Seedream 4.0–5.0 Prompt Guide](https://docs.volcengine.com/docs/82379/1829186?lang=zh)
