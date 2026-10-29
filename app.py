from dataclasses import replace

import streamlit as st

from finance_assistant.config import Settings
from finance_assistant.documents import InputError
from finance_assistant.providers import ChatModel, ConfigurationError, ProviderError, knowledge_provider, knowledge_files
from finance_assistant.workflow import Workflow, WorkflowError, load_dsl, report_markdown

st.set_page_config(page_title="金融合规审查助手", page_icon="◈", layout="wide")
st.markdown("""<style>
.stApp {background:#f5f7fb;}
.block-container {max-width:1160px;padding-top:2.4rem;}
[data-testid="stSidebar"] {background:#eef2f7;}
h1,h2,h3 {color:#132c48;}
.hero {border-left:5px solid #137d8d;padding:10px 0 10px 20px;margin-bottom:24px;}
.eyebrow {color:#137d8d;font-size:12px;letter-spacing:2px;font-weight:700;}
.hero p {color:#627186;font-size:15px;margin-bottom:0;}
[data-testid="stChatMessage"] {background:white;border:1px solid #e4eaf2;border-radius:12px;}
.stButton>button {border-radius:8px;}
</style>""", unsafe_allow_html=True)

dsl = load_dsl()
try:
    cloud_config = dict(st.secrets)
except FileNotFoundError:
    cloud_config = {}
settings = Settings.load(cloud_config)

# A hosted reviewer must never be able to redirect the server's API key to
# an arbitrary endpoint via the editable connection controls.
entered_key = ""
base_url = settings.base_url
model_name = settings.model or "deepseek-flash"
mode = "corrected"
backend = settings.knowledge_backend

with st.sidebar:
    st.markdown("### ◈ 审查工作台")
    st.caption("LangGraph · 金融合规智能助手")
    if settings.evaluation_mode:
        st.caption("选择审查任务，输入内容或上传材料，即可开始测试。")
    else:
        mode_label = st.selectbox("工作流版本", ["修正版（参赛推荐）", "原版对照"])
        mode = "corrected" if mode_label.startswith("修正版") else "faithful"
        st.caption("法规资料来源：项目自有知识库")
        st.caption("已读取本地模型密钥" if settings.api_key else "尚未配置模型密钥")
        with st.expander("模型连接", expanded=not bool(settings.api_key)):
            entered_key = st.text_input("模型 API key（仅本次会话）", type="password", help="留空时读取项目 .env 或环境变量；不会写入报告。")
            base_url = st.text_input("API Base URL", value=settings.base_url)
            model_name = st.text_input("模型名称", value=settings.model or "deepseek-flash")
        st.caption("将法规 TXT、MD、PDF、DOCX、CSV 放入项目 knowledge 文件夹。")
    files = st.file_uploader("上传待审查材料", type=["txt", "md", "csv", "pdf", "docx"], accept_multiple_files=True,
                             help="最多 3 份、每份 15 MB；扫描版 PDF 需先 OCR。材料只用于本轮，不自动加入法规库。")
    st.caption("每次提交独立审查；历史记录仅用于本页展示。")
    if st.button("清空当前对话", width="stretch"):
        st.session_state.reviews = []
        st.rerun()

st.markdown('<div class="hero"><div class="eyebrow">FINANCIAL COMPLIANCE / REVIEW DESK</div><h1>金融合规审查助手</h1><p>识别审查任务 · 检索监管依据 · 定位风险与修改建议</p></div>', unsafe_allow_html=True)
reviewer_unavailable = settings.evaluation_mode and (
    not settings.api_key or
    (backend == "local" and not knowledge_files(settings.knowledge_dir))
)
if reviewer_unavailable:
    st.error("审查服务尚未完成配置，请联系参赛团队接通模型和法规资料后再测试。")
if mode == "faithful":
    st.warning("原版对照保留 DSL 的接线问题：合同正文来源错误，一般咨询引用未执行节点可能报错。用于迁移核对。")
