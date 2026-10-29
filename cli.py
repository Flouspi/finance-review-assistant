import argparse
import json
from pathlib import Path
import sys

from finance_assistant.config import Settings
from finance_assistant.documents import InputError
from finance_assistant.providers import ChatModel, ConfigurationError, ProviderError, knowledge_provider
from finance_assistant.workflow import Workflow, WorkflowError, load_dsl, report_markdown


def main():
    parser = argparse.ArgumentParser(description="金融合规 LangGraph 助手")
    parser.add_argument("--query", default="")
    parser.add_argument("--file", action="append", default=[])
    parser.add_argument("--mode", choices=["corrected", "faithful"], default="corrected")
    parser.add_argument("--check", action="store_true", help="检查配置和图结构，不调用付费接口")
    parser.add_argument("--graph", action="store_true", help="输出 Mermaid 图")
    parser.add_argument("--output", type=Path, help="保存 Markdown 报告；拒绝覆盖已有文件")
    args = parser.parse_args()
    try:
        settings = Settings.load()
        workflow = Workflow(load_dsl(), ChatModel(settings), knowledge_provider(settings), args.mode, settings.max_input_chars)
        if args.graph:
            print(workflow.mermaid())
            return 0
        if args.check:
            print(json.dumps({"mode": args.mode, "graph_compiled": True, "reachable_nodes": len(workflow.reachable),
                              "unreachable_nodes": workflow.unreachable, "model": settings.model or "deepseek-flash",
                              "model_key_configured": bool(settings.api_key), "knowledge_backend": settings.knowledge_backend,
                              "local_knowledge_files": sum(p.is_file() and p.suffix.lower() in {".txt", ".md", ".csv", ".pdf", ".docx"} for p in settings.knowledge_dir.rglob("*")),
                              "dify_key_configured": bool(settings.dify_api_key), "dify_dataset_configured": bool(settings.dify_dataset_id)}, ensure_ascii=False, indent=2))
            return 0
        if args.output and args.output.exists():
            raise InputError("报告目标已存在，请使用新文件名。")
        files = [{"name": Path(p).name, "data": Path(p).read_bytes()} for p in args.file]
        state = workflow.invoke(args.query, files)
        report = report_markdown(state, args.mode)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("x", encoding="utf-8") as handle:
                handle.write(report)
        else:
            print(report)
        return 0
    except (InputError, ConfigurationError, ProviderError, WorkflowError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
