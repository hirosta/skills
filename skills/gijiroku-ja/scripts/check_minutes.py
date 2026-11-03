#!/usr/bin/env python3
"""定型Markdownの議事録を読み取り、機械的な確認候補だけを表示する。"""

import argparse
from collections import Counter
from datetime import date
from pathlib import Path
import re


SECTIONS = ("決定事項", "宿題", "持ち帰り", "持ち越し")
DATE = re.compile(
    r"(?<!\d)(?P<year>\d{4})(?:-(?P<m1>\d{1,2})-(?P<d1>\d{1,2})"
    r"|/(?P<m2>\d{1,2})/(?P<d2>\d{1,2})"
    r"|年(?P<m3>\d{1,2})月(?P<d3>\d{1,2})日)(?!\d)"
    r"(?:[ \t]*[（(](?P<weekday>[月火水木金土日])(?:曜日|曜)?[）)])?"
)
AMBIGUOUS = re.compile(
    r"再来週(?:中|末)?|来週(?:中|末)?|今週(?:中|末)?|近日中|早めに|なるべく早く"
    r"|できるだけ早く|随時|適宜|後日|未定|調整中|月末(?:まで)?|今月中|来月中"
    r"|明後日|明日|今日|本日|翌日|\d+営業日(?:以内|後)|\d+日(?:以内|後)"
)
PENDING = re.compile(r"検討します|持ち帰ります|社内で確認します|検討する|持ち帰る|社内で確認する")
FILLER = re.compile(r"えー+|あのー+|ええと|えっと")
EMPTY = {"", "-", "—", "なし", "未定", "不明", "未記入", "tbd", "n/a"}
HUMAN = (
    "人が確かめる点：原文との一致、決定の合意・否定・条件、担当の実在と責任範囲、"
    "期限の意図、人名の対応、社外秘・配布先、敬語の適切さ。"
    "検出0件でも内容の正しさや配布の可否は保証しない。"
)


class InputError(ValueError):
    """対応形式でない入力。"""


class Parser(argparse.ArgumentParser):
    def error(self, message):
        # argparse標準のエラーには入力パスが含まれ得るため再掲しない。
        self.print_usage()
        self.exit(2, "引数エラー：議事録ファイルを1つ指定する。--helpを参照。\n")

    def _print_message(self, message, file=None):
        if message:
            print(message, end="")


def cells(line):
    return [value.strip() for value in line.strip()[1:-1].split("|")]


def is_separator(row):
    return bool(row) and all(re.fullmatch(r":?-{3,}:?", value) for value in row)


def parse(lines):
    """見出しと表を読み、非対応の表や空の必須欄を黙って通さない。"""
    sections = {}
    current = None
    root_level = 0
    header = None
    tables = []
    in_fence = False
    for number, line in enumerate(lines, 1):
        if line.lstrip().startswith(("```", "~~~")):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        heading = re.match(r"^(#{1,6})\s+(.+?)\s*#*\s*$", line)
        if heading:
            level, title = len(heading[1]), heading[2]
            if title in (*SECTIONS, "参加者"):
                if title in sections:
                    raise InputError("必須見出し・参加者見出しは重複させない。")
                current, root_level = title, level
                sections[title] = []
            elif level <= root_level:
                current = None
            header = None
            continue
        if current is not None:
            if line.strip():
                sections[current].append((number, line))
            if line.strip().startswith("|"):
                if not line.strip().endswith("|"):
                    raise InputError("表の各行は | で始めて | で終える。")
                row = cells(line)
                if is_separator(row):
                    continue
                if header is None:
                    header = row
                    if len(header) != len(set(header)):
                        raise InputError("表の列名は重複させない。")
                else:
                    if len(row) != len(header):
                        raise InputError("表の列数をそろえる。セル内の | は使わない。")
                    tables.append((current, number, dict(zip(header, row))))
            else:
                header = None
    if in_fence:
        raise InputError("コードブロックが閉じていない。")
    for section in SECTIONS:
        if not sections.get(section):
            raise InputError("決定事項・宿題・持ち帰り・持ち越しの見出しと内容が必要。")
    for section in ("宿題", "持ち帰り"):
        rows = [row for title, _, row in tables if title == section]
        content = [line.strip() for _, line in sections[section]]
        if content == ["なし"]:
            continue
        if not rows or any("内容" not in row or not row["内容"] for row in rows):
            raise InputError("宿題・持ち帰りは内容列のある表、または「なし」とする。")
        if any(not line.startswith("|") for line in content):
            raise InputError("宿題・持ち帰りの表の外に作業を書かない。")
    return sections, tables


