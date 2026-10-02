# arXiv 每日简报 · 2026-10-03

## 完整档

### MediSee: Reasoning-based Pixel-level Perception in Medical Images
https://arxiv.org/abs/2504.11008v2

**背景：** 医学图像分割虽已用于识别器官、病灶等 ROI，但既有专科模型和交互式医学图像分割（IMIS）多依赖精确框或标注文本，难以处理需要逻辑推理的隐含查询。
**贡献：** 本文提出医学推理分割与检测任务 MedSD，构建包含超过 200K 复杂隐式问答的 MLMR-SD 数据集，并提出基线模型 MediSee。
**方法：** MediSee 以 MedSAM 和 LLaVA-Med 为骨干，通过 Adaptive Democratic Candidate Fusion 自适应融合候选 token 的隐藏表示，分别生成分割掩码与检测框。训练使用文本、掩码和边界框监督，并在额外微调阶段加入相似性损失。
**实验：** 在 MLMR-SD 验证集整体评估中，额外微调的 MediSee 的 Dice 为 59.4，而 LISA-7B 为 31.6（表 1）；这些结果来自论文基准，不能视为独立临床验证。
**结论：** 作者总结称，本文提出 MedSD 任务、构建数据集并提供基线模型 MediSee，以推理实现医学图像像素级感知，并希望推动医学分割模型进入日常应用。

## 轻量档

- [LISA: Reasoning Segmentation via Large Language Model](https://arxiv.org/abs/2308.00692v3)

## 运行备注

- 真实模型小规模联调；根代理按同版 PDF 核对并精简实验段，原模型输出保留在联调 JSON。未发送微信，未改变生产状态。
