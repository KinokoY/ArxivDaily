# 第三方来源与许可

[`X-PG13/paper-digest`](https://github.com/X-PG13/paper-digest) 的固定提交
`8906f9a12309956913eab29dade75c01cb7d0771` 提供了本项目复用的 arXiv
元数据类、基础 ID 与交叉分类合并逻辑。选入的五个 Python 文件和原 MIT
[`LICENSE`](../arxivdaily/_vendor/paper_digest/LICENSE) 均与该提交原始 Git blob
逐字节一致，不经过本地 checkout 换行转换；
哈希见 [`ORIGIN.json`](../arxivdaily/_vendor/paper_digest/ORIGIN.json)，
实际调用边界见 [`UPSTREAM.md`](../UPSTREAM.md)。本项目新增代码另有
[`LICENSE`](../LICENSE)。上游 GitHub workflows、摘要分析和多渠道发送器未导入。

本地已安装依赖的 METADATA 与原许可文件已检查。正文方案采用 pypdf 与 PDFium，没有加入 PyMuPDF 等需要额外评估的 AGPL 依赖。

| 主要依赖 | 用途 | 已安装包的许可声明 |
| --- | --- | --- |
| arxiv 4.0.1 | 单客户端元数据 API、分页 | MIT |
| httpx 0.28.1 | 模型、正文、通知 HTTP | BSD-3-Clause |
| beautifulsoup4 4.15.0 | 有结构 HTML | MIT |
| pypdf 6.19.0 | PDF 文字、物理页码 | BSD-3-Clause |
| pypdfium2 5.13.0 | PDF 列顺序核查、必要页渲染 | BSD-3-Clause、Apache-2.0 与捆绑依赖许可 |
| Pillow 11.1.0 | 渲染页 PNG 编码 | MIT-CMU |
| pytest 9.1.1 | 离线和模拟测试 | MIT |
| PyYAML 6.0.3 | 工作流静态解析测试 | MIT |

pypdfium2 wheel 带有原 `licenses/`，包括 PDFium、freetype、libjpeg 等捆绑组件许可和数据的 CC-BY-4.0 声明；不能把整份 wheel 描述为只有 BSD 许可。应用没有复制或重新打包其二进制，只以 PyPI 依赖安装；若以后离线分发 wheel/二进制，需要一起保留这些完整许可与署名。

`requirements.lock` 锁定 Python 包版本，安装按平台选择原 wheel。Windows/ml 已完成本地运行验证；Ubuntu runner 安装与远程工作流实际执行仍在部署阶段验证。论文 HTML/PDF 的原始材料只用于本地阅读校准，默认不提交到公开状态分支。公开归档保存原创中文短报、必要短证据和具体版本出处。
