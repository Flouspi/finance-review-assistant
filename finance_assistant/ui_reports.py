"""Structured presentation data without manufactured risk scores."""
import json
import re

REPORT_INSTRUCTION = """本次回答需用于审查工作台，请只返回一个JSON对象，不要使用代码围栏。
保留前述审查要求，但将输出格式统一为：
{"summary":"简要结论，明确资料不足等限制","overall_risk":"高/中/低/待核实",
"answer_markdown":"完整的审查回答，保留风险等级、问题、依据、修改建议",
"findings":[{"title":"问题名称","level":"高/中/低/待核实","clause":"原文条款号，没有则留空",
"quote":"从用户材料逐字摘录的原文，没有则留空","reason":"为什么需要关注",
"recommendation":"具体修改建议","revision":"建议替换文本，没有足够原文则留空",
"evidence_ids":[1]}]}
evidence_ids只能引用本次提供的[证据N]编号，没有适用依据就留空。
findings只列实际识别到的问题，不凑数量。不能凭信息不足认定合规。
不要生成综合风险分数，不要编造页码、条款号或原文。一般知识咨询可以返回空findings并在完整回答中作答。
"""


def parse_report(text):
    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = re.sub(r"^```(?:json)?\s*|\s*```$", "", candidate, flags=re.I)
    try:
        data = json.loads(candidate)
    except (ValueError, TypeError):
        return None
    if not isinstance(data, dict) or not isinstance(data.get("findings"), list):
        return None
    if not isinstance(data.get("answer_markdown"), str) or not data["answer_markdown"].strip():
        return None
    levels = {"高", "中", "低", "待核实"}
    findings = []
    for item in data["findings"]:
        if not isinstance(item, dict) or not isinstance(item.get("title"), str) or not item["title"].strip():
            return None
        clean = {key: item.get(key, "") if isinstance(item.get(key, ""), str) else ""
                 for key in ("title", "clause", "quote", "reason", "recommendation", "revision")}
        level = item.get("level")
        clean["level"] = level if isinstance(level, str) and level in levels else "待核实"
        clean["evidence_ids"] = [x for x in item.get("evidence_ids", []) if type(x) is int and x > 0] if isinstance(item.get("evidence_ids", []), list) else []
        findings.append(clean)
    overall = data.get("overall_risk")
    return {"summary": data.get("summary", "") if isinstance(data.get("summary", ""), str) else "",
            "overall_risk": overall if isinstance(overall, str) and overall in levels else "待核实",
            "answer_markdown": data["answer_markdown"], "findings": findings}


class ReportModel:
    """Use the existing second LLM call for both prose and risk cards."""
    def __init__(self, model):
        self.model = model
        self.calls = 0
        self.report = None

    def complete(self, messages, config):
        self.calls += 1
        if self.calls == 1:
            return self.model.complete(messages, config)
        response = self.model.complete([*messages, {"role": "system", "content": REPORT_INSTRUCTION}], config)
        self.report = parse_report(response)
        return self.report["answer_markdown"] if self.report else response


def bind_report(report, citations, source_text):
    if not report:
        return None
    # Copy via JSON so per-case validation never mutates the model adapter.
    result = json.loads(json.dumps(report, ensure_ascii=False))
    compact_source = re.sub(r"\s+", "", source_text)
    for item in result["findings"]:
        original_ids = item["evidence_ids"]
        item["evidence_ids"] = list(dict.fromkeys(x for x in original_ids if x <= len(citations)))
        item["unavailable_evidence"] = any(x > len(citations) for x in original_ids)
        quote = item["quote"]
        item["quote_located"] = bool(quote.strip() and re.sub(r"\s+", "", quote) in compact_source)
    return result


def risk_counts(report):
    if report is None:
        return None
    return {level: sum(f["level"] == level for f in report["findings"]) for level in ("高", "中", "低", "待核实")}


def revision_markdown(record):
    report = record.get("report")
    if not report or not report.get("findings"):
        return ""
    parts = ["# 修改建议清单", "以下为模型建议，需结合原文与适用依据核对后采用。"]
    for index, item in enumerate(report["findings"], 1):
        parts.extend([f"## {index}. {item['clause']} {item['title']}",
                      f"原文：{item['quote'] or '未提供'}", f"建议：{item['recommendation'] or '待补充'}",
                      f"建议替换文本：{item['revision'] or '未生成，需补充原文或人工起草'}"])
    return "\n\n".join(parts)
