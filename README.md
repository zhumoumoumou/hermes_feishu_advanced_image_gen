# Advanced ImageGen for Hermes

这是一个面向成品交付的多供应商生图编排插件。它把供应商、模型、模型族 Prompt
Skill、限流、异步任务、错误处理、自动验收和交付状态放在同一条受控工作流里。
Hermes Agent 自带的 `image_generate` 以 `hermes-native/active` 供应商模型提供。

## 启用

```bash
hermes plugins enable advanced-imagegen --no-allow-tool-override
```

重启 Gateway 或新建 Hermes 会话后，用户可以直接描述生图需求：

```text
为我的产品生成三版 16:9 主视觉，每版只改变一个设计轴，交付前严格验收。
```

如未配置生图后端，请先运行 `hermes tools`，选择 Image Generation provider 和模型。
这项配置只决定 `hermes-native` 的上游模型；外部供应商与模型由本插件目录和向导选择。

## 工具与向导

- `advanced_image_wizard`：持久化多轮向导，依次完成供应商/模型选择、Prompt Skill
  路由、草稿确认和 API 调用。
- `advanced_image_catalog`：列出、描述、校验和热重载供应商/模型目录。
- `advanced_image_generate`：执行已经确认的请求；向导内部最终调用这套编排逻辑。
- 原生 `image_generate` 的模型侧调用会被 hook 拒绝并指向向导。

向导顺序固定为：`start → select → 讨论 Prompt → draft → 用户确认 → confirm`。
`draft` 只生成确认摘要，不调用供应商 API；`confirm` 必须带
`confirmed=true`，并且只应在用户明确同意后调用。

模型目录返回 `prompt_skill`。相同模型族即使来自不同供应商，也可引用同一个 Skill；
例如 AtlasCloud 与 ByteDance 的 `seedream-5-pro` 都映射到
`advanced-imagegen:prompt-seedream-5-pro`。

## 供应商配置

默认只启用完整可用的 `hermes-native/active`。外部供应商配置放在当前 profile 的：

```text
$HERMES_HOME/advanced-imagegen.yaml
```

从 [`config.example.yaml`](config.example.yaml) 复制起步。API Key 只通过
`api_key_env` 指向环境变量，不能写入 YAML。示例中的 AtlasCloud/ByteDance endpoint、
上游 model id 和 JSON 路径是待替换的 transport 模板，不代表供应商当前正式接口。

外部 `http-json` 适配器支持：

- 文生图、主输入图与多参考图字段映射；
- 同步 JSON 返回或提交任务后轮询；
- QPS、TPM、最大并发和最大本地等待；
- 指数退避、抖动、`Retry-After` 与幂等键；
- HTTP/网络/鉴权/限流/异步失败/响应契约的统一错误码。

当前限流器是单 Gateway 进程内的保护，不是跨机器分布式配额器。真实接入新供应商时，
应按其官方 API 文档校准 endpoint、字段、状态值、配额和错误码；契约差异较大时新增专用
adapter，而不是不断扩张通用映射。

## 目录

- `skills/studio/SKILL.md`：高级生图与编辑工作流。
- `orchestrator.py`：生成、质检、重试、持久化与交付状态机。
- `runtime/catalog.py`：profile 本地供应商与模型目录。
- `runtime/providers.py`：Hermes Native 与声明式 HTTP/JSON 适配器。
- `runtime/rate_limit.py`：异步 QPS/TPM/并发控制。
- `runtime/wizard.py`：持久化多轮选择、确认与执行向导。
- `config.example.yaml`：外部供应商接入模板。
- `skills/studio/references/prompt-recipes.md`：可复制的提示词配方。
- `scripts/remove_chroma_key.py`：将纯色色键背景转换为透明通道。
- `scripts/inspect_image.py`：检查尺寸、模式、透明度和文件信息。
- `tests/test_plugin.py`：插件注册与脚本级测试。

透明背景脚本和检查脚本依赖 Pillow：

```bash
python -m pip install pillow
```

## 控制模型

- Agent 默认从 `advanced_image_wizard` 开始；直接调用 `image_generate` 会被门禁拒绝。
- 用户和上层 Agent 不需要显式提示“先加载 Skill”。
- 选择 `hermes-native` 时仍走 Hermes 原生 provider 链，不覆盖底层工具或更换模型。
- 是否支持参考图编辑取决于当前 provider/model 的动态能力描述。
- 每个变体独立生成；视觉验收失败最多定向重试两次。
- `accepted` 才是机器验收成品；`needs_review` 等待人工确认；失败草稿带
  `-rejected`，不得冒充交付物。
- 复杂毛发、烟雾、玻璃等原生透明需求不会伪装成可靠的色键抠图。
- 默认非破坏性命名；项目资产可通过 `destination` 直接持久化到项目目录。
