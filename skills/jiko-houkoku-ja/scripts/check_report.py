#!/usr/bin/env python3
"""定型Markdownの事故報告書を読み取り、修正・確認候補を標準出力へ返す。"""

import argparse
from datetime import date, datetime
from pathlib import Path
import re


INTERNAL = ("概要・影響", "時系列", "原因の候補", "原因の整理", "再発防止策", "未確認の一覧")
EXTERNAL = ("事実", "影響", "お願いすること", "問い合わせ先", "今後の対応")
COLUMNS = {
    "時系列": ("日時", "段階", "出来事", "根拠"),
    "原因の候補": ("分野", "候補", "状態", "根拠"),
    "再発防止策": ("種類", "何を・どう変えるか", "担当", "期限", "完了の確かめ方"),
}
FIELDS = ("作業の手順", "使っている道具とその設定", "確認の仕組み", "人の配置と引き継ぎ",
          "外部のサービス・委託先", "気付く仕組み")
TYPES = ("早く気付く", "被害を小さくする", "起きないようにする")
EMPTY = {"", "-", "—", "なし", "未定", "不明", "未記入", "未確認", "tbd"}
DATE = re.compile(r"(?<!\d)(\d{4})-(\d{2})-(\d{2})(?!\d)(?:[（(]([月火水木金土日])(?:曜日|曜)?[）)])?")
STAMP = re.compile(r"\d{4}-\d{2}-\d{2}[（(][月火水木金土日](?:曜日|曜)?[）)] ([0-2]\d):([0-5]\d)")
HUMAN_ERROR = re.compile(r"不注意|確認不足|うっかり|ミス|失念|怠った|忘れた")
WEAK = re.compile(r"徹底|ダブルチェック|注意喚起|教育")
CONCRETE = re.compile(r"必須|禁止|照合|自動|制限|通知|記録|追加|固定|切替|切り替|停止|分離|表示|検証|保存")
INSIDE = re.compile(r"根本原因|引き金|悪化させた要因|なぜなぜ|原因の候補|原因の整理|不注意|確認不足|うっかり")
HUMAN = (
    "人が確かめる点：材料との一致、記録のない時間帯、原因の根拠と反証、"
    "個人を責める表現、対策の担当・期限・実行可能性、社内と社外の分離、"
    "個人情報への対応を公式案内で確認する必要性、説明・公表の可否。"
    "検出0件でも原因の正しさ・対策の効き目・社外への説明の適切さは保証しない。"
)


class InputError(ValueError):
    """非対応または不完全な入力形式。"""


class Parser(argparse.ArgumentParser):
    def _print_message(self, message, file=None):
        if message:
            print(message, end="")

    def error(self, message):
        self.print_usage()
        self.exit(2, "引数エラー：--helpで引数の指定方法を確認する。\n")


def read_file(filename):
    text = Path(filename).read_text(encoding="utf-8-sig")
    if not text.strip() or "\x00" in text:
        raise InputError("空入力・NUL文字は使えない。")
    return text


def parse(text, required):
    """固定の第2階層見出しとパイプ表だけを扱う。"""
    sections = {}
    current = None
    for number, line in enumerate(text.splitlines(), 1):
        if line.lstrip().startswith(("```", "~~~")):
            raise InputError("報告書をコードブロックで囲まない。")
        heading = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if heading:
            if len(heading[1]) == 2:
                current = heading[2]
                if current in sections:
                    raise InputError("第2階層の見出しを重複させない。")
                sections[current] = []
            elif len(heading[1]) < 2:
                current = None
            continue
        if current and line.strip():
            sections[current].append((number, line.strip()))
    if any(not sections.get(title) for title in required):
        raise InputError("必須見出しと内容が必要。references/templates.mdを参照する。")
    return sections


def table(sections, title):
    content = sections[title]
    rows = []
    for number, line in content:
        if not (line.startswith("|") and line.endswith("|")):
            raise InputError("時系列・原因の候補・再発防止策はパイプ表にする。")
        values = [value.strip() for value in line[1:-1].split("|")]
        rows.append((number, values))
    columns = COLUMNS[title]
    if len(rows) < 3 or tuple(rows[0][1]) != columns:
        raise InputError("表の列名・順序とデータ行を型に合わせる。")
    if not all(re.fullmatch(r":?-{3,}:?", cell) for cell in rows[1][1]):
        raise InputError("表には見出しの区切り行が必要。")
    if any(len(values) != len(columns) for _, values in rows):
        raise InputError("表の列数をそろえ、セル内には | を使わない。")
    return [(number, dict(zip(columns, values))) for number, values in rows[2:]]


def valid_date(match):
    return date(*(int(match[index]) for index in (1, 2, 3)))


