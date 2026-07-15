---
name: studio
description: Plan and deliver production raster images through the advanced image wizard. Use for photos, illustrations, concepts, product or marketing images, image editing, reference composition, deliberate variants, transparent assets, exact text, or any request requiring supplier/model selection and acceptance checks; do not use for deterministic SVG, HTML/CSS, Canvas, or vector-source edits.
---

# Image Studio Skill

将模糊的视觉需求转成可执行的生图规格，通过 `advanced_image_wizard` 选择供应商与
模型、路由模型级 Prompt Skill、确认请求，再编排生成、验收、重试、持久化和交付。

## Prerequisites

- Hermes 已启用 `image_gen` toolset，且 `advanced_image_wizard`、
  `advanced_image_catalog` 与 `advanced_image_generate` 可用。
- 使用 `hermes-native` 时，用户已通过 `hermes tools` 配置 Image Generation provider
  和模型；外部供应商使用 profile 本地目录配置。
- 编辑能力以向导选中模型返回的 `modalities` 和 `max_reference_images` 为准。
- 透明背景后处理和文件质检需要 Pillow。若缺失，告知用户执行
  `python -m pip install pillow`，不要伪称后处理成功。

## Routing and Skill Use

- 强制路由由插件 hook 和工具描述负责，不依赖本 Skill 是否已加载。
- 用户发起高级生图请求时默认调用 `advanced_image_wizard(action="start")`。
- 参考图编辑、身份保持、精确文字、透明背景、多变体、严格验收或项目资产交付等
  复杂任务，应按需加载 `advanced-imagegen:studio`，使用下面的规格与检查规则。
- 不要要求用户在自然语言请求中附加 `skill_view` 指令。
- 若误调用原生 `image_generate`，门禁会拒绝并要求改用向导；不要重复尝试原生工具。

## How to Run

1. 调用向导 `start`，把可用供应商与模型展示给用户。
2. 用户选择后调用 `select`，读取返回的 `prompt_skill` 并按需 `skill_view`。
3. 按模型 Skill 与用户讨论 Prompt、输入图角色、变体和验收条件。
4. 调用 `draft`，向用户完整展示向导返回的确认摘要。
5. 只有用户明确同意后，调用 `confirm(confirmed=true)`；不要把沉默当确认。
6. 根据 manifest 交付 `accepted` 文件；`rejected` 不得冒充成品，`needs_review`
   必须再次请用户确认。

## Quick Reference

| 目标 | 向导/执行输入 | 关键规则 |
|---|---|---|
| 开始 | `advanced_image_wizard(action="start")` | 先选择供应商和模型 |
| 选择 | `action="select", provider, model` | 加载返回的模型 Prompt Skill |
| 草稿 | `action="draft", prompt, ...` | 只返回确认摘要，不生图 |
| 执行 | `action="confirm", confirmed=true` | 必须有用户明确确认 |
| 文生图 | `prompt`, `aspect_ratio` | 不传任何图片参数 |
| 编辑主图 | 加 `image_url` | 当前模型必须支持 image modality |
| 多参考图 | 加 `reference_image_urls` | 标注每张图的角色并遵守数量上限 |
| 三版变体 | `variants=3`, `variant_instructions` | 每版只改变一个设计轴 |
| 透明抠图 | `qa_profile="transparent"` | 自动色键去背与 alpha 验收 |
| 精确文字 | `qa_profile="exact-text"`, `required_text` | 逐字作为硬门槛验收 |
| 人工验收 | `require_human_approval=true` | 返回 `needs_review`，不自动宣称验收 |

宽高比只使用 `landscape`、`portrait`、`square`。如果用户给出 16:9、9:16、1:1
以外的比例，映射到最接近的选项，并在交付时说明映射。

### Use-case slugs

生成：`photorealistic-natural`、`product-mockup`、`ui-mockup`、
`infographic-diagram`、`scientific-educational`、`ads-marketing`、
`productivity-visual`、`logo-brand`、`illustration-story`、
`stylized-concept`、`historical-scene`。

编辑：`text-localization`、`identity-preserve`、`precise-object-edit`、
`lighting-weather`、`background-extraction`、`style-transfer`、
`compositing`、`sketch-to-render`。

## Procedure

### 1. Classify intent and delivery

- 没有输入图：默认为新生成。
- 要保留图中大部分内容，只改变一部分：编辑。
- 图片仅用于风格、人物、材质或构图参考：参考图生成/编辑。
- 明确结果是预览还是项目资产；项目资产必须落到项目目录。
- 记录目标媒介、受众、宽高比、必须出现的内容和必须避免的内容。

对每张输入图显式标注角色：

- `edit target`：需要被修改的主图。
- `style reference`：只借鉴视觉语言。
- `identity reference`：保持人物或角色身份。
- `composition reference`：借鉴布局、镜头或姿态。
- `insert/composite source`：需要合成进主图的素材。

编辑本地文件前，先看清当前内容。不要仅凭文件名推断图片。

### 2. Shape the prompt

只保留有用字段：

```text
Use case: <slug>
Asset type: <最终用途>
Primary request: <用户的核心要求>
Input images: <Image 1: role; Image 2: role>
Scene/backdrop: <环境>
Subject: <主体>
Style/medium: <照片/插画/3D 等>
Composition/framing: <景别、机位、主体位置、留白>
Lighting/mood: <光线与气氛>
Color palette: <色彩约束>
Materials/textures: <材质细节>
Text (verbatim): "<逐字文本>"
Constraints: <必须保持、必须满足>
Avoid: <不要出现>
```

具体需求只做结构化，不擅自扩写。笼统需求可以补充实用的镜头、构图、留白和完成度，
但不要添加用户未暗示的角色、品牌、标语、叙事事件或任意方位要求。

