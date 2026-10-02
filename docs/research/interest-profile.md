# 研究兴趣与代表论文核查

核查日期：2026-10-02（Asia/Shanghai）。范围：arXiv 的具体版本、论文全文的任务 / 方法 / 训练段落，以及论文指向的作者官方仓库。没有下载到外部目录、执行代码或开发应用。以下论文事实与兴趣建议分开；**建议均未替代用户决定，也不是已实现的配置文件 schema**。

## 当前用户兴趣：已知事实与尚需确认的边界

- 核心：医学领域 reasoning segmentation。
- 医学直接相关工作优先；通用领域 reasoning segmentation 重点关注 RL / DPO。
- 传统 segmentation / SAM 只有损失设计、有较好理论、能迁移到用户研究时才感兴趣。
- 用户最新意向是初筛关键词**仅匹配摘要**；标题用于展示和 LLM 信息输入，标题关键词规则只有后续明确开启时才启用。
- 用户提供 LISA、Medisee / PRS-Med、ARIADNE 作为代表名称。它们是兴趣理解与回放校准的样例，不应自动把四篇都标成当日推送正例。

尚需用户决定：① 通用、无 RL / DPO 的 reasoning segmentation 是否仍低优先级保留；② 医学普通分割是否仍需要推理要素，或医学 RL / DPO / 拓扑目标即使没有自然语言推理也可独立纳入。下面的分组有意保留这两处开关。

## 精确论文对应

