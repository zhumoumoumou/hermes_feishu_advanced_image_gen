---
name: prompt-seedream-5-lite
description: Refine and confirm provider-neutral Seedream 5 Lite prompts for text-to-image, image editing, reference-image composition, multi-image input, coherent image sets, exact text, diagrams, and prototype rendering. Use after the advanced image wizard selects any supplier's Seedream 5 Lite model.
---

# Seedream 5 Lite Prompt

Apply the same semantic prompt method across suppliers. Supplier choice affects transport,
credentials, quotas, and errors, not how the scene is described.

Follow the official Seedream 4.0–5.0 prompt guide. Do not call generation tools; prepare a
confirmed prompt packet for the wizard.

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

Source: [Volcengine Seedream 4.0–5.0 Prompt Guide](https://docs.volcengine.com/docs/82379/1829186?lang=zh).
