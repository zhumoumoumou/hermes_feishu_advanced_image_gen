---
name: prompt-seedream-5-pro
description: Refine and confirm provider-neutral Seedream 5 Pro prompts for text-to-image, image editing, reference-image composition, multi-image input, coherent image sets, exact text, diagrams, and prototype rendering. Use after the advanced image wizard selects any supplier's Seedream 5 Pro model.
---

# Seedream 5 Pro Prompt

Apply one semantic prompt policy across suppliers. Supplier choice changes transport,
credentials, quotas, and errors, not the model-family prompt method.

The official Seedream 4.0–5.0 prompt guide currently names Seedream 5.0 Lite, 4.5, and
4.0, not a separate Pro variant. Apply its verified shared Seedream guidance here; do not
invent Pro-only syntax, limits, or capabilities. Check supplier metadata before promising a
feature.

Do not call generation tools. Produce a confirmed prompt packet for the wizard.

## Build the prompt

Use concise, coherent natural language. Begin with `subject + action + environment`, then add
only useful details for application, style, color, lighting, composition, camera, material, and
finish. Name the intended use, such as a poster, logo, product hero, infographic, or storyboard.
Avoid disconnected keyword piles, repeated adjectives, and decorative detail that does not
change the output.

For visible text, put the exact copy in double quotes and say whether any other text is allowed.
For knowledge-dense graphics, use correct domain terms and specify the visualization type,
information hierarchy, layout, and visual style.

## Adapt by task type

### Edit one image

Name the target and operation explicitly: add, delete, replace, or modify. State the allowed
change and invariants together. Avoid pronouns such as “it” when more than one object is present.

```text
Change only: replace the mug in Image 1 with a clear glass cup.
Keep unchanged: the person, pose, facial features, hands, table layout, camera,
crop, perspective, lighting, existing logo, and every unmentioned region.
```

When the source uses arrows, boxes, or scribbles, explain what each marker identifies and whether
the marker itself must disappear. For sketches, floor plans, and UI wireframes, follow source
annotations and lock the existing layout, positions, and structure unless the user requests a
change.

### Use reference or multiple input images

Number every image and give it a single explicit role. Say which features to extract or preserve,
then describe the desired output scene. Do not allow unintended identity, text, logo, or style
transfer.

```text
Image 1 is the edit target. Preserve its composition and product geometry.
Image 2 supplies the character identity only.
Image 3 supplies the ink-wash style only; do not copy its person or text.
```

### Produce a coherent set

Say “a series”, “a set”, or “a group of images” and specify the exact count. Define the common
character, product, style, palette, and continuity rules, then list the content of each image.
Use this for storyboards, comics, IP derivatives, product sets, or emoji packs.

## Discuss and confirm

Ask one compact group of questions at a time, in this order:

1. intended outcome, application, and exact image count;
2. numbered image roles and requested operation;
3. subject, action, environment, and spatial relationships;
4. style, composition, camera, light, color, and material;
5. exact quoted text;
6. invariants, exclusions, and measurable acceptance criteria.

If the request is already concrete, summarize assumptions and move to confirmation. Return:

- final prompt;
- image-role map and edit invariants;
- aspect ratio, image count, and variant instructions;
- exact rendered text;
- QA profile and acceptance criteria;
- supplier capabilities that still require runtime verification.

Ask the user to approve or revise the packet. Never interpret silence as confirmation.

Source: [Volcengine Seedream 4.0–5.0 Prompt Guide](https://docs.volcengine.com/docs/82379/1829186?lang=zh).
