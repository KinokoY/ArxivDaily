# 每日 arXiv 简报推送调研

查证日期：2026-10-02（Asia/Shanghai）。仅查阅公开官方文档；未使用用户账号，也未发送测试消息。下列“推荐”是基于每日 1 份私人日报的推断，尚待用户选择。

## 可用方案比较

| 方案 | 成本、额度 | 接收条件 | 正文与阅读体验 | 适用性 |
| --- | --- | --- | --- | --- |
| Server酱 Turbo + 微信服务号 | 注册即免费，每日最多 5 条；每分钟 50 条。官方促销订阅价 8 元/月、39 元/年，以购买页为准 | 微信扫码登录取得 SendKey，保持关注接收服务号；普通微信即可 | 正文支持 Markdown（含表格、图片），不支持 HTML；免费卡片仅显示标题，需要进入详情阅读。免费详情仅保留 1 天，会员 3 天 | 每天合并 1 份日报额度足够；历史日报需要应用另存 |
| PushPlus + 微信服务号 | 实名非会员每日 200 请求、每分钟 5 请求；未实名发送额度 0。实名认证本身收费，或购买 1 个月会员免额外认证费；会员标价 10 元/月 | 关注“pushplus 推送加”，建立账号，提供姓名、身份证号、手机号并完成实名验证 | 非会员标题 100 字、正文 2 万字；支持 HTML/Markdown；历史存储 30 天。免费模板消息主要显示标题，点击查看详情 | 能容纳长日报，但不是完全零成本开户；公众号共享模板额度可能当日耗尽 |
| 邮件 SMTP（以已有 QQ 邮箱为例） | 无需购买推送平台订阅；本次没有查到可据以保证的 QQ SMTP 固定免费日额度，因此不承诺无限发送 | 用户自行开启 IMAP/SMTP 或 POP3/SMTP，取得专用授权码；收件人使用已有邮箱/邮件客户端即可 | 适合发送完整 HTML 日报，并附纯文本替代。Markdown 需先转换为 HTML 或作为附件；实际大小及反垃圾限制由邮箱服务决定 | 推荐作为完整简报的主渠道，方便检索、保存和跨设备阅读 |
| Server酱³ App | 当前官方写测试期间免费，正式版收费标准与 Turbo 一致；不应把测试期免费作为长期承诺 | 独立账号、安装 iOS/Android App，与 Turbo 用户和 SendKey 不通用 | 独立 App 阅读；服务端缓存 72 小时，客户端收到后本地保存 | 用户愿意安装 App 时可备选 |

Server酱额度、价格、保留时间和格式依据：[官方 FAQ](https://sct.ftqq.com/docs/getting-started/faq/)。微信通道及卡片行为依据：[官方通道对比](https://sct.ftqq.com/docs/getting-started/channels/)。注册与接收前提依据：[获取 SendKey](https://sct.ftqq.com/docs/getting-started/sendkey/)。标题最长 32 字符依据：[官方 SendKey 页面](https://sct.ftqq.com/sendkey/)。本次未在可读取的当前官方文档中核实 Turbo 正文的数值长度上限，不把第三方常见的“32 KB”写成已验证事实；开发时需要查询控制台/API 文档并做边界测试。

PushPlus 额度及保留时间依据：[系统功能额度](https://pushplus.plus/doc/guide/use.html)。账号手续依据：[实名认证说明](https://pushplus.plus/doc/function/verify.html)，订阅价依据：[会员功能](https://www.pushplus.plus/doc/function/vip.html)。正文模板依据：[消息接口文档](https://www.pushplus.plus/doc/guide/api.html)，免费卡片行为依据：[如何显示推送内容](https://www.pushplus.plus/doc/help/showmessage.html)。

QQ SMTP 官方配置依据：[腾讯云 CloudBase 自定义 SMTP 指南](https://docs.cloudbase.net/authentication-v2/method/email-login)：`smtp.qq.com`，465 + SSL 或 587 + STARTTLS，用户名为发件邮箱，密码为专用授权码。直接访问 QQ 邮箱帮助链接本次只得到帮助目录，因此采用腾讯官方现行配置文档。HTML 正文方式依据：[腾讯官方 QQ 邮箱连接器文档](https://help.apaas.cloud.tencent.com/docs/product/%E4%BD%BF%E7%94%A8%E6%8C%87%E5%8D%97/%E6%B5%81%E7%A8%8B%E5%AE%9A%E4%B9%89/%E8%BF%9E%E6%8E%A5%E5%99%A8)。

## 不应承诺的微信行为

PushPlus 官方说明：微信公众号模板消息有平台整体日额度；若耗尽，全部用户当天可能无法走微信通道。其发送接口是异步接口，“请求成功”仅说明请求接收，需要用流水号查询最终状态或配置回调。依据：[发送接口限制](https://www.pushplus.plus/doc/help/limit.html)。

PushPlus 的“激活消息”只是临时客服消息模式，需要用户主动交互。官方两页分别写 24 小时/5 条和 48 小时/5 条，存在冲突，不应将它作为无人值守长期方案的前提。依据：[内容显示](https://www.pushplus.plus/doc/help/showmessage.html)、[激活消息](https://www.pushplus.plus/doc/help/activation.html)。

企业微信应用/群机器人可以作为已有企业微信使用者的备选，但它需要额外的企业或群配置；本次官方机器人详细页抓取失败，未独立确认最新正文上限与客户端条件，因此不建议首版基于旧教程实现“私人微信机器人”。Server酱官方通道页确认有企业微信应用与群机器人通道，但不能据此推断任意个人微信群均可配置。

## 推荐首版路径与待决策

推荐：每日发送 1 封完整 HTML 邮件；用户希望微信提醒时，再用 Server酱 Turbo 发 1 条带日期、论文数量及简报入口的通知。若简报入口为私有 GitHub 内容，微信浏览器可能需要 GitHub 登录；若用户不接受该阅读步骤，就在 Server酱详情内附精简日报并靠邮件/应用存档保存完整版。该建议优先保留阅读与历史检索体验，最终渠道由用户决定。

需要确认：

1. 邮件、微信或独立 App 哪个是必须的，哪个只是备选？是否能接受点击详情阅读？
2. 是否已有可用于 SMTP 的 QQ/163/Gmail 等邮箱，愿意自己在邮箱网站生成专用授权码并填入 GitHub Secrets？不需要在聊天中给出密钥。
3. 微信路径选择免平台订阅的 Server酱、需要实名开户的 PushPlus，还是已有企业微信通道？
4. 每日合并一份日报还是逐篇发送？无论文时静默还是发送“今日无匹配”？
5. 推送成功需要记录到何种程度：服务接收、查询最终投递状态，还是需要另一个渠道在失败时补发？
6. 日报存档是否可公开？保存多久？若只用 Server酱，是否接受免费详情 1 天后不可访问？

实现阶段应分别记录日报生成状态与各渠道投递状态，限制重试，并测试目标 GitHub Actions runner 到 SMTP/推送服务的实际连通性。SMTP 服务接受邮件也不代表邮件已经进入收件箱，仍可能延迟、退信或进入垃圾邮件；不能把邮件描述为绝对可靠。用户未提供凭证前，连接可用性与真实到达尚未验证。
