from dataclasses import replace
from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

import streamlit as st

from . import providers
from .config import Settings
from .documents import InputError
from .ui_reports import ReportModel, bind_report, risk_counts, revision_markdown
from .ui_styles import CSS
from .workflow import Workflow, WorkflowError, load_dsl, report_markdown, EXTRACTOR


def e(value):
    return escape(str(value or ""), quote=True).replace("\n", "<br>")


def level_class(level):
    return {"高": "high", "中": "medium", "低": "low"}.get(level, "unknown")


def badge(level):
    return f'<span class="badge {level_class(level)}">{e(level)}风险</span>' if level in {"高", "中", "低"} else '<span class="badge unknown">待核实</span>'


def citation_view(citation, index):
    st.markdown(f"**证据 {index} · {citation.get('title') or citation['source']}**")
    st.caption(f"{citation['source']} · {citation.get('location', '')}")
    if citation.get("evidence_type"):
        st.caption("资料层级：" + citation["evidence_type"])
    if citation.get("verification_status"):
        st.caption("原表核验状态（本次未独立复核）：" + citation["verification_status"])
    st.text(citation["content"])
    if citation.get("source_url"):
        st.write("原始来源：", citation["source_url"])


def finding_view(item, index, record):
    with st.container(key=f"finding_{level_class(item['level'])}_{index}"):
        st.markdown(f'<div class="finding-head">{badge(item["level"])}<div class="finding-title">{e(item["clause"])}　{e(item["title"])}</div></div><div class="finding-reason">{e(item["reason"])}</div>', unsafe_allow_html=True)
        tabs = st.tabs(["法规依据", "相似案例", "原文定位"])
        citations = record["state"].get("citations", [])
        selected = [(n, citations[n - 1]) for n in item["evidence_ids"]]
        with tabs[0]:
            evidence = [(n, c) for n, c in selected if "案例" not in c.get("evidence_type", "")]
            if evidence:
                for n, c in evidence:
                    with st.expander(f"证据 {n} · {c.get('title') or c['source']}"):
                        citation_view(c, n)
            else:
                st.caption("本条未关联可展示的法规依据，请结合完整参考资料核实。")
        with tabs[1]:
            cases = [(n, c) for n, c in selected if "案例" in c.get("evidence_type", "")]
            if cases:
                for n, c in cases:
                    with st.expander(f"证据 {n} · {c.get('title') or c['source']}"):
                        citation_view(c, n)
            else:
                st.caption("本次引用中没有关联案例。")
        with tabs[2]:
            if item["quote"]:
                st.markdown(f'<div class="quote">{e(item["quote"])}</div>', unsafe_allow_html=True)
                st.caption("已在本次材料中匹配到摘录。" if item.get("quote_located") else "暂未在本次材料中精确匹配，请人工核对摘录与条款位置。")
            else:
                st.caption("模型未提供可定位的原文摘录。")
        if item.get("unavailable_evidence"):
            st.caption("模型引用的部分证据编号无效，已从本卡片的依据列表中排除。")
        st.markdown(f'<div class="recommendation">建议：{e(item["recommendation"] or "补充材料并人工核实。")}</div>', unsafe_allow_html=True)
        if item["revision"]:
            with st.expander("查看建议替换文本"):
                st.write(item["revision"])


def conversation_view(record):
    turns = record.get("turns") or [{"query": record["query"], "answer": record["state"]["answer"]}]
    for turn in turns[:-1]:
        with st.expander("此前问答 · " + (turn["query"] or "审查上传材料")[:36]):
            st.write(turn["query"])
            st.markdown(turn["answer"])
    question = turns[-1]["query"] or "请审查上传的材料。"
    st.markdown(f'<div class="user-row"><div class="user-bubble">{e(question)}</div><div class="avatar user">我</div></div>', unsafe_allow_html=True)
    report = record.get("report")
    counts = risk_counts(report)
    summary = report.get("summary") if report else "审查回答已生成，可展开查看完整内容。"
    if counts is not None:
        intro = f"高风险 {counts['高']} 项 · 中风险 {counts['中']} 项 · 低风险 {counts['低']} 项"
        if counts["待核实"]:
            intro += f" · 待核实 {counts['待核实']} 项"
    else:
        intro = "已完成审查。"
    st.markdown(f'<div class="assistant-row"><div class="avatar ai">审</div><div><div class="assistant-title">{e(intro)}</div><div class="assistant-sub">{e(summary)}</div></div></div>', unsafe_allow_html=True)
    for warning in record["state"].get("warnings", []):
        st.warning(warning)
    if report and report["findings"]:
        ranked = sorted(report["findings"], key=lambda x: {"高": 0, "中": 1, "待核实": 2, "低": 3}[x["level"]])
        st.caption("优先处理")
        finding_view(ranked[0], 0, record)
        if len(ranked) > 1:
            with st.expander(f"查看其余 {len(ranked) - 1} 项风险"):
                for i, item in enumerate(ranked[1:], 1):
                    finding_view(item, i, record)
    elif report is None:
        st.info("本次回答未能整理成风险卡片。完整内容已保留，风险数量暂不统计。")
        st.markdown(record["state"]["answer"])
    else:
        st.markdown(record["state"]["answer"])
    if report and report["findings"]:
        with st.expander("查看完整审查回答"):
            st.markdown(record["state"]["answer"])


