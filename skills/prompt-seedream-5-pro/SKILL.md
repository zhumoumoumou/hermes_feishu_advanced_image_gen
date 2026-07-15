---
name: prompt-seedream-5-pro
description: Refine and confirm prompts for the provider-neutral Seedream 5 Pro model family. Use when the advanced image wizard selects any supplier's Seedream 5.0 Pro entry for text-to-image, image-to-image, multi-reference composition, identity/product preservation, exact text, or deliberate variants.
---

# Seedream 5 Pro Prompt

Apply the same prompt policy regardless of supplier. Supplier choice changes transport,
credentials, quotas, and error behavior—not the semantic prompt skill.

Do not call generation tools. Produce a confirmed draft for the wizard.

## Establish the instruction hierarchy

Discuss missing information in this order:

1. primary outcome and final medium;
2. numbered input images and each image's single role;
3. subject, action, setting, and spatial relationships;
4. composition, camera, lighting, color, material, and finish;
5. exact rendered text;
6. edit invariants, hard negatives, and acceptance criteria.

Ask one compact group of questions at a time. If the request is already concrete, summarize
assumptions and move directly to confirmation.

## Write a coherent prompt

Prefer clear natural-language instructions over disconnected keyword piles. Start with the
main outcome, then describe the scene and visual treatment. Put constraints after the desired
result so prohibitions do not obscure the objective.

For reference images, use stable numbering:

```text
Image 1 is the edit target. Image 2 is identity reference only.
Image 3 supplies composition only. Do not transfer its person, text, or branding.
```

For edits, state the change and invariants together:

```text
Change only: <allowed change>.
Keep unchanged: identity, facial structure, body proportions, product geometry,
camera, crop, perspective, logos, exact text, and every unmentioned region.
```

For text, quote it verbatim and forbid additional text. For variants, preserve the common base
prompt and place one changed design axis in each `variant_instructions` entry.

## Confirmation output

Return a compact packet containing:

- final prompt;
- image-role map and invariants;
- aspect ratio and variant instructions;
- exact text;
- QA profile and measurable acceptance criteria;
- any capability assumption that must be checked against the wizard's selected model entry.

Ask the user to approve or revise the packet. Never interpret silence as confirmation.
