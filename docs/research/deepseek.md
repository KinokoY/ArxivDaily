# DeepSeek API 调研与任务配置建议

最终状态：用户已接受官方 `https://api.deepseek.com` 与 `deepseek-flash` 两角色，并将思考意图调整为“中等 / 极高”。按当前 provider 映射，终筛采用 `high`、总结采用最高预算 `max`，均显式 `thinking.type=enabled`；`medium` 与 `xhigh` 都映射 `high`，因此“极高”不照抄成 literal `xhigh`。这是参数映射，不是用户提供的 API literal。以下保留调研快照与旧候选建议；旧 `none/low` 终筛、`high` 总结建议已由 [最终规格](../SPEC.md) 覆盖。来源：[当前 Chat schema](https://api-docs.deepseek.com/api/create-chat-completion/)。

核查日期：2026-10-02（Asia/Shanghai）。仅查阅 DeepSeek 官方文档与官方开源项目；未读取、索取任何密钥，未调用付费模型 API，未编写应用代码。价格表的网页直读多次超时，本文价格依据官方域名搜索索引返回的完整价目内容（最近一至两周抓取）；部署前需要再次核实价目，不能把本记录当成永久报价。Vision、Chat API、Responses API 和 Thinking 文档已直接读取。

## 当前官方接口与模型

官方 OpenAI 格式 `base_url` 是 `https://api.deepseek.com`，Chat Completions 为 `POST /chat/completions`，Responses 为 `POST /responses`；另有 Anthropic 格式 `https://api.deepseek.com/anthropic`。Python 可以使用 OpenAI SDK 调用。**当前官方 API 支持图像输入**，不能沿用旧知识说“DeepSeek 官方 API 不支持图片”。来源：[首次调用](https://api-docs.deepseek.com/)、[Chat Completions schema](https://api-docs.deepseek.com/api/create-chat-completion/)、[Responses schema](https://api-docs.deepseek.com/api/create-response/)。

| 接口模型名 | 当前价目表对应版本 | 输入 | 上下文 / 最大输出 | 思考与 JSON |
| --- | --- | --- | --- | --- |
| `deepseek-flash` | DeepSeek-V4.1-Flash | 文本、图像 | 1M / 最大 384K | 非思考、思考；JSON 支持 |
| `deepseek-v4-pro` | DeepSeek-V4-Pro-0813 | 文本，**不支持图像** | 1M / 最大 384K | 非思考、思考；JSON 支持 |

模型列表 schema 的示例给出精确 `context_window=1048576`、`max_output_tokens=393216`，以及输入 modalities。旧 `deepseek-v4-flash`、`deepseek-v4-flash-vision-exp` 名仍暂时接受，但由 V4.1 Flash 服务，不能据名称假设获得旧版本。来源：[模型价格](https://api-docs.deepseek.com/quick_start/pricing/)、[模型列表说明](https://api-docs.deepseek.com/api/list-models/)。

文档历史有变化：2026-09-10 发布新闻曾计划 09-14 后把 Pro 请求路由到 Flash；较新英文价目与更新日志写继续提供 Pro，中文页面或缓存仍可能保留路由公告。选择当前明确模型配置并记录 response 中的 model/fingerprint，不按旧新闻强制迁移。`deepseek-chat`/`deepseek-reasoner` 的旧官方 API 名在 2026-07-24 后按发布说明停用；第三方提供的同名服务须单独核查。来源：[英文价目](https://api-docs.deepseek.com/quick_start/pricing/)、[更新日志](https://api-docs.deepseek.com/updates/)、[旧名停用说明](https://api-docs.deepseek.com/news/news260424/)。

中英文页面及搜索缓存可能不同步：部分旧缓存仍保留 09-14 后 Pro 路由 Flash 的脚注，其他当前价目/更新日志则写继续提供 Pro。因此不要把旧路由公告当作现状；本轮 Flash 的模型名与视觉能力已由直接读取的文档确认，Pro 的实际服务身份与可用性在开发时按用户 endpoint/model 做小规模验证。

## 图像输入方式、限制与论文图表

Flash 的图像可通过公开 HTTP(S) URL、base64 data URL，或 Files API 上传的图片 `file_id` 提供。支持 JPEG、PNG、GIF、WebP。Chat 使用 `image_url` / `file` 内容块；Responses 使用 `input_image`，`image_url` 与 `file_id` 互斥。**这里的文件能力是图片输入，不能据此承诺原生读取整份 PDF**；Responses 文档明确不支持通用 file input。论文 PDF 可由应用抽取正文并渲染关键页/图表为图片后发送。来源：[Vision](https://api-docs.deepseek.com/guides/vision/)、[Responses schema](https://api-docs.deepseek.com/api/create-response/)。

| 限制/处理 | 官方值 |
| --- | --- |
| 请求 body | 48 MiB |
| 单张图片 | base64/URL 最大 32 MiB；`file_id` 最大 64 MiB |
| 每请求图片 | 最多 600 张 |
| 总图片字节 | 无 `file_id` 时 64 MiB；含 `file_id` 时可达 200 MiB |
| 单边尺寸 | 最大 8192 px；请求包含 ≥15 张时降为 4096 px |
| 外链 | URL 最多 8192 字符，下载须 60 秒内完成 |
| 视觉 token | 按图片尺寸处理并计入输入费用，每图最多 1024 tokens |
| detail | `low` 先缩至 512×512；`high`/`original`/`auto` 当前保留原图后进入模型通用尺寸处理 |

该表来源：[Vision: Limits / Token Usage / Detail Level](https://api-docs.deepseek.com/guides/vision/)。图像处理仍会自动按像素规模缩放，因此把密集表格整页送入并不能保证小字保留。官方图像支持证明“可以输入图片”，不等于已证明本应用能准确读所有论文图表。

文档存在角色表述不完全一致：Vision restrictions 简述 Chat 图片仅 user；Chat schema 同时列出 tool 的图像内容块；Responses 明确允许 user/developer 及工具输出图像。该应用使用 **user 消息携带论文图片** 可避免依赖边缘角色兼容。来源：[Vision](https://api-docs.deepseek.com/guides/vision/)、[Chat schema](https://api-docs.deepseek.com/api/create-chat-completion/)、[Responses schema](https://api-docs.deepseek.com/api/create-response/)。

首版基础按用户已同意的“正文 + 可提取表格、图注”处理。进一步的工程建议（属于推导，尚未决定）：保留章节/页码与图表编号；需要视觉证据的关键方法图、结果图、实验表格，以清晰裁剪配合附近文字送给 Flash 高思考总结。图中看不清的数值标记缺失，不能补造。无需为首版默认引入 Pro 与 Flash 之间的多模型图像预处理流程。

## 思考、结构化输出与费用控制

当前模型默认开启思考、默认 `high`。Chat 可用 `thinking.type=enabled/disabled`，以及 `reasoning_effort=none/low/high/max`；OpenAI SDK 中 `thinking` 放在 `extra_body`。Responses 用 `reasoning.effort=none/low/high/max`。应显式配置模式，避免筛选无意中启用高思考。来源：[Thinking Mode](https://api-docs.deepseek.com/guides/thinking_mode/)、[Chat schema](https://api-docs.deepseek.com/api/create-chat-completion/)。

思考模式中 `temperature` 不生效；`top_p` 仅思考模式生效，有效范围 0.95–1.0，非思考时忽略。Chat 不设置 `max_tokens` 时，默认输出上限为非思考 8K、思考 64K（max 思考 128K），整体最高 384K。由此，六句可见总结不会天然限制隐藏推理量和输出费用。来源：[Thinking Mode](https://api-docs.deepseek.com/guides/thinking_mode/)、[Chat schema](https://api-docs.deepseek.com/api/create-chat-completion/)。

当前价目与 schema 并未把 JSON 限定为非思考模型；两种模式均可配置 JSON 输出。Chat 的 `response_format={type:json_object}` 保障 JSON 语法，不等同于业务 schema 完整；prompt 还须明确 JSON 并给目标结构。文档说明可能有空内容或长度截断，应验证字段、类型、枚举与完成状态后再保存结果。Responses 的 `text.format` 支持 `json_object` 与 `json_schema`。来源：[JSON Output](https://api-docs.deepseek.com/guides/json_mode/)、[Chat schema](https://api-docs.deepseek.com/api/create-chat-completion/)、[Responses schema](https://api-docs.deepseek.com/api/create-response/)。

Responses 并非实现所有同名 OpenAI 功能：无状态，不存 conversation，`previous_response_id`/`store`/`background` 不支持，通用 file input 和部分内置 tools 不支持；某些不支持参数会被静默忽略。此应用可使用一次论文一次请求的 Chat 接口减少兼容面，或明确采用 Responses schema 约束，并做接口能力探测。来源：[Responses compatibility guide](https://api-docs.deepseek.com/guides/responses_api/)。

## 当前价目快照

每百万 tokens 的人民币价，空闲 / 高峰：

| 模型 | 输入：缓存命中 | 输入：缓存未命中 | 输出 |
| --- | --- | --- | --- |
| Flash | ￥0.02 / ￥0.04 | ￥1 / ￥2 | ￥4 / ￥8 |
| Pro | ￥0.15 / ￥0.30 | ￥4.5 / ￥9 | ￥13.5 / ￥27 |

来源：[官方中文价目](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/)。英文价目对应每百万 tokens：Flash 缓存命中 $0.003/$0.006、未命中 $0.15/$0.30、输出 $0.60/$1.20；Pro $0.022/$0.044、$0.66/$1.32、$1.98/$3.96。来源：[英文价目](https://api-docs.deepseek.com/quick_start/pricing/)。不用汇率把这两组官方标价相互换算。

高峰北京时间周一至周五 09:00–12:00、14:00–18:00。价格会调整，按实际调用时段和账号扣费为准。GitHub Actions 延迟也可能改变实际请求落在哪个计费时段。来源：[中文价目](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/)、[英文价目](https://api-docs.deepseek.com/quick_start/pricing/)。

用户已允许北京时间 14:00–18:00 的执行窗口；15:17 落在上述当前高峰段内。这是费用记录信息，不应为省钱擅自把任务移到 18:00 以后。

费用按缓存命中输入、未命中输入、全部输出分别计算；图像 tokens 计入输入，思考 tokens 计入输出统计。因此需记录 usage，而不是仅根据推送字数估算。Responses 返回 `output_tokens_details.reasoning_tokens`；Chat 返回 `completion_tokens_details.reasoning_tokens`。来源：[Vision token usage](https://api-docs.deepseek.com/guides/vision/)、[Responses schema](https://api-docs.deepseek.com/api/create-response/)、[Chat schema](https://api-docs.deepseek.com/api/create-chat-completion/)。

按账号计算的并发上限当前为 Flash 2500、Pro 500，超过返回 429；请求等待时会 keep alive，十分钟仍未开始推理则关闭连接。日常少量论文远无需达到官方并发上限；本应用应有自己的低并发、请求超时、指数退避与重试次数。来源：[Rate Limit & Isolation](https://api-docs.deepseek.com/quick_start/rate_limit/)。

## 可复用的两任务配置

下表为建议而非已确定的配置，也不主张更贵的模型必然更适合论文总结：

| 配置项 | 最终筛选任务 | 全文总结任务 |
| --- | --- | --- |
| 服务身份 | 同一 provider/base_url/api_key 环境变量引用 | 可复用同一服务，也允许独立配置 |
| 默认候选 model | `deepseek-flash` | `deepseek-flash`，图表可直接输入 |
| 默认候选思考 | `none` 或 `low`，样本验证再选 | `high`，必要时再评估 `max` |
| 输入 | 规则匹配证据、标题、摘要、分类与用户兴趣 | 合格全文、章节/页码、关键图表、图注和筛选理由 |
| 输出 | `decision`、相关度、简短原因、匹配/排除证据、`uncertain` | 六句分段总结、依据章节/图表、阅读范围与缺失信息 |
| 输出协议 | Chat JSON 或 Responses JSON Schema | 同左，最终推送只渲染总结正文 |
| 容量设置 | 独立 max_tokens、timeout、重试上限 | 独立更大 max_tokens、timeout、图像数量与正文 token 上限 |
| 提交前校验 | 不把空结果、JSON 错误、截断视为“拒绝论文” | 不把摘要替代全文、缺失方法/实验证据视为合格总结 |

调研阶段优先候选为 Flash 较低推理预算终筛、Flash 较高思考正文与必要图表总结；用户现已确认同一 model 两角色，并调整思考预算，最终 `high/max` 映射见顶部状态及最终规格。Pro 属于可独立配置的纯文本备选，不作为本轮默认。两角色不要求两把 key，也不要求第二角色的单价更高；其总调用成本通常因全文、图像、推理量更大而更高。

建议把服务参数和业务质量策略分开：`provider`、`protocol`、`base_url`、`model`、`thinking/effort`、`max_output_tokens`、`timeout`、`retries`、`supports_images` 是可复用配置；秘密仅用环境变量/Actions secrets 引用。用户表示自行控制成本，可将预算/每日篇数设为可选配置，仍记录实耗并保留超时/失败候选。

## 开发时配置与验证

1. 官方服务与模型默认值已确认，不再作为待用户回答的业务问题。开发时按最终规格实现 `high/max` 两配置，并复核协议、支持能力与实际返回字段。
2. 输出上限、超时、重试等常规实现参数由开发给可配置默认值并通过样本校准，不重新开启 grilling；首版按正文与必要图表取得证据，不能把图片接口等同于原生 PDF 输入。
3. 未来用户主动改为第三方服务时，才按其公开文档或不含密钥的配置样例核查模型映射、vision、context、JSON/Responses 兼容与价格；记录 base_url 时去除任何凭据或签名。

API key 留到实际开发部署阶段由用户设置 secrets；本轮不需要。

## 其他 DeepSeek 系列与第三方差异

官方另有 DeepSeek-VL2 与 Janus/Janus-Pro 等开源多模态项目，README 有图像理解/图表理解或多模态推理代码；它们不自动等同于 `api.deepseek.com` 当前模型，也不能把其本地模型名、上下文或能力套用到官方 Flash/Pro API。第三方若提供这些系列，必须按其真实 model 和接口验证。来源：[DeepSeek-VL2 官方仓库](https://github.com/deepseek-ai/DeepSeek-VL2)、[Janus 官方仓库](https://github.com/deepseek-ai/Janus)。不建议为本需求默认把大型视觉模型部署到免费标准 Actions runner。
