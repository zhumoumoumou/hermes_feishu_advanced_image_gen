---
name: prompt-seedream-5-pro
description: Refine and confirm provider-neutral Seedream 5 Pro prompts for production-grade dense information graphics, spatially annotated or layered edits, realistic photography and portraits, multilingual layouts, text-to-image, references, and coherent image sets. Use after the advanced image wizard selects any supplier's Seedream 5 Pro model.
---

# Seedream 5 Pro Prompt

Apply one semantic prompt policy across suppliers. Supplier choice changes transport,
credentials, quotas, and errors, not the model-family prompt method.

Use the shared Seedream prompt grammar, then optimize for Pro's officially highlighted strengths:
high-density information, interactive precise editing, realistic imagery and portraits, and
native multilingual creation. Do not invent syntax, limits, or output modes. Check supplier
metadata before promising a feature.

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

## Exploit Pro strengths deliberately

### Organize dense professional content

Use Pro when the output must hold many coordinated facts, panels, labels, or UI modules. Convert
the request into a spatial content plan rather than a paragraph:

1. define audience, application, canvas, and reading order;
2. divide the canvas into named regions, grids, panels, or layers;
3. assign exact content and priority to every region;
4. define typography hierarchy, connectors, legends, units, and color semantics;
5. list facts or copy verbatim and identify anything that still requires verification.

For storyboards, technical drawings, educational posters, dashboards, and complex UI, specify the
exact panel count and the content of each panel. High density does not excuse illegible type,
invented facts, or missing hierarchy.

### Treat annotations as an edit interface

Interpret boxes, arrows, handwriting, masks, and doodles as spatial instructions. Map every marker
to its target, operation, replacement content, and removal policy. When the user requests layer
separation, define semantic layers and their ordering, but verify that the selected supplier can
actually return layered output; otherwise generate a flattened image that preserves the intended
layer relationships.

### Control realism and portrait finish

For photography, describe physically consistent key, fill, rim, reflections, shadows, depth, and
material response. For portraits, preserve identity and natural skin, hair, anatomy, and asymmetry.
State retouching limits so “beautify” does not become plastic skin, face drift, or body distortion.

### Localize multilingual layouts

List each language and exact string separately. Specify reading direction, alignment, regional
typography, line breaks, and which names, numbers, or brands must not be translated. For translation
edits, lock imagery, icons, colors, and module structure while replacing only the requested text
and adapting layout direction where necessary.

## Adapt by task type

### Edit one image

Name the target and operation explicitly: add, delete, replace, or modify. State the allowed
change and invariants together. Avoid pronouns such as “it” when more than one object is present.

```text
Change only: replace the mug in Image 1 with a clear glass cup.
Keep unchanged: the person, pose, facial features, hands, table layout, camera,
crop, perspective, lighting, existing logo, and every unmentioned region.
```

When the source uses arrows, boxes, or scribbles, follow the annotation-interface rules above. For
sketches, floor plans, and UI wireframes, follow source annotations and lock the existing layout,
positions, and structure unless the user requests a change.

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

Sources:

- [ByteDance Seed: Seedream 5.0 Pro](https://seed.bytedance.com/zh/seedream5_0_pro)
- [Volcengine Seedream 4.0–5.0 Prompt Guide](https://docs.volcengine.com/docs/82379/1829186?lang=zh)
