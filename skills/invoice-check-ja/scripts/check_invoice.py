#!/usr/bin/env python3
"""独自CSVの請求書を読み、機械的な点検結果だけを標準出力へ返す。"""

import argparse
import calendar
import csv
from datetime import date, timedelta
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP, localcontext
from pathlib import Path
import re
import sys

FIELDS = {
    'kind', 'invoice_id', 'issuer', 'registration', 'recipient', 'issue_date',
    'due_date', 'basis', 'rounding', 'closing_day', 'payment_months', 'payment_day',
    'weekend', 'invoice_amount', 'paid_amount', 'history', 'transaction_date',
    'description', 'rate', 'reduced', 'amount', 'tax',
}
HEADER = FIELDS - {'transaction_date', 'description', 'rate', 'reduced', 'amount', 'tax'}
LINE = {'kind', 'invoice_id', 'transaction_date', 'description', 'rate', 'reduced', 'amount', 'tax'}
TOTAL = {'kind', 'invoice_id', 'rate', 'amount', 'tax'}
ROUNDING = {'切り捨て': ROUND_FLOOR, '切り上げ': ROUND_CEILING, '四捨五入': ROUND_HALF_UP}


class InputError(ValueError):
    """入力形式の誤り。入力本文はエラーへ転記しない。"""


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise InputError('引数を確認してください（--help参照）')


def parse_date(value):
    """日付、表記体系、付記された曜日を返す。平成・令和のみ対応。"""
    match = re.fullmatch(
        r'(?:(令和|平成)(元|[0-9]+)年([0-9]{1,2})月([0-9]{1,2})日|'
        r'([0-9]{4})-([0-9]{2})-([0-9]{2}))(?:[（(]([月火水木金土日])[）)])?', value)
    if not match:
        raise InputError('日付はYYYY-MM-DDまたは平成・令和の年月日で指定してください')
    era, year, month, day, gy, gm, gd, weekday = match.groups()
    try:
        if era:
            n = 1 if year == '元' else int(year)
            if n < 1:
                raise ValueError
            result = date(n + (2018 if era == '令和' else 1988), int(month), int(day))
            if era == '令和' and result < date(2019, 5, 1):
                raise ValueError
            if era == '平成' and not date(1989, 1, 8) <= result <= date(2019, 4, 30):
                raise ValueError
        else:
            result = date(int(gy), int(gm), int(gd))
    except ValueError as exc:
        raise InputError('存在しない日付または元号の範囲外です') from exc
    return result, '和暦' if era else '西暦', weekday


def money(value):
    if not value:
        return None
    if not re.fullmatch(r'[0-9]{1,15}(?:\.[0-9]{1,2})?', value):
        raise InputError('金額は非負、整数部15桁以内、小数2桁以内で指定してください')
    return Decimal(value)


def read_csv(path):
    invoices = {}
    with path.open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream, strict=True)
        if reader.fieldnames is None or len(reader.fieldnames) != len(FIELDS) or set(reader.fieldnames) != FIELDS:
            raise InputError('CSV列名が仕様と一致しません')
        for number, raw in enumerate(reader, 2):
            if None in raw or None in raw.values():
                raise InputError(f'CSV {number}行目の列数が一致しません')
            row = {key: value.strip() for key, value in raw.items()}
            kind, key = row['kind'], row['invoice_id']
            allowed = {'header': HEADER, 'line': LINE, 'total': TOTAL}.get(kind)
            if not key or allowed is None:
                raise InputError(f'CSV {number}行目のkindまたはinvoice_idが不正です')
            if any(value for field, value in row.items() if field not in allowed):
                raise InputError(f'CSV {number}行目に行種別と異なる列の値があります')
            group = invoices.setdefault(key, {'header': [], 'line': [], 'total': []})
            group[kind].append(row)
            for field in ('amount', 'tax', 'invoice_amount', 'paid_amount'):
                money(row[field])
            for field in ('transaction_date', 'issue_date', 'due_date'):
                if row[field]:
                    parse_date(row[field])
            enums = {'basis': ('税抜', '税込'), 'rounding': tuple(ROUNDING),
                     'weekend': ('前', '次'), 'history': ('いつも期日どおり', 'ときどき遅れる', '何度も遅れる'),
                     'rate': ('10', '8'), 'reduced': ('はい', 'いいえ')}
            for field, choices in enums.items():
                if row[field] and row[field] not in choices:
                    raise InputError(f'CSV {number}行目の{field}は対応する選択肢ではありません')
            for field in ('closing_day', 'payment_day'):
                if row[field] and row[field] != '末' and not re.fullmatch(r'(?:[1-9]|[12][0-9]|3[01])', row[field]):
                    raise InputError(f'CSV {number}行目の日指定は末または1〜31です')
            if row['payment_months'] and row['payment_months'] not in ('0', '1', '2'):
                raise InputError('payment_monthsは0・1・2に対応します')
    if not invoices or any(len(g['header']) != 1 for g in invoices.values()):
        raise InputError('各請求書にheaderが1行必要です。空CSVは扱えません')
    return invoices