def check(text):
    lines = text.splitlines()
    sections, tables = parse(lines)
    findings = []

    def add(number, category, detail):
        findings.append((number, category, detail))

    for section, number, row in tables:
        if section not in ("宿題", "持ち帰り"):
            continue
        for column in ("担当", "期限"):
            value = row.get(column, "")
            if value.lower() in EMPTY or "要確認" in value:
                add(number, f"{column}の抜け", f"{section}の{column}を確認する。")
        deadline = row.get("期限", "")
        for _ in AMBIGUOUS.finditer(deadline):
            add(number, "あいまいな期限", "原文と会議日を照合し具体日を確認する。")
        found = list(DATE.finditer(deadline))
        if deadline.lower() not in EMPTY and "要確認" not in deadline:
            if not found:
                add(number, "期限の形式", "期限を西暦の日付と曜日にする。")
            elif any(not match["weekday"] for match in found):
                add(number, "期限の形式", "期限に曜日を付ける。")

    for number, line in enumerate(lines, 1):
        for match in DATE.finditer(line):
            month = match["m1"] or match["m2"] or match["m3"]
            day = match["d1"] or match["d2"] or match["d3"]
            try:
                actual = date(int(match["year"]), int(month), int(day))
            except ValueError:
                add(number, "不正な日付", "存在しない日付を原文と照合する。")
                continue
            if match["weekday"] and match["weekday"] != "月火水木金土日"[actual.weekday()]:
                add(number, "曜日のずれ", "日付と曜日を原文・暦で照合する。")
        for _ in FILLER.finditer(line):
            add(number, "つなぎの言葉", "フィラーか固有名詞の一部かを確かめる。")
        if not re.fullmatch(r"#{1,6}\s+要確認の一覧\s*", line):
            for _ in re.finditer("要確認", line):
                add(number, "残った要確認", "未確定の材料を確認する。")

    for number, line in sections["決定事項"]:
        for _ in PENDING.finditer(line):
            add(number, "決定欄の持ち帰り表現", "合意か検討・回答待ちかを原文で確かめる。")

    # 同姓や同じ役職を推測せず、利用者が登録した対応だけを調べる。
    names = {}
    participant_lines = {number for number, _ in sections.get("参加者", [])}
    for section, _, row in tables:
        if section != "参加者":
            continue
        canonical = row.get("表記", "")
        if not canonical or canonical == "なし" or "要確認" in canonical:
            continue
        aliases = row.get("別表記", "なし")
        for name in [canonical, *aliases.split("、")]:
            name = name.strip()
            if not name or name == "なし" or "要確認" in name:
                continue
            names.setdefault(name, set()).add(canonical)
    if names:
        pattern = re.compile("|".join(re.escape(name) for name in sorted(names, key=len, reverse=True)))
        for number, line in enumerate(lines, 1):
            if number in participant_lines:
                continue
            for match in pattern.finditer(line):
                targets = names[match[0]]
                if len(targets) > 1:
                    add(number, "人名の対応が不明", "同じ別表記が複数人に対応している。")
                elif match[0] not in targets:
                    add(number, "人名の表記ゆれ", "参加者欄の標準表記にそろえる。")
    return sorted(findings)


def main():
    parser = Parser(description="定型Markdownの議事録を読み取りだけで点検する。")
    parser.add_argument("minutes", help="UTF-8の議事録ファイル（1つ）")
    args = parser.parse_args()
    try:
        text = Path(args.minutes).read_text(encoding="utf-8-sig")
        if not text.strip() or "\x00" in text:
            raise InputError("空のファイルやNUL文字を含む入力は使えない。")
        findings = check(text)
    except (OSError, UnicodeError):
        print("入力エラー：読み取り可能なUTF-8の議事録ファイルを指定する。")
        return 2
    except InputError as error:
        print(f"入力エラー：{error}")
        return 2
    for number, category, detail in findings:
        print(f"行{number} [{category}] {detail}")
    print(f"検出合計：{len(findings)}件（検出項目の一致数。評価点ではない）")
    for category, count in sorted(Counter(item[1] for item in findings).items()):
        print(f"  {category}：{count}件")
    print(HUMAN)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