def dashboard_view(record):
    report = record.get("report")
    counts = risk_counts(report)
    if counts is None:
        st.info("本次回答暂时无法统计风险条目，请查看完整结果。")
        st.markdown(record["state"]["answer"])
        return
    findings = sorted(report["findings"], key=lambda x: {"高": 0, "中": 1, "待核实": 2, "低": 3}[x["level"]])
    document, statistics = st.columns([1.03, 1.25], gap="large")
    with document:
        cards = []
        for item in findings:
            excerpt = item["quote"] or "未提供可定位原文；请补充原文后核实。"
            match = "原文已匹配" if item.get("quote_located") else "原文待核对"
            cards.append(f'<div class="paper-excerpt {level_class(item["level"])}"><strong>{e(item["clause"])} {e(item["title"])}</strong><p>{e(excerpt)}</p><p>{e(match)} · {e(item["level"])}风险</p></div>')
        if not cards:
            cards.append('<div class="empty-state">本次没有结构化风险条目。<br>请结合完整回答判断资料是否充分。</div>')
        name = "、".join(record.get("filenames", [])) or "输入内容"
        st.markdown(f'<div class="paper"><div class="paper-head">{e(name)}<span>条款摘录</span></div><div class="paper-body">{"".join(cards)}<div class="paper-foot">附件 {len(record.get("filenames", []))} 份 · 参考片段 {len(record["state"].get("citations", []))} 条</div></div></div>', unsafe_allow_html=True)
    with statistics:
        overall, distribution = st.columns([.85, 1.2])
        with overall:
            color = {"高": "#af443e", "中": "#946e35", "低": "#687787"}.get(report["overall_risk"], "#747d89")
            st.markdown(f'<div class="metric-card"><div class="section-label">综合风险等级</div><div class="metric-value" style="color:{color}">{e(report["overall_risk"])}</div><div class="metric-note">共 {sum(counts.values())} 个风险条目<br>待人工复核</div></div>', unsafe_allow_html=True)
        with distribution:
            total = sum(counts.values())
            bars = ""
            for level in ["高", "中", "低", "待核实"]:
                percentage = counts[level] / total * 100 if total else 0
                bars += f'<div class="distribution-row"><span class="distribution-label">{e(level)}</span><div class="bar-track"><div class="bar {level_class(level)}" style="width:{percentage:.2f}%"></div></div><span class="distribution-count">{counts[level]}项</span></div>'
            st.markdown(f'<div class="metric-card"><div class="section-label">风险分布</div>{bars}</div>', unsafe_allow_html=True)
        rows = "".join(f'<div class="top-row">{badge(item["level"])}<div class="top-text">{e(item["title"])}<div class="top-advice">{e(item["recommendation"] or "补充材料后核实")}</div></div></div>' for item in findings)
        st.markdown(f'<div class="top-findings"><div class="section-label">主要问题与建议</div>{rows or "本次未生成风险条目，请阅读完整回答。"}</div>', unsafe_allow_html=True)


def source_view(record):
    original, references = st.columns([1.15, 1])
    with original:
        st.markdown("#### 审查材料原文")
        text = record.get("source_text", "")
        if text:
            st.text_area("原文内容", value=text, height=480, disabled=True, key=f"source_{record.get('created', '')}")
        else:
            st.caption("此历史记录未保留可展示的材料原文。")
    with references:
        st.markdown("#### 检索参考资料")
        for i, citation in enumerate(record["state"].get("citations", []), 1):
            with st.expander(f"证据 {i} · {citation.get('title') or citation['source']}"):
                citation_view(citation, i)
        if not record["state"].get("citations"):
            st.caption("本次未检索到参考片段。")
    with st.expander("查看执行过程"):
        st.dataframe(record["state"].get("trace", []), hide_index=True, width="stretch")