def check(text, external=False, names=()):
    sections = parse(text, EXTERNAL if external else INTERNAL)
    findings = []

    def add(number, level, label):
        findings.append((number, level, label))

    for number, line in enumerate(text.splitlines(), 1):
        for match in DATE.finditer(line):
            try:
                actual = valid_date(match)
            except ValueError:
                add(number, "×", "存在しない日付")
                continue
            if not match[4]:
                add(number, "×", "日付の曜日抜け")
            elif match[4] != "月火水木金土日"[actual.weekday()]:
                add(number, "×", "日付と曜日のずれ")
        if not re.fullmatch(r"## 未確認の一覧", line):
            for _ in re.finditer("未確認", line):
                add(number, "△", "残った未確認：確かめる担当と対象を照合する")
        if external:
            for _ in INSIDE.finditer(line):
                add(number, "△", "社外向けに社内の原因分析の言葉が残っている")
            for name in sorted(set(names)):
                if name in line:
                    add(number, "×", "社外向けに登録した人名が残っている")
    if external:
        return sorted(findings)

    candidates = table(sections, "原因の候補")
    for number, row in candidates:
        if row["分野"] not in FIELDS:
            raise InputError("原因の候補は指定の6分野にする。")
        if not row["候補"] and not row["状態"] and not row["根拠"]:
            continue
        if row["状態"] not in ("確認済み", "疑い", "否定"):
            add(number, "×", "原因候補の状態は確認済み・疑い・否定にする")
    if sorted(row["分野"] for _, row in candidates) != sorted(FIELDS):
        raise InputError("原因の候補は各分野を1行ずつ用意する。該当しない欄は空にする。")
    for title in ("原因の候補", "原因の整理"):
        for number, line in sections[title]:
            if HUMAN_ERROR.search(line):
                add(number, "△", "人の誤りの表現：仕組みの欠けまで掘れているか確認する")

    measures = table(sections, "再発防止策")
    for number, row in measures:
        action = row["何を・どう変えるか"]
        if not action or action.lower() in EMPTY:
            add(number, "×", "対策の内容抜け")
        elif WEAK.search(action) and not CONCRETE.search(action):
            add(number, "△", "徹底・確認・教育だけの対策の可能性：変更内容を具体化する")
        if row["種類"] not in TYPES:
            add(number, "×", "対策の種類抜け・指定外")
        for key in ("担当", "期限"):
            if row[key].lower() in EMPTY or "未確認" in row[key]:
                add(number, "×", f"対策の{key}抜け")
        if row["担当"] not in EMPTY and re.search(r"チーム|全員|部一同|全社", row["担当"]):
            add(number, "△", "対策の担当を1人の役割にする")
        deadline = DATE.fullmatch(row["期限"])
        if row["期限"].lower() not in EMPTY and "未確認" not in row["期限"] and not deadline:
            add(number, "×", "期限はYYYY-MM-DD（曜）の具体日にする")
        if row["完了の確かめ方"].lower() in EMPTY:
            add(number, "△", "対策の完了の確かめ方抜け")
    if "発見の遅れ：あり" in text and not any(row["種類"] == "早く気付く" for _, row in measures):
        add(1, "×", "発見が遅れた事故に早く気付く対策がない")

    previous = None
    for number, row in table(sections, "時系列"):
        value = row["日時"]
        if "未確認" in value:
            continue
        match = STAMP.fullmatch(value)
        if not match:
            add(number, "×", "時系列の日時はYYYY-MM-DD（曜） HH:MMにする")
            continue
        try:
            day = valid_date(DATE.match(value))
            current = datetime.combine(day, datetime.min.time()).replace(
                hour=int(match[1]), minute=int(match[2]))
        except ValueError:
            add(number, "×", "時系列に存在しない日時")
            continue
        if previous is not None and current < previous:
            add(number, "×", "時系列の時刻の順序が逆転している")
        previous = current
    return sorted(findings)


def main():
    parser = Parser(description="事故報告書を読み取りだけで点検する。文面・パス・人名は出力しない。")
    parser.add_argument("report", help="UTF-8の社内報告書")
    parser.add_argument("--external", action="append", default=[], help="別文書の社外向け下書き（繰り返し可）")
    parser.add_argument("--name", action="append", default=[], help="社外に出さない人名の表記（繰り返し可）")
    args = parser.parse_args()
    try:
        if any(not name.strip() for name in args.name):
            raise InputError("空の人名は登録できない。")
        results = [("社内", check(read_file(args.report)))]
        for index, filename in enumerate(args.external, 1):
            results.append((f"社外{index}", check(read_file(filename), True, args.name)))
    except (OSError, UnicodeError):
        print("入力エラー：読み取り可能なUTF-8のファイルを指定する。")
        return 2
    except InputError as error:
        print(f"入力エラー：{error}")
        return 2
    total = 0
    for label, findings in results:
        for number, level, detail in findings:
            print(f"{level} {label} 行{number}：{detail}")
        print(f"{label}：{len(findings)}件")
        total += len(findings)
    print(f"検出合計：{total}件（検出項目の一致数。報告書の評価点ではない）")
    print(HUMAN)
    return 1 if total else 0


if __name__ == "__main__":
    raise SystemExit(main())