elif backend == "local" and not knowledge_files(settings.knowledge_dir):
    st.info("自有知识库尚未导入资料。请将法规、制度或业务规则放入项目 knowledge 文件夹。")

if "reviews" not in st.session_state:
    st.session_state.reviews = []

def display_result(record, index):
    with st.chat_message("user"):
        st.write(record["query"] or "请审查上传的材料")
        if record["filenames"]:
            st.caption("附件：" + "、".join(record["filenames"]))
    state = record["state"]
    with st.chat_message("assistant"):
        st.caption(f"{state.get('category', '')} · {'修正版' if record['mode'] == 'corrected' else '原版对照'}")
        for warning in state.get("warnings", []):
            st.warning(warning)
        st.markdown(state.get("answer", ""))
        with st.expander(f"参考资料 · {len(state.get('citations', []))} 条"):
            st.caption("以下为检索命中片段，不代表每条均适用于本次业务；请结合回答中的引用核实。")
            for i, citation in enumerate(state.get("citations", []), 1):
                st.markdown(f"**证据{i} · {citation['source']}**")
                st.caption(citation.get("location", ""))
                if citation.get("evidence_type"):
                    st.caption("资料层级：" + citation["evidence_type"])
                if citation.get("verification_status"):
                    st.caption("原表核验状态（本次未独立复核）：" + citation["verification_status"])
                if citation.get("source_url"):
                    st.write("原始来源：", citation["source_url"])
                st.text(citation["content"])
        with st.expander("查看执行过程"):
            st.dataframe(state.get("trace", []), hide_index=True, width="stretch")
        st.download_button("下载审查报告", report_markdown(state, record["mode"]), file_name=f"合规审查报告-{index + 1}.md", mime="text/markdown", key=f"report_{index}")

for index, record in enumerate(st.session_state.reviews):
    display_result(record, index)

if not st.session_state.reviews:
    columns = st.columns(4)
    labels = ["合同审查", "产品审查", "投资范围", "营销宣传"]
    questions = dsl["workflow"]["features"]["suggested_questions"]
    for col, label, question in zip(columns, labels, questions):
        if col.button(label, width="stretch"):
            st.session_state.query_draft = question
    st.caption("选择审查类型可填入示例问题；请补充具体条款、产品信息或上传文件。")

with st.form("review_form", clear_on_submit=False):
    query = st.text_area("审查内容", key="query_draft", height=140, placeholder="例如：请检查这段理财宣传文案是否合规，并指出需要修改的表达……")
    submitted = st.form_submit_button("开始审查", type="primary", disabled=reviewer_unavailable)

if submitted:
    runtime = replace(settings, api_key=entered_key or settings.api_key, base_url=base_url.rstrip("/"), model=model_name,
                      knowledge_backend=backend)
    if not runtime.api_key:
        st.error("请先在左侧填写模型 API key，或配置项目 .env 文件。")
    else:
        try:
            workflow = Workflow(dsl, ChatModel(runtime), knowledge_provider(runtime), mode, runtime.max_input_chars)
            uploads = [{"name": f.name, "data": f.getvalue()} for f in files]
            with st.status("正在审查材料…", expanded=True) as status:
                state = None
                last_count = 0
                for state in workflow.stream(query, uploads):
                    if len(state["trace"]) > last_count:
                        item = state["trace"][-1]
                        st.write(f"✓ {item['title']} · {item['seconds']} 秒")
                        last_count = len(state["trace"])
                status.update(label="审查完成", state="complete", expanded=False)
            if state and state.get("answer"):
                # Do not retain raw file bytes, prompt variables or credentials in chat history.
                public_state = {k: state[k] for k in ("answer", "category", "citations", "warnings", "trace")}
                st.session_state.reviews.append({"query": query, "filenames": [f.name for f in files], "state": public_state, "mode": mode})
                st.rerun()
        except (InputError, ConfigurationError, ProviderError, WorkflowError) as exc:
            st.error(str(exc))
        except Exception:
            st.error("运行出现未预期错误。请使用命令行自检并检查配置；密钥和原始服务响应不会在页面显示。")

