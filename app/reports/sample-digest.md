# arXiv 每日简报 · 2026-10-02

## 完整档

### MediSee: Reasoning-based Pixel-level Perception in Medical Images
https://arxiv.org/abs/2504.11008v2

**背景：** 专科医学分割模型交互性不足，隐含口语查询使目标定位更加困难。
**贡献：** 论文提出 MedSD 医学推理分割与检测任务，以及同时输出掩码和边框的 MediSee 基线。
**方法：** MediSee 结合 LLaVA-Med、MedSAM 与候选 token 路由融合。训练同时优化文本生成、掩码和边框，并通过相似度目标进一步微调。
**实验：** MLMR-SD 结果表的首组 Dice 指标中，MediSee 进一步微调后为 59.4，未进一步微调版本为 56.7。
**结论：** 作者认为该任务和基线可推动隐含查询下的医学图像分割研究；现有验证范围是 MLMR-SD 与 SA-Med2D-20M 基准，真实临床部署表现未报告。

### PRS-Med: Position Reasoning Segmentation in Medical Imaging
https://arxiv.org/abs/2505.11872v4

**背景：** 医学分割依赖显式提示，临床空间关系问题需要位置推理和掩码输出。
**贡献：** 论文提出 PosMed 数据集及 PRS-Med 框架，以区域式位置推理支持医学图像分割。
**方法：** 框架把视觉骨干、经 LoRA 调整的医学多模态模型与提示掩码解码器结合，生成位置解释和分割掩码；定位采用类别化空间区域而非像素坐标回归。
**实验：** 论文报告肺 CT 组相对次优方法的 mDice 与 mIoU 提升分别为 31.2% 和 41.5%。
**结论：** 作者把病灶大小与结构间距离等更丰富的空间推理列为后续工作。

### ARIADNE: A Perception-Reasoning Synergy Framework for Trustworthy Coronary Angiography Analysis
https://arxiv.org/abs/2603.19169v1

**背景：** 单纯像素级分割目标难约束冠脉树拓扑连续性，碎裂血管会干扰狭窄定位。
**贡献：** ARIADNE 将拓扑一致的血管重建与上下文感知的狭窄定位联成感知和推理两个阶段。
**方法：** 感知阶段以 DPO 偏好对齐完整血管结构；诊断阶段基于血管中心线构造决策过程，并用 PPO 优化带拒绝选项的策略。
**实验：** 论文在狭窄检测中报告 TPR 0.867、FPPI 0.85，优于所列比较方法。
**结论：** 论文认为结构有效性应进入训练目标，并指出二维造影的投影歧义仍需多视角分析。

## 轻量档

- [LISA: Reasoning Segmentation via Large Language Model](https://arxiv.org/abs/2308.00692v3)

## 运行备注

- 脚本化离线运行：未调用真实模型或发送服务。
