"""Build deterministic synthetic fixtures (no network or model calls)."""
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from arxivdaily.models import Body, Decision, Evidence, Paper, Section, Summary


def build():
    fixture = {"fixture_kind": "synthetic", "papers": [], "decisions": {}, "bodies": {}, "summaries": {}}
    tasks = [("medical_reasoning", "full", "select"), ("general_reasoning", "light", "select"), ("irrelevant", "light", "reject"), ("transferable_objective", "full", "uncertain")]
    for index, (route, tier, status) in enumerate(tasks, 1):
        abstract = {1: "Medical image reasoning segmentation uses implicit queries and supervised mask learning.", 2: "Reasoning segmentation uses implicit instructions with a large language model and supervised learning.", 3: "Medical segmentation with attention improves Dice but offers no objective contribution.", 4: "We propose a segmentation loss for medical masks; theory and transfer require further study."}[index]
        paper = Paper(f"2501.9000{index}v1", f"Synthetic fixture {index}: {route}", abstract, ["cs.CV"], "2026-10-01T02:00:00+00:00", "2026-10-01T02:00:00+00:00")
        fixture["papers"].append(paper.to_dict())
        decision = Decision(status, route, tier, "脚本化测试预期，不是模型实测判断。", [abstract], ["需要正文确认理论与迁移"] if status == "uncertain" else [], False, False, False, False, 90-index)
        fixture["decisions"][paper.base_id] = decision.to_dict()
        if index not in {1, 4}:
            continue
        texts = {"Introduction": "Medical implicit queries require pixel masks rather than text answers.", "Contribution": "We introduce a supervised segmentation interface for implicit medical queries.", "Method": "The image encoder and language decoder are trained with supervised mask and text losses.", "Experiments": "On the synthetic benchmark the supervised system achieves Dice 82.5 compared with baseline Dice 78.0.", "Conclusion": "The method supports implicit medical requests but generalization to unseen modalities is not established."}
        sections = [Section(f"section:{k}", v) for k, v in texts.items()]
        body = Body(paper.version_id, f"https://arxiv.org/html/{paper.version_id}", "html", sections, quality={"passed": True, "fixture_kind": "synthetic", "reading_order_ok": True, "read_locators": [s.locator for s in sections], "reasons": []})
        fixture["bodies"][paper.base_id] = body.to_dict()
        if index == 1:
            summary = Summary("医学隐含请求需要输出像素掩码。", "该合成样例提出监督式医学推理分割接口。", "图像编码器与语言解码器用掩码和文本监督损失训练。", "合成基准 Dice 为 82.5，比较基线为 78.0。", "可处理隐含医学请求；对未见模态的泛化尚未确立。", [Evidence(field, f"section:{loc}", texts[loc], body.source_url) for field, loc in [("background","Introduction"),("contribution","Contribution"),("method","Method"),("experiments","Experiments"),("conclusion","Conclusion")]])
            fixture["summaries"][paper.base_id] = summary.to_dict()
    output = Path(__file__).resolve().parents[1] / "fixtures" / "demo.json"
    output.write_text(json.dumps(fixture, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    build()
