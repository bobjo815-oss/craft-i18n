#!/usr/bin/env python3
"""Validate Korean reference TSVs; optionally export a readable Markdown glossary.

This checks reference data, not runtime translation catalogs. Without --export-to it is read-only.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "docs" / "terminology"
FIELDS = ["english", "korean", "context", "novice_help", "references", "decision"]
SCOPES = dict(common="공통", pdfcraft="PdfCraft", designcraft="DesignCraft",
              photocraft="PhotoCraft", vectorcraft="VectorCraft", filmcraft="FilmCraft")


def load():
    sources = json.loads((DATA / "ko-sources.json").read_text(encoding="utf-8"))
    by_id = {source["id"]: source for source in sources}
    errors = []
    if len(by_id) != len(sources):
        errors.append("duplicate source IDs")
    for source in sources:
        if not source["url"].startswith("https://helpx.adobe.com/kr/"):
            errors.append(f"{source['id']}: unexpected reference URL")
    catalogs = {}
    for scope in SCOPES:
        path = DATA / f"ko-{scope}.tsv"
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream, delimiter="\t")
            if reader.fieldnames != FIELDS:
                errors.append(f"{path.name}: incorrect header")
                continue
            rows = list(reader)
        seen = set()
        for line, row in enumerate(rows, 2):
            label = f"{path.name}:{line}"
            if None in row or any(not isinstance(row.get(key), str) or not row[key].strip() for key in FIELDS):
                errors.append(f"{label}: empty field or wrong column count")
                continue
            pair = row["english"], row["context"]
            if pair in seen:
                errors.append(f"{label}: duplicate English/context {pair}")
            seen.add(pair)
            for ref in row["references"].split(","):
                if ref != "editorial" and ref not in by_id:
                    errors.append(f"{label}: unknown reference {ref}")
            for key, value in row.items():
                if value != value.strip() or "\x00" in value:
                    errors.append(f"{label}: invalid whitespace/control character in {key}")
        catalogs[scope] = rows
    return catalogs, by_id, errors


def render(catalogs, sources):
    total = sum(len(rows) for rows in catalogs.values())
    lines = ["# Craft 앱 한국어 용어집", "", f"2026-10-24 초안 · 문맥별 {total}개 항목 · 공통 및 5개 앱 전용 용어", "",
             "메뉴에 쓸 이름과 초보자에게 설명할 문장을 함께 정리했습니다. 용어 연구 자료이며 앱 전체의 번역 완료나 기능 지원을 뜻하지 않습니다. 설명은 새로 집필했으며 AI 자체 검토 후 별도 사람 검수는 아직 없습니다.", "",
             "같은 영어라도 문맥에 따라 뜻이 다릅니다. 표의 Columns는 열, 본문의 Columns는 단입니다. 인터페이스 언어와 OCR 문서 언어, 마스크와 삭제, 레이아웃 프레임과 영상 프레임을 구별합니다.", "",
             "[집필·툴팁 적용 안내](Korean-Localization.md) · [TSV 원본](terminology/ko-common.tsv)", ""]
    for scope, title in SCOPES.items():
        rows = catalogs[scope]
        lines.extend([f"## {title} ({len(rows)}개)", "",
                      "| 영어 | 우선 한국어 | 문맥 | 초보자 설명 | 선택 이유 / 동의어 | 참고 |",
                      "|---|---|---|---|---|---|"])
        for row in rows:
            refs = ", ".join(f"[{ref}]({sources[ref]['url']})" if ref in sources else "자체 선택"
                             for ref in row["references"].split(","))
            values = [row["english"], row["korean"], row["context"], row["novice_help"], row["decision"], refs]
            lines.append("| " + " | ".join(value.replace("|", "\\|").replace("\n", "<br>") for value in values) + " |")
        lines.append("")
    lines.extend(["## 읽고 확인한 자료", "", "모두 Adobe가 직접 게시한 자료이며 2026-10-24에 확인했습니다. 용어를 참고했으며 Craft의 구현 동작은 코드로 따로 확인해야 합니다.", ""])
    lines.extend(f"- {ref}: [{source['title']}]({source['url']})" for ref, source in sources.items())
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export-to", type=Path)
    args = parser.parse_args()
    try:
        catalogs, sources, errors = load()
        if errors:
            for error in errors:
                print(f"ERROR: {error}")
            return 1
        counts = {scope: len(rows) for scope, rows in catalogs.items()}
        print(json.dumps({"terms": counts, "total": sum(counts.values()), "sources": len(sources), "errors": 0}, ensure_ascii=False))
        if args.export_to:
            args.export_to.parent.mkdir(parents=True, exist_ok=True)
            args.export_to.write_text(render(catalogs, sources), encoding="utf-8")
            print(f"Exported: {args.export_to}")
    except (OSError, ValueError, KeyError) as error:
        print(f"ERROR: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