def main():
    st.set_page_config(page_title="智合规 · 金融合规审查", page_icon="📄", layout="wide")
    st.markdown(CSS, unsafe_allow_html=True)
    dsl = load_dsl()
    try:
        cloud_config = dict(st.secrets)
    except FileNotFoundError:
        cloud_config = {}
    settings = Settings.load(cloud_config)
    ss = st.session_state
    if "reviews" not in ss:
        ss.reviews = []
    if "active_review" not in ss:
        ss.active_review = len(ss.reviews) - 1 if ss.reviews else None
    if "upload_nonce" not in ss:
        ss.upload_nonce = 0
    if ss.pop("clear_draft", False):
        ss.query_draft = ""

    entered_key = ""
    base_url, model_name, mode = settings.base_url, settings.model or "deepseek-flash", "corrected"
    with st.sidebar:
        st.markdown('<div class="brand">智合规</div><div class="brand-sub">金融合规审查</div>', unsafe_allow_html=True)
        if st.button("＋  新建审查", type="primary", width="stretch"):
            ss.active_review = None
            ss.query_draft = ""
            ss.upload_nonce += 1
            st.rerun()
        st.markdown('<div class="nav-label">审查记录</div>', unsafe_allow_html=True)
        if not ss.reviews:
            st.markdown('<div class="nav-empty">暂无记录</div>', unsafe_allow_html=True)
        for i in reversed(range(len(ss.reviews))):
            entry = ss.reviews[i]
            name = "、".join(entry.get("filenames", [])) or entry.get("query", "内容审查")
            prefix = "当前 · " if i == ss.active_review else ""
            if st.button(prefix + name[:28], key=f"history_{i}", width="stretch"):
                ss.active_review = i
                ss.query_draft = ""
                ss.upload_nonce += 1
                st.rerun()
        if not settings.evaluation_mode:
            with st.expander("连接设置"):
                entered_key = st.text_input("模型 API key（仅本次会话）", type="password")
                base_url = st.text_input("API Base URL", value=settings.base_url)
                model_name = st.text_input("模型名称", value=model_name)
                selected = st.selectbox("工作流版本", ["修正版", "原版对照"])
                mode = "corrected" if selected == "修正版" else "faithful"
                st.caption("法规资料来自项目自有知识库。")
        with st.container(key="sidebar_footer"):
            st.markdown(f'<div class="sidebar-stat">本次会话 · {len(ss.reviews)} 份审查</div><div class="sidebar-identity">自有法规知识库</div>', unsafe_allow_html=True)

    active = ss.active_review
    current = ss.reviews[active] if isinstance(active, int) and 0 <= active < len(ss.reviews) else None
    title = "、".join(current.get("filenames", [])) if current else "新建合规审查"
    title = title or current.get("query", "内容审查")[:40]
    if current:
        meta = f"{current['state'].get('category', '合规审查')} · {len(current['state'].get('citations', []))} 条参考片段"
        status = "待人工复核" if current.get("human_review") else "审查完成"
    else:
        meta, status = "", "等待材料"
    meta_html = f'<div class="case-meta">{e(meta)}</div>' if meta else ""
    st.markdown(f'<div class="case-header"><div><div class="case-title">{e(title)}</div>{meta_html}</div><div class="case-status">{e(status)}</div></div>', unsafe_allow_html=True)

    missing = []
    if not settings.api_key:
        missing.append("模型连接")
    if not providers.knowledge_files(settings.knowledge_dir):
        missing.append("法规知识库")
    reviewer_unavailable = settings.evaluation_mode and bool(missing)
    if reviewer_unavailable:
        st.error("审查服务尚未完成配置：" + "、".join(missing) + "尚未就绪。请联系参赛团队配置后再测试。")
    if mode == "faithful":
        st.warning("原版对照保留原工作流接线问题，仅用于迁移核对。")

    if current:
        chat, report, sources = st.tabs(["对话审查", "报告总览", "原文与依据"])
        with chat:
            conversation_view(current)
        with report:
            dashboard_view(current)
        with sources:
            source_view(current)
        actions = st.columns([1, 1, 1])
        with actions[0]:
            st.download_button("下载审查报告", report_markdown(current["state"], current.get("mode", "corrected")), file_name="合规审查报告.md", mime="text/markdown", width="stretch")
        with actions[1]:
            revisions = revision_markdown(current)
            st.download_button("下载修改建议清单", revisions, file_name="修改建议清单.md", mime="text/markdown", disabled=not revisions, width="stretch")
        with actions[2]:
            if st.button("已标记人工复核" if current.get("human_review") else "标记人工复核", width="stretch", disabled=bool(current.get("human_review"))):
                current["human_review"] = True
                st.rerun()
    else:
        st.markdown('<div class="welcome"><h1>提交审查材料</h1><p>上传文件或输入正文。选择下方类型可填入审查要求。</p></div>', unsafe_allow_html=True)
        questions = dsl["workflow"]["features"]["suggested_questions"]
        for col, label, question in zip(st.columns(4), ["合同审查", "产品合规", "投资范围", "营销宣传"], questions):
            if col.button(label, width="stretch"):
                ss.query_draft = question

    with st.expander("上传材料" + (" / 开始新的审查" if current else ""), expanded=not bool(current)):
        files = st.file_uploader("选择待审查材料", type=["txt", "md", "csv", "pdf", "docx"], accept_multiple_files=True,
                                 key=f"case_files_{ss.upload_nonce}", max_upload_size=15,
                                 help="最多3份，每份15MB。扫描PDF需先OCR；附件不会自动加入法规知识库。")
    with st.form("review_form", clear_on_submit=False):
        query = st.text_area("审查内容", key="query_draft", height=100, placeholder="继续追问，或输入需要审查的内容……" if current else "输入审查要求，或上传一份文件……")
        submitted = st.form_submit_button("开始审查", type="primary", disabled=reviewer_unavailable)
    if submitted:
        runtime = replace(settings, api_key=entered_key or settings.api_key, base_url=base_url.rstrip("/"), model=model_name)
        if not runtime.api_key:
            st.error("请先在连接设置或云端 Secrets 中配置模型 API key。")
            return
        try:
            uploads = [{"name": f.name, "data": f.getvalue()} for f in files]
            followup = current is not None and not uploads
            if followup and not query.strip():
                raise InputError("请输入追问内容，或上传新材料开始审查。")
            effective_query = query
            if followup:
                effective_query = f"【本轮问题】\n{query}\n\n【此前审查意见，仅供本轮核对】\n{current['state']['answer']}\n\n【原始材料】\n{current.get('source_text') or current['query']}"
            model = ReportModel(providers.ChatModel(runtime)) if mode == "corrected" else providers.ChatModel(runtime)
            workflow = Workflow(dsl, model, providers.knowledge_provider(runtime), mode, runtime.max_input_chars)
            with st.status("正在解析材料与检索依据…", expanded=True) as progress:
                state, count = None, 0
                for state in workflow.stream(effective_query, uploads):
                    if len(state["trace"]) > count:
                        item = state["trace"][-1]
                        st.write(f"✓ {item['title']} · {item['seconds']} 秒")
                        count = len(state["trace"])
                progress.update(label="审查完成", state="complete", expanded=False)
            if not state or not state.get("answer"):
                raise WorkflowError("未获得审查结果，请稍后重试。")
            source_text = current.get("source_text", "") if followup else (state["values"].get(f"{EXTRACTOR}.text") or query)
            structured = bind_report(getattr(model, "report", None), state.get("citations", []), source_text)
            public = {k: state[k] for k in ("answer", "category", "citations", "warnings", "trace")}
            turn = {"query": query, "answer": state["answer"]}
            if followup:
                previous_turns = current.get("turns") or [{"query": current["query"], "answer": current["state"]["answer"]}]
                current["state"] = public
                current["report"] = structured
                current["turns"] = [*previous_turns, turn]
                current["human_review"] = False
            else:
                ss.reviews.append({"query": query, "filenames": [f.name for f in files], "state": public, "mode": mode,
                                   "report": structured, "source_text": source_text, "turns": [turn],
                                   "created": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()})
                ss.active_review = len(ss.reviews) - 1
            ss.upload_nonce += 1
            ss.clear_draft = True
            st.rerun()
        except (InputError, providers.ConfigurationError, providers.ProviderError, WorkflowError) as exc:
            st.error(str(exc))
        except Exception:
            st.error("审查暂未完成，请检查模型连接或联系参赛团队。")
