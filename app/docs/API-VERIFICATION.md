# 开发阶段接口事实复核

更新：2026-10-03（Asia/Shanghai）。公开论文来源已有校验；本轮重新核查官方 DeepSeek schema/价目与 GitHub schedule timezone，并执行有限真实 DeepSeek 调用。本轮微信发送 0 次，真实 GitHub/Ubuntu 尚未执行。

- [arxiv 4.0.1 PyPI](https://pypi.org/project/arxiv/4.0.1/)：使用 Client.results(Search)，移除的下载方法未调用。安装后的真实 Client 通过合成 feed 分页测试，四个固定版本 ID 的真实元数据请求也成功。
- [DeepSeek Thinking](https://api-docs.deepseek.com/guides/thinking_mode/) 与 [Chat schema](https://api-docs.deepseek.com/api/create-chat-completion/)：默认 Flash 的筛选 high、总结 max，显式 thinking enabled；只接受正常 stop 完成的完整 JSON，并进行业务与证据校验。
- [DeepSeek 官方中文价目](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/)：当前 Flash 默认名映射到 V4.1 Flash，支持图像与 JSON。配置取高峰 CNY 单价（缓存输入 0.04、未缓存输入 2、输出 8 / 百万 tokens）作保守上界；实际计费还受时段/日期/价格变更影响，usage 中保留实际 model/fingerprint，不能把估计当精确账单。
- [Server酱官方集成](https://sct.ftqq.com/docs/integrations/activepieces/) 支持 SendKey POST title/desp，免费五条/日。当前适配器只把已识别业务成功记 queued，同轮使用内存 readkey 有限查询。完整 wxstatus 枚举、查询是否消耗额度、平台日界、实际详情长度与免费账号投递体验必须用用户账号联调确认；未识别返回保留 unknown。

真实 DeepSeek 两次终筛返回正常 `stop`、可用 usage 和 reasoning token 计数，high 下 LISA 为 light、MediSee 为 full，均非 RL/DPO。MediSee 总结用 max、合格固定版 HTML 与两张同版本 PDF 关键页。失败尝试与最终质量核查分别保存于 `../reports/live-api-smoke.json`，不公开 reasoning 内容。这是小样本联调，不能外推为终筛精度或任意图像数字准确率。

GitHub 官方 [workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#onschedule) 支持 schedule timezone；根工作流使用 `17 15 * * *` + `Asia/Shanghai`。上游固定源码与原许可已导入，Git publisher 在本地 bare remote 做过真实事务；公网 raw URL 在该测试中模拟，真实 workflow/远程归档仍待部署。