| 名称 | 精确标题 | arXiv / 年份 / 当前核查版本 | 与 medical / general / RL / DPO 的关系 |
|---|---|---|---|
| LISA | LISA: Reasoning Segmentation via Large Language Model | [2308.00692](https://arxiv.org/abs/2308.00692)，2023-08-01 首发；[v3](https://arxiv.org/abs/2308.00692v3) 2024-05-01；CVPR 2024 | 通用自然图像 reasoning segmentation；原方法是监督学习 / LoRA，不是 RL / DPO |
| 用户写的 Medisee | **MediSee: Reasoning-based Pixel-level Perception in Medical Images** | [2504.11008](https://arxiv.org/abs/2504.11008)，2025-04-15 首发；[v2](https://arxiv.org/abs/2504.11008v2) 2025-04-23；作者仓库标明 ACM Multimedia 2025 | 医学 implicit-query reasoning segmentation **与 detection**；监督学习 / LoRA，不是 RL / DPO |
| PRS-Med | 当前标题：**PRS-Med: Position Reasoning Segmentation in Medical Imaging** | [2505.11872](https://arxiv.org/abs/2505.11872)，2025-05-17 首发；[v4](https://arxiv.org/abs/2505.11872v4) 2026-03-31；作者仓库标明 CVPRW 2026 | 医学 position / spatial reasoning segmentation；LLaVA-Med + TinySAM / mask decoder，监督学习 / LoRA，不是 RL / DPO |
| ARIADNE | **ARIADNE: A Perception-Reasoning Synergy Framework for Trustworthy Coronary Angiography Analysis** | [2603.19169v1](https://arxiv.org/abs/2603.19169v1)，2026-03-19；本次只见 v1 | 医学冠脉造影；DPO 对齐血管拓扑，PPO / RL 做狭窄定位；这里的 diagnostic reasoning 是几何状态上的策略决策，不是语言 CoT |

命名与版本注意：

1. `MediSee` 是论文及作者仓库的大小写形式。其 [arXiv 全文](https://arxiv.org/html/2504.11008v2) 直接指向 [Edisonhimself/MediSee](https://github.com/Edisonhimself/MediSee)，因此医学推理分割语境下可高置信映射用户的 Medisee。不要误认成同名药物不良反应软件。
2. PRS-Med 的 [v1](https://arxiv.org/abs/2505.11872v1) 标题为 **PRS-Med: Position Reasoning Segmentation with Vision-Language Model in Medical Imaging**，数据称 MMRS；[v4](https://arxiv.org/abs/2505.11872v4) 标题省去 with Vision-Language Model、数据称 PosMed，作者列表也变动。最新元数据为 Quoc-Huy Trinh、Minh-Van Nguyen、Jun Zeng、Debesh Jha、Ulas Bagci；v1 则含 Jung Peng。官方 README 的 BibTeX 仍保留旧标题 / 名称，论文记录以具体 arXiv 版本为准，不能把搜索缓存的旧题名误当作另一篇论文。
3. ARIADNE 名称本身不是全局唯一论文标识，但上述论文的 medical + DPO + topology + RL 组合与用户语境高度吻合。论文 [全文](https://arxiv.org/html/2603.19169v1) 明确给出代码地址 [qimingfan10/ARIADNE](https://github.com/qimingfan10/ARIADNE)。用户未提供链接，因此“这就是用户意指的 ARIADNE”仍是语境推断；目前没有发现需要强制用户补链才能继续的实质歧义。
4. LISA 原论文链接的 [dvlab-research/LISA](https://github.com/dvlab-research/LISA) 当前跳转到 [JIA-Lab-research/LISA](https://github.com/JIA-Lab-research/LISA)。不要误用其他领域同名 LISA；[CVPR 2024 官方论文 PDF](https://openaccess.thecvf.com/content/CVPR2024/papers/Lai_LISA_Reasoning_Segmentation_via_Large_Language_Model_CVPR_2024_paper.pdf) 和作者仓库可互证。

## 方法归纳与兴趣映射

### LISA：领域基准、无 RL 的通用样例

输入自然图像和隐含、复杂指令，推断目标并输出 mask。方法将新增 SEG token 的隐藏表示投影到 SAM 的 mask decoder，把语言理解与分割连接起来；训练目标为文本 CE 与 mask 的 BCE / Dice，采用 LoRA。它说明 reasoning segmentation 本身不等于强化学习，适合校准任务定义与迁移价值。是否把今后类似的无 RL 通用工作送入总结，需要用户确认；LISA 原文作为代表可留在回放集。[方法与训练目标](https://arxiv.org/html/2308.00692v3#S4.SS1)

### MediSee：医学推理分割 / 检测样例

针对需要医学知识与逻辑的口语化隐含请求，输出 mask、box 和解释；创建 MLMR-SD 数据，结合 LLaVA-Med、MedSAM 与多个候选 token，通过路由融合分别供给下游解码器。训练使用文本、mask、box 监督，并在额外微调加入视觉语义相似图损失。其核心是医学推理任务、交互与监督，不要求 RL / DPO 才相关；也不能因使用 MedSAM 就归入“普通 SAM 改良”并拒绝。[全文任务与方法](https://arxiv.org/html/2504.11008v2#S4)

### PRS-Med：医学位置推理样例

关注病灶或解剖结构的相对位置，以医学 VLM 与分割头同时输出 mask 和位置说明。当前 v4 构造有专家审核的 PosMed 空间问答，LLaVA-Med 采用 LoRA，TinySAM 图像特征与语言表示融合；目标是 mask 的 BCE / Dice 加文本 CE。全文提到其他工作的 RL 不代表 PRS-Med 自身用 RL，应把“相关工作”与“本方法”区分。它符合医学 position reasoning，即使标题不用 exact phrase reasoning segmentation。[v4 框架与训练](https://arxiv.org/html/2505.11872v4#S4)

### ARIADNE：医学 DPO / 拓扑目标、非语言 CoT 的样例

先对 Sa2VA 血管分割进行拓扑偏好对齐，利用 Betti 数与连接结构定义 preferred / non-preferred mask，再根据分割的血管中心线和局部形态构建狭窄候选，由独立 PPO 策略导航、确认或拒绝不确定候选。它体现 DPO 从语言对齐向几何 / 医学结构约束迁移的价值。**摘要没有固定短语 reasoning segmentation**，却直接涉及 vessel segmentation、DPO、RL；初筛硬要求那个短语会误杀。不能根据标题里的 reasoning 把它写成“LLM 生成医学思维链”；也不应仅凭作者的贡献宣称就判定有严格理论保证。[感知与 RL 方法全文](https://arxiv.org/html/2603.19169v1#S2)

## 可供后续初始配置使用的建议

本节是**候选规则建议**：按用户最新意向，默认关键词只匹配 abstract；标题用于展示和 LLM 信息输入，不参与关键词命中。标题规则只有用户后续明确开启时才启用。分类是否作为候选边界及其范围待下一轮确认；**没有全文关键词规则**。读上述论文全文是为了核查兴趣，不能据此暗中启用应用正文检索。所有规则先宽召回，再由低成本 LLM 判断任务、贡献、理论和迁移；最终是否总结由用户确认的偏好决定。

### 分类范围

若用户确认启用分类候选边界，建议的 OR 组为 `cs.CV`、`eess.IV`、`cs.AI`、`cs.LG`；是否启用及具体范围待下一轮确认。其中 cs.CV 是主范围，eess.IV 补影像分割，cs.AI / cs.LG 补视觉语言与优化方法。启用时建议采用文章全部分类中的任一命中，避免仅按 primary category 判断。四篇代表都含 cs.CV，MediSee 与 ARIADNE 还含 cs.AI；不能把医学工作必须具有 q-bio 类别设为门槛。[arXiv 官方分类表](https://arxiv.org/category_taxonomy)

### 摘要的同义词 OR 组

下表每行内部为 OR；组与组的组合见下一节。默认只在摘要中匹配，不与标题命中取并集。大小写不敏感，规范连字符 / 空格；`RL`、`DPO`、`PPO`、`GRPO`、`CT`、`MRI` 等缩写需完整词匹配，避免字符子串误命中。一个 acronym 在摘要中只是 baseline / 相关工作时，交给 LLM 核查，不直接认作本方法。

| 组 | 建议关键词 / 同义词 | 用途 |
|---|---|---|
| SEG | segmentation; segmenting; segmentation mask; semantic segmentation; instance segmentation; pixel-level perception; pixel-wise perception; vessel segmentation | 识别输出 mask 的分割任务；不独用 mask 这个泛词 |
| REASON | reasoning segmentation; reasoning-based segmentation; position reasoning; positional reasoning; spatial reasoning; medical reasoning; implicit query; implicit queries; implicit instruction; complex instruction; chain-of-thought; chain of thought; visual reasoning | 宽召回推理任务；不只查一个 fixed phrase，也不把出现 reasoning 视为证明 |
| VLM | vision-language model; vision language model; multimodal large language model; multi-modal large language model; MLLM; VLM; large language model; language-guided segmentation; text-guided segmentation | 捕获措辞不同的视觉语言分割；单独出现不能证明有推理 |
| MED | medical; biomedical; clinical; radiology; radiologist; anatomical; anatomy; pathology; lesion; tumor; tumour; MRI; CT; X-ray; ultrasound; endoscopy; angiography; coronary; retinal; histopathology; polyp | 医学 / 影像领域；模态或器官词只作召回线索 |
| RL_PREF | reinforcement learning; direct preference optimization; preference optimization; preference alignment; preference-based learning; policy optimization; reward optimization; RLHF; DPO; PPO; GRPO; RL | RL 或偏好优化；DPO 与 RL 分开标记，不把 DPO 强行算成 PPO 类型的在线 RL |
| OBJECTIVE | loss; loss function; objective; optimization; regularization; boundary; topological; topology; connectivity; Betti; structural constraint; clDice | 捕获损失、目标与结构约束；**理论关键词不是必需门槛** |
| SAM | segment anything; segment anything model; SAM; SAM2; SAM 2; MedSAM | 普通 / 医学 SAM 工作候选；缩写 SAM 应与 SEG 或明确模型上下文搭配 |
| THEORY_HINT | theoretical; theory; provable; theorem; convergence; generalization bound; guarantee; transferability; transferable | 仅提高相关性 / 提供给 LLM 的提示；缺失不直接拒绝 |

不建议用 `LISA` / `MediSee` / `PRS-Med` / `ARIADNE` 本身作为后续论文的必要关键词：新工作未必在标题或摘要中提到基准，LISA / ARIADNE 还可能跨领域重名。可以把已核查 arXiv ID 加入固定回放样例，而非日常必要词。

### 建议的候选路线：路线之间 OR

1. 医学推理分割：`MED AND SEG AND (REASON OR VLM)`。允许 MediSee / PRS-Med 类监督方法进入；LLM 判断是否真正有隐含请求、空间推理或相关的医学推理任务。
2. 通用 RL / DPO 推理分割：`SEG AND (REASON OR VLM) AND RL_PREF`。优先度较高；若 RL / DPO 只出现在比较基线或相关工作，不能因此选择。
3. 医学结构 / 优化：`MED AND SEG AND (RL_PREF OR OBJECTIVE)`。捕获 ARIADNE 等没有 exact reasoning segmentation 的医学 DPO / 拓扑方法；是否所有此类都纳入，受“医学普通分割需要怎样的推理要素”答案约束。
4. 传统分割 / SAM 的可迁移方法候选：`SEG AND (OBJECTIVE OR SAM)`。**不要求 THEORY_HINT，也不要求 transfer 词显式出现在摘要**；LLM 检查是否有实质损失 / 目标设计、理论依据、可向 reasoning segmentation / 医学迁移，而非仅架构拼装或指标小涨。词面规则无法确定“较好理论”和“可迁移”。
5. 可选低优先级通用 reasoning segmentation：`SEG AND REASON`，且不命中医学或 RL 优先路线。该路线启用与否待用户答复；不能因 LISA 是代表就默认永久开启全部无 RL 通用工作。

以上各路线无需互斥；重复文章保留命中理由后只评一次。负向过滤不建议一刀切排除 classification、detection、SAM、Dice：代表工作可能同时包含这些任务 / 目标，例如 MediSee 的 detection、ARIADNE 的 stenosis detection。应拒绝“核心只是分类 / 文本 QA，分割仅背景提及”等语义情形。

## 建议提供给最终筛选 LLM 的判定维度

1. 领域：medical / general；是否直接对应医学影像中的分割目标。
2. 任务：隐含语言请求、位置 / 空间推理、诊断结构决策、普通显式 referring / conventional segmentation；不要把这些都折叠成一个 reasoning 标签。
3. 方法：监督、RL、DPO / 偏好优化；对应的是本研究方法还是仅相关工作 / baseline。
4. 贡献：是否改变推理到 mask 的关系、可迁移 loss / reward / structure constraint，还是只换 backbone、加模块或报更高 Dice。
5. 理论与迁移：摘要能支持到什么程度；有明确理论线索、仅动机推导、或信息不足。信息不足时输出 uncertainty，不假装已读全文；用户的全文总结阶段再验证。

这套维度是建议，不设未经用户确认的精确分数、阈值或每类配额。

## 需要主代理集中确认的两项兴趣边界

1. **通用、无 RL / DPO 的 reasoning segmentation**：低优先级保留（推荐，可捕获 LISA 后续有可迁移想法），或直接排除？LISA 本身是领域基准，不能拿它替用户决定这个边界。
2. **医学普通分割 / 医学 SAM**：必须有隐含请求 / 空间推理等任务要素，还是 DPO / RL / 拓扑结构或有理论的 loss 已足够相关？ARIADNE 说明“医学推理”不一定指语言 CoT，因此建议允许明确的医学优化 / 结构贡献作为独立路线，但不把所有普通医学 segmentation 泛化成正例。

论文身份在当前语境中均有高置信对应；PRS-Med 的版本题名差异已经查明，不需要用户再解决这个可查事实。只有用户确实意指另一篇同名 ARIADNE 时才需要补具体链接。
