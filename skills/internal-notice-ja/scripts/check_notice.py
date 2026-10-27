#!/usr/bin/env python3
"""社内連絡の機械的な指摘を標準出力へ出す。入力は変更しない。"""

import re
import sys
import unicodedata
from pathlib import Path


DATE = re.compile(
    r"(?<!\d)(?:\d{4}年)?\d{1,2}月\d{1,2}日"
    r"|(?<![\d/\-])(?:\d{4}[/\-])?\d{1,2}[/\-]\d{1,2}(?!\d)"
)
WEEKDAY = re.compile(r"\s*\([月火水木金土日](?:曜(?:日)?)?\)")
TIME = re.compile(r"\d{1,2}:\d{2}|\d{1,2}時(?:\d{1,2}分)?")
REQUEST = re.compile(
    r"ください|お願いします|お願いいたします|願います|求めます"
    r"|返信[はも]?不要|対応[はも]?不要|作業[はも]?不要"
)
VAGUE = re.compile(r"今週中|なるべく早く|できるだけ早く|近日中|後ほど|早急に|明日|本日中")
# 代表的な絵文字範囲。記号は文脈による誤検出があり、全Unicodeを網羅しない。
EMOJI = re.compile(
    "[\U0001F000-\U0001FAFF\u2600-\u27BF\u2300-\u23FF]"
    "|[©®™]\ufe0f?|[0-9#*]\ufe0f?\u20e3|\ufe0f"
)
HELP = "使い方: python3 check_notice.py <UTF-8の文面ファイル>"


def inspect(text):
    """空行を除く先頭行を件名、続く3行を冒頭として指摘を返す。"""
    lines = [
        (number, unicodedata.normalize("NFKC", line.strip()))
        for number, line in enumerate(text.splitlines(), 1)
        if line.strip()
    ]
    if not lines:
        return [(1, "文面が空です。件名と本文を記入してください。")]
    issues = []
    subject_number, subject = lines[0]
    subject = re.sub(r"^(?:件名|Subject)\s*[:：]\s*", "", subject, flags=re.I)
    if not subject:
        issues.append((subject_number, "件名が空です。"))
    if re.search(r"について[。.!！?？\s]*$", subject):
        issues.append((subject_number, "件名が「について」で終わっています。用件を具体化してください。"))
    if not DATE.search(subject):
        issues.append((subject_number, "件名に日付・期限の日付がありません。"))
    opening = "\n".join(line for _, line in lines[1:4])
    body_number = lines[1][0] if len(lines) > 1 else subject_number
    if not (DATE.search(opening) or TIME.search(opening)):
        issues.append((body_number, "冒頭3行に期限・確認時点を示す日付や時刻がありません。"))
    if not REQUEST.search(opening):
        issues.append((body_number, "冒頭3行に依頼の言葉・返信不要などの明記がありません。"))
    for number, line in lines:
        for _ in EMOJI.finditer(line):
            issues.append((number, "絵文字の候補があります。"))
        for match in VAGUE.finditer(line):
            issues.append((number, f"あいまいな期限の候補「{match.group()}」があります。"))
        for match in DATE.finditer(line):
            if not WEEKDAY.match(line[match.end():]):
                issues.append((number, f"曜日のない日付「{match.group()}」があります。"))
        for _ in re.finditer("要確認", line):
            issues.append((number, "「要確認」が残っています。材料を確認してください。"))
    return issues


def main():
    args = sys.argv[1:]
    if args in (["-h"], ["--help"]):
        print(HELP)
        return 0
    if len(args) != 1:
        print(HELP)
        return 2
    try:
        text = Path(args[0]).read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError, ValueError):
        # パスや原文をエラーへ転記しない。
        print("入力を読めません。UTF-8の読み取り可能なファイルを指定してください。")
        return 2
    issues = inspect(text)
    for number, message in issues:
        print(f"{number}行: {message}")
    print(f"直すべき点 {len(issues)}件")
    print("人が確認: 敬語の段階、転送されて困る情報、日付と曜日の整合、事実と根拠。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
