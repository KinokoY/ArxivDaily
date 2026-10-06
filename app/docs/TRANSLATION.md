# 标题与摘要翻译选型

核查日期：2026-10-07。免费额度均针对官方 API，不是网页翻译的自动化接口。额度与账号资格以服务商页面为准。

| 方案 | 免费方式 | 本项目接入 | 适用判断 |
| --- | --- | --- | --- |
| DeepL API Free | 每月 500,000 个字符 | `translation.provider = "deepl"` | 适合先用少量真实论文比较译文，标题和摘要使用 text API，不走文档计费 |
| Microsoft Azure Translator F0 | 每月 2,000,000 个字符 | 尚未接入 | 候选多时值得考虑；需 Azure 资源和密钥，官方另有中国区入口 |
| Google Cloud Translation NMT | 每月前 500,000 字符，以 $10 抵扣形式提供 | 尚未接入 | 有 Google Cloud 账号时可考虑；超过额度产生费用，LLM 翻译不适用此免费额度 |
| LibreTranslate | 自建开源服务，无第三方按字符 API 费用 | `translation.provider = "libretranslate"` | 需要自己提供机器与维护；官方托管 API key 收费，不等同于自建免费 |
| 现有 LLM | 按原 API 计费，无免费承诺 | `translation.provider = "llm"`，默认 | 无额外账号；可在提示里明确学科、术语、公式和缩写，项目只提交标题/摘要，关闭思考 |

若平均每篇标题加摘要约 2,000 个英文字符，50 万字符大约覆盖 250 篇/月，200 万字符约 1,000 篇/月。这只是容量估算，实际长度、重试和标题索引的补译会影响用量。

这里没有足够证据把某个免费通用 API 称为“专门针对你的学术领域优化”。建议先沿用 LLM 翻译，拿 10–20 篇医学分割、拓扑损失、RL/DPO 论文比较 DeepL；重点检查专业词义、否定/限定语、公式、指标数字与模型名称。Google Advanced 支持术语表和定制，但通用免费额度不意味着定制训练和所有附加功能免费。LibreTranslate 的 Argos 引擎也没有本项目所需学科的质量保证；它的优势是自建控制和费用可控。

本项目的 LLM 提示要求忠实完整翻译、统一学术术语、保留 LaTeX/数字/数据集名/模型名/缩写，不扩写也不总结。LLM 复用 `llm.filter` 的配置，使用非思考请求；如果改用不同模型或端点，仍需正确填写 `llm.pricing` 的 custom 价格策略。英文原文保留在通知和日报里，便于对照。

## 配置

```toml
[workflow]
mode = "translation"

[translation]
provider = "deepl"
base_url = "https://api-free.deepl.com"
api_key_env = "TRANSLATION_API_KEY"
```

API key 配置为环境变量或 Actions Secret，不写入 TOML。切换自建 LibreTranslate 时同时修改 provider 和 base_url：

```toml
[translation]
provider = "libretranslate"
base_url = "http://localhost:5000"
api_key_env = "TRANSLATION_API_KEY"
```

LibreTranslate 若关闭鉴权可不设置该密钥。远程服务使用 HTTPS；Actions 不能通过 localhost 访问你个人电脑上的实例。无论哪个后端，摘要终筛仍使用现有 LLM；机器翻译免费不意味着整个 pipeline 完全没有 LLM 成本。

译文与中文标题保存到 `state.json`；恢复投递复用既有译文，不因配置变化重译。处理失败保持待恢复，跨运行次数和时间受原阶段机制约束，可用 `--retry-stage translation --retry-ids ID` 重开有限尝试。单独的索引标题补译使用 `--retry-stage title_translation`，此操作只更新索引，不重投已确认论文。正常无新增通知共享 Server酱每天的发送配额，抓取/处理失败不会被写成无新增。

## 官方来源

- [DeepL API Free 的字符额度](https://support.deepl.com/hc/en-us/articles/360020685720-Usage-count-and-billing-in-DeepL-API)
- [DeepL 文本翻译 API](https://developers.deepl.com/api-reference/translate/request-translation)
- [Microsoft Translator API 与免费订阅](https://www.microsoft.com/en-us/translator/business/translator-api/)
- [Google Cloud Translation 定价](https://cloud.google.com/products/translate/pricing)
- [Google Cloud Translation 能力与术语表](https://cloud.google.com/translate)
- [LibreTranslate 自建说明](https://docs.libretranslate.com/)
- [LibreTranslate 托管密钥收费说明](https://docs.libretranslate.com/guides/manage_api_keys/)