def month_day(year, month, day):
    last = calendar.monthrange(year, month)[1]
    return date(year, month, last if day == '末' else min(int(day), last))


def shifted(value, months, day):
    index = value.year * 12 + value.month - 1 + months
    year, month = divmod(index, 12)
    return month_day(year, month + 1, day)


def inspect(key, group, as_of, holidays):
    h, lines, totals = group['header'][0], group['line'], group['total']
    findings = []

    def add(level, message):
        findings.append((level, message))

    for field, label in [('issuer', '発行者の名称'), ('registration', '登録番号'), ('recipient', '受取者の名称')]:
        if not h[field]:
            add('直すべき点', f'{label}が欠けています')
    reg = h['registration']
    if reg:
        if not re.fullmatch(r'T[0-9]{13}', reg):
            add('直すべき点', '登録番号の形式はTと13桁の半角数字です')
        else:
            digits = reg[1:]
            checksum = 9 - sum(int(p) * (1 if n % 2 else 2)
                               for n, p in enumerate(reversed(digits[1:]), 1)) % 9
            if int(digits[0]) != checksum:
                add('要確認', '法人番号の形としては合わない（個人事業者の番号の可能性もあるため、国税庁の公表サイトで確かめる）')
    dates, styles = {}, set()
    for label, value in [('請求日', h['issue_date']), ('記載期日', h['due_date'])] + [
            (f'取引日{n}', row['transaction_date']) for n, row in enumerate(lines, 1)]:
        if value:
            parsed, style, weekday = parse_date(value)
            dates[label] = parsed
            styles.add(style)
            if weekday and weekday != '月火水木金土日'[parsed.weekday()]:
                add('直すべき点', f'{label}の曜日と日付が一致しません')
        else:
            add('直すべき点' if label.startswith('取引日') else '要確認', f'{label}が未記載です')
    if len(styles) > 1:
        add('要確認', '和暦と西暦が混在しています（換算日を照合）')
    transactions = [v for k, v in dates.items() if k.startswith('取引日')]
    if dates.get('請求日') and any(dates['請求日'] < d for d in transactions):
        add('直すべき点', '取引日より前の請求日です')
    if not lines:
        add('直すべき点', '明細がなく、取引年月日・取引内容・適用税率を点検できません')
    for n, row in enumerate(lines, 1):
        for field, label in [('description', '取引内容'), ('rate', '適用税率'), ('amount', '金額')]:
            if not row[field]:
                add('直すべき点', f'明細{n}の{label}が欠けています')
        if row['rate'] == '8' and row['reduced'] != 'はい':
            add('直すべき点', f'明細{n}の軽減税率対象の表示がありません')
        if row['rate'] == '10' and row['reduced'] == 'はい':
            add('要確認', f'明細{n}の10%と軽減対象表示の組合せを確認してください')
    if not h['basis']:
        add('要確認', '税抜・税込の区別が未指定です')
    if not h['rounding']:
        add('要確認', '端数処理の方法が未指定です')
    gross = Decimal(0)
    reliable = bool(lines) and bool(h['basis']) and all(r['rate'] and r['amount'] for r in lines)
    for n, total in enumerate(totals, 1):
        for field, label in [('amount', '対価の合計'), ('tax', '消費税額等')]:
            if not total[field]:
                add('直すべき点', f'税率別合計{n}の{label}が欠けています')
                reliable = False
    for rate in sorted({r['rate'] for r in lines + totals if r['rate']}):
        rows = [r for r in lines if r['rate'] == rate]
        summary = [r for r in totals if r['rate'] == rate]
        if len(summary) != 1:
            add('直すべき点', f'{rate}%の税率別合計が欠落または重複しています')
            reliable = False
            continue
        total = summary[0]
        if not rows:
            add('要確認', f'{rate}%の税率別合計に対応する明細がありません')
            reliable = False
        complete = bool(rows) and all(r['amount'] for r in rows)
        amount = sum((money(r['amount']) for r in rows), Decimal(0)) if complete else None
        if amount is not None and total['amount'] and amount != money(total['amount']):
            add('直すべき点', f'{rate}%の明細合計{amount}円と記載合計{total["amount"]}円が不一致です')
            reliable = False
        if amount is not None and h['basis'] and h['rounding']:
            tax = (amount * Decimal(rate) / (100 if h['basis'] == '税抜' else 100 + int(rate))).quantize(
                Decimal('1'), rounding=ROUNDING[h['rounding']])
            print(f'  {rate}% 検算: 対価{amount}円 / 税額{tax}円')
            if total['tax'] and tax != money(total['tax']):
                add('直すべき点', f'{rate}%の記載税額{total["tax"]}円と検算{tax}円が不一致です')
                reliable = False
            if all(r['tax'] for r in rows):
                line_tax = sum((money(r['tax']) for r in rows), Decimal(0))
                if line_tax != tax:
                    add('要確認', f'{rate}%の明細税額合計{line_tax}円と一括計算{tax}円に差額{line_tax - tax}円（明細ごとの端数処理の可能性）')
        if total['amount'] and total['tax']:
            gross += money(total['amount']) + (money(total['tax']) if h['basis'] == '税抜' else 0)
    if any(not r['rate'] for r in totals):
        add('直すべき点', '税率別合計の適用税率が欠けています')
        reliable = False
    billed, paid = money(h['invoice_amount']), money(h['paid_amount'])
    if billed is None or paid is None:
        add('要確認', '請求総額または基準日時点の入金額が未指定です。催促前に確認してください')
    if reliable and billed is not None and billed != gross:
        add('直すべき点', f'請求総額{billed}円と税率別合計からの総額{gross}円が不一致です')
    if paid is not None and billed is not None and paid > billed:
        add('要確認', '入金額が請求総額を超えています')
    due = None
    terms = ('closing_day', 'payment_months', 'payment_day', 'weekend')
    if all(h[f] for f in terms) and len(transactions) == len(lines) and lines:
        cycles = set()
        for transaction in transactions:
            closing = month_day(transaction.year, transaction.month, h['closing_day'])
            if transaction > closing:
                closing = shifted(transaction, 1, h['closing_day'])
            cycles.add(closing)
        if len(cycles) != 1:
            add('要確認', '複数の締め期間の明細があります。期日を一つに決めません')
        else:
            closing = next(iter(cycles))
            due = shifted(closing, int(h['payment_months']), h['payment_day'])
            if due < closing:
                add('要確認', '支払条件から求めた期日が締め日より前です')
                due = None
            else:
                step = -1 if h['weekend'] == '前' else 1
                while due.weekday() >= 5 or due in (holidays or set()):
                    due += timedelta(days=step)
                print(f'  締め日: {closing} / 計算期日: {due}')
                if dates.get('記載期日') and dates['記載期日'] != due:
                    add('要確認', '記載期日と計算期日が不一致です。契約条件の確認まで催促を保留してください')
                    due = None
    else:
        add('要確認', '締め日・支払条件・休日の扱いまたは取引日が不足し、期日を確定できません')
    if holidays is None:
        add('要確認', '祝日一覧がないため、祝日を考慮していません')
    if not h['history']:
        add('要確認', '支払いの履歴が未提供です。催促は①から始めます')
    for level, message in findings:
        print(f'  [{level}] {message}')
    errors = sum(level == '直すべき点' for level, _ in findings)
    questions = len(findings) - errors
    print(f'  集計: 直すべき点 {errors}件 / 要確認 {questions}件')
    if not findings:
        print('  [問題なし] 機械点検の範囲で指摘はありません')
    print('  人が確かめる点: 公表サイトの登録状況・取引時点の有効性、税率の適用、契約条件、税務判断')
    if due is not None and as_of > due:
        if billed is not None and paid is not None and billed > paid:
            return f'{key}: 期日{due} / 超過{(as_of - due).days}日 / 未入金{billed - paid}円 / 履歴{h["history"] or "未提供（①）"}（催促前に指摘・入金状況を再確認）'
        if billed is None or paid is None:
            return f'{key}: 期日{due}超過 / 入金状況・金額は要確認（催促保留）'
    return None


