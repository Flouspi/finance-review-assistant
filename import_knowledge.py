"""Import the team's XLSX knowledge collection into versioned JSONL records."""
import argparse
import json
from pathlib import Path
import sys

from finance_assistant.documents import InputError
from finance_assistant.workbook_import import convert_workbook, write_records


def main():
    parser = argparse.ArgumentParser(description="从知识库 XLSX 导入法规、案例和风险线索")
    parser.add_argument("xlsx", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        records, report = convert_workbook(args.xlsx)
        write_records(records, args.output)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    except (InputError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
