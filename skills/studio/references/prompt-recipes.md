# Prompt Recipes

这些配方是起点，不是必须填满的表单。保留用户给出的具体信息，只添加能直接改善
结果的字段。

## Landing page hero

```text
Use case: product-mockup
Asset type: landing page hero
Primary request: <产品与画面要求>
Scene/backdrop: <简洁环境>
Style/medium: polished product photography
Composition/framing: wide composition, product clearly readable, usable negative space for copy
Lighting/mood: soft controlled studio lighting
Constraints: preserve product geometry and label; no extra props unless requested
Avoid: watermark, invented logo, unreadable text, clipped product
```

## Editorial portrait

```text
Use case: photorealistic-natural
Asset type: editorial portrait
Primary request: <人物与场景>
Style/medium: natural editorial photography with realistic skin texture
Composition/framing: <close/medium/full>, eye-level camera, intentional background separation
Lighting/mood: motivated natural light, restrained color grade
Constraints: anatomically plausible hands and face; no beauty-filter plastic skin
Avoid: watermark, duplicated accessories, distorted fingers, oversharpening
```

## Character identity edit

```text
Use case: identity-preserve
Asset type: character scene edit
Primary request: change only <服装/环境/动作中的一个>
Input images: Image 1: edit target and identity reference
Constraints: keep face, identity, body proportions, hairstyle, pose, camera, crop,
perspective, and all unmentioned regions unchanged
Avoid: face drift, age change, extra limbs, costume details not requested
```

## Product background replacement

```text
Use case: precise-object-edit
Asset type: catalog image
Primary request: replace only the background with <新环境>
Input images: Image 1: edit target
Constraints: keep product outline, dimensions, material, label, text, camera,
perspective, reflections on the product, and edge quality unchanged
Avoid: warped label, invented branding, changed product color, floating product
```

## Marketing visual with exact copy

```text
Use case: ads-marketing
Asset type: campaign visual
Primary request: <活动主题>
Composition/framing: reserve a clean high-contrast area for the headline
Text (verbatim): "<逐字文案>"
Constraints: render the quoted text exactly once with unchanged punctuation and line breaks
Avoid: any other text, misspelling, watermark, fake legal copy
```

若文字必须 100% 准确，优先生成无字底图并用确定性排版流程添加文案。

## Stylized concept art

```text
Use case: stylized-concept
Asset type: concept art
Primary request: <主体和世界观>
Scene/backdrop: <空间与时间>
Style/medium: <明确媒介，不使用在世艺术家姓名>
Composition/framing: strong readable silhouette, layered depth, clear focal hierarchy
Lighting/mood: <主光方向与情绪>
Color palette: <主色、点缀色、禁用色>
Avoid: watermark, text, noisy tangent intersections, duplicated elements
```

## Transparent cutout source

```text
Use case: background-extraction
Asset type: transparent PNG source
Primary request: <单一不透明主体>
Scene/backdrop: perfectly flat solid #00ff00 chroma-key background
Composition/framing: centered full subject, generous padding, nothing touches the frame
Lighting/mood: even subject lighting without cast or contact shadow
Constraints: uniform #00ff00 background; crisp separated edges; do not use #00ff00 in subject
Avoid: gradient, texture, floor plane, reflection, shadow, watermark, text
```