def main():
    parser = Parser(description=__doc__)
    parser.add_argument('csv', type=Path, help='独自仕様のUTF-8 CSV')
    parser.add_argument('--as-of', required=True, help='点検基準日')
    parser.add_argument('--holidays', type=Path, help='休日一覧。1行1日付、空行可')
    try:
        args = parser.parse_args()
        as_of, _, weekday = parse_date(args.as_of)
        if weekday and weekday != '月火水木金土日'[as_of.weekday()]:
            raise InputError('基準日の日付と曜日が一致しません')
        holidays = None
        if args.holidays is not None:
            holidays = set()
            for value in args.holidays.read_text(encoding='utf-8-sig').splitlines():
                if value.strip():
                    d, _, weekday = parse_date(value.strip())
                    if weekday and weekday != '月火水木金土日'[d.weekday()]:
                        raise InputError('休日一覧の日付と曜日が一致しません')
                    holidays.add(d)
        invoices = read_csv(args.csv)
        overdue = []
        with localcontext() as context:
            context.prec = 50
            for key, group in invoices.items():
                print(f'請求書 {key}')
                item = inspect(key, group, as_of, holidays)
                if item:
                    overdue.append(item)
        print(f'基準日 {as_of} の期日超過一覧: {len(overdue)}件（期日未確定・完済分は含みません）')
        for item in overdue:
            print(f'  {item}')
        return 0
    except InputError as exc:
        print(f'入力エラー: {exc}')
        return 2
    except (OSError, UnicodeError, csv.Error, OverflowError, ValueError):
        # ファイル名・入力値などをエラーへ転記しない。
        print('入力エラー: CSV仕様・日付・金額・選択肢・ファイルの読み取り権限を確認してください（--help参照）')
        return 2


if __name__ == '__main__':
    sys.exit(main())