### 3. Lock editing invariants

编辑 prompt 必须重复不变量，而不是只描述变化：

```text
Change only: <唯一允许改变的内容>.
Keep unchanged: identity, face, body proportions, pose, camera, crop,
perspective, product geometry, logos, text, and all unmentioned regions.
```

根据任务删除不相关项。身份保持任务优先锁定面部、体型、发型和姿态；产品编辑优先
锁定轮廓、比例、材质、标签与文字；局部替换优先锁定构图、镜头、光线方向和透视。

### 4. Generate or edit

- 交互请求通过向导 `confirm` 执行；`advanced_image_generate` 只用于已经确认的执行请求。
- 编辑：将主图放在 `image_url`，补充参考图放在 `reference_image_urls`。
- 不要在调用中编造 provider/model 参数；这些由 Hermes 配置决定。
- 不要假设编辑一定可用。动态说明为 text-only 时，向用户说明限制并提供重新生成方案。
- 返回后检查顶层 `status` 及每个 item 的 `status`、`path`、`provider`、`model`、
  `modality`、实际宽高比、attempts 和 qa。

### 5. Produce variants deliberately

不同资产使用不同 prompt。同一资产的多个版本使用 `variants` 与
`variant_instructions`，编排器会独立调用底层生成，避免把多个成品塞进一张拼图。
每版只改变一个设计轴，例如：

- 构图：居中产品 vs. 大面积文案留白。
- 风格：写实摄影 vs. 编辑插画。
- 光线：柔和日光 vs. 戏剧性轮廓光。
- 色彩：冷静中性 vs. 高饱和活动色。

把不变量保留在每个 prompt 中，文件名使用稳定且可辨认的后缀，如
`hero-centered.png`、`hero-negative-space.png`。

### 6. Handle exact text

- 把所有必须出现的文字放进 `Text (verbatim)`，保留标点、大小写和换行。
- 对易错词逐字拼写，并要求不增加其他文字。
- 使用 `qa_profile="exact-text"` 和 `required_text` 触发逐字视觉验收。
- 如果逐字准确性是硬要求且模型持续失败，生成无字底图，再用项目已有的确定性排版
  工具添加文字；不要继续声称不准确的模型文字已经通过。

### 7. Make a transparent asset

简单不透明主体使用色键流程。默认背景 `#00ff00`；绿色主体使用 `#ff00ff`。
Prompt 追加：

```text
Place the subject on a perfectly flat solid #00ff00 chroma-key background.
Use one uniform background color with no shadow, gradient, texture, reflection,
floor plane, or lighting variation. Keep crisp separated edges and generous
padding. Do not use #00ff00 in the subject. No watermark or text.
```

调用时设置 `qa_profile="transparent"` 和 `chroma_key`。编排器会追加色键约束、执行
去背、检查 alpha/角点/覆盖率，再做视觉验收。附带脚本只用于故障诊断，不是正常
交付路径。

毛发、羽毛、烟雾、玻璃、液体、半透明材质、强反射和柔影通常不适合色键。遇到这些
情况应说明需要当前 provider 的原生透明能力或专用抠图工具；不要输出粗糙结果冒充透明成品。

### 8. Inspect and iterate

编排器按以下顺序检查：文件可解码性与尺寸、透明属性、主体与需求、构图、身份/产品
不变量、精确文字、异常边缘/重复物、品牌和水印。失败后 correction prompt 只修观察到
的问题，并完整保留原始约束；最多按 `max_iterations` 重试两次，不允许无限循环。

### 9. Persist deliverables

- 底层生成可能返回 URL 或缓存路径，编排器会安全解析并持久化。
- 未传 `destination` 时保存到当前 profile 的 `output/advanced-imagegen/`。
- 项目资产应把 `destination` 指向项目目录。
- 未明确要求覆盖时，使用版本化或语义化新文件名，不覆盖已有资产。
- `accepted`/`needs_review` 使用正常文件名；失败草稿带 `-rejected`，不得当成交付物。

更多可复制配方见 `references/prompt-recipes.md`。

## Pitfalls

- 把“批量”误解为一次生成一张多宫格，而不是多个独立成品。
- 未检查动态能力就向 text-only provider 传图片。
- 编辑时只描述变化，不重复必须保持的部分，导致主体漂移。
- 让模型选择 provider/model，造成调用参数与 Hermes 配置不一致。
- 用图片生成代替已有 SVG 或代码原生资产的小改动。
- 绕过 `advanced_image_generate` 直接调用原生工具（门禁会拒绝）。
- 忽略 manifest 状态，把 `rejected` 或 `qa_error` 当成交付文件。
- 未逐字检查图片文字，或把接近正确当成正确。
- 对复杂边缘强行色键抠图，产生色边、孔洞或半透明污染。
- 一次迭代同时改构图、风格、光线和主体，无法判断哪项有效。

## Verification

交付前逐项确认：

- [ ] 使用场景 slug 与任务一致。
- [ ] 生成/编辑模式正确，所有输入图角色已标注。
- [ ] 主体、环境、构图和风格符合请求。
- [ ] 编辑不变量未漂移。
- [ ] 精确文字已逐字核对。
- [ ] 无多余人物、物体、logo、文字或水印。
- [ ] 宽高比和用途匹配。
- [ ] 透明文件通过 alpha、角点、覆盖率和色边检查。
- [ ] 项目资产已保存到项目目录，未意外覆盖旧文件。
- [ ] manifest 顶层及各 item 状态均已处理，未把失败草稿冒充成品。
- [ ] 最终回复包含所有路径、最终 prompt、使用模式以及 provider/model 回显。
