#!/usr/bin/env python3
"""日本語の点検候補を数え、行・列番号と一致文字列を表示する。"""

import argparse
import re
import sys
from collections import Counter
from pathlib import Path


PATTERNS = (
    ("重要さの結び", r"ことが重要です"),
    ("範囲のぼやけた修飾", r"さまざまな"),
    ("重い場面表現", r"において|における"),
    ("抽象的な達成表現", r"を実現"),
    ("結論前の助走", r"ご存じのとおり"),
    ("強調", r"非常に|圧倒的"),
    ("依頼の敬語", r"いただけますと幸いです"),
    ("定型的な締め", r"いかがでしたか"),
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path, help="点検するUTF-8の文章ファイル")
    args = parser.parse_args()
    try:
        content = args.file.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError):
        print("エラー: UTF-8の文章ファイルを読み取れません。", file=sys.stderr)
        return 2

    counts = Counter()
    for line_number, line in enumerate(content.splitlines(), start=1):
        matches = []
        for name, expression in PATTERNS:
            for match in re.finditer(expression, line):
                matches.append((match.start(), name, match.group()))
        for column, name, matched in sorted(matches):
            counts[name] += 1
            print(f"{line_number}:{column + 1}\t{name}\t{matched}")

    print("分類別件数:")
    for name, _ in PATTERNS:
        print(f"  {name}: {counts[name]}")
    print(f"合計: {sum(counts.values())}")
    print("件数は点検候補の数です。自然さや執筆者を判定する値ではありません。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
