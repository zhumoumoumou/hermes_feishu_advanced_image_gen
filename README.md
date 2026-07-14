# Advanced ImageGen for Hermes

这是一个面向成品交付的 Hermes 生图编排插件。它提供统一模型工具
`advanced_image_generate`，内部复用 Hermes 已配置的 `image_generate` provider，
完成生成、文件检查、视觉验收、有界定向重试、持久化和交付状态控制。

## 启用

```bash
hermes plugins enable advanced-imagegen --no-allow-tool-override
```

重启或新建 Hermes 会话后，显式加载技能：

```text
请先调用 skill_view("advanced-imagegen:studio")，然后为我的产品生成三版 16:9 主视觉。
```

如未配置生图后端，请先运行 `hermes tools`，选择 Image Generation provider 和模型。
模型和 provider 由用户配置，技能不会在调用中偷偷切换。

## 目录

- `skills/studio/SKILL.md`：高级生图与编辑工作流。
- `orchestrator.py`：生成、质检、重试、持久化与交付状态机。
- `skills/studio/references/prompt-recipes.md`：可复制的提示词配方。
- `scripts/remove_chroma_key.py`：将纯色色键背景转换为透明通道。
- `scripts/inspect_image.py`：检查尺寸、模式、透明度和文件信息。
- `tests/test_plugin.py`：插件注册与脚本级测试。

透明背景脚本和检查脚本依赖 Pillow：

```bash
python -m pip install pillow
```

## 控制模型

- Agent 必须调用 `advanced_image_generate`；直接调用 `image_generate` 会被门禁拒绝。
- 编排器内部仍走 Hermes 原生 provider 链，不覆盖底层工具或更换模型。
- 是否支持参考图编辑取决于当前 provider/model 的动态能力描述。
- 每个变体独立生成；视觉验收失败最多定向重试两次。
- `accepted` 才是机器验收成品；`needs_review` 等待人工确认；失败草稿带
  `-rejected`，不得冒充交付物。
- 复杂毛发、烟雾、玻璃等原生透明需求不会伪装成可靠的色键抠图。
- 默认非破坏性命名；项目资产可通过 `destination` 直接持久化到项目目录。
