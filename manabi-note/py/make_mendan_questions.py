# -*- coding: utf-8 -*-
"""
学びの軌跡NOTE の抽出データ（フィードバック付き）と質問定義 JSON から、面談質問リストを作る。

使い方:
    python py/make_mendan_questions.py <PDFフォルダ>
    例: python py/make_mendan_questions.py "学び/30"

入力:
    <PDFフォルダ>/抽出データ_FB/<学籍番号4桁>_<氏名>.md   （/portfolio-feedback の出力）
    <PDFフォルダ>/面談質問リスト/questions.json            （学生ごとの質問。/mendan-questions で作る）
出力（<PDFフォルダ>/面談質問リスト/）:
    <学籍番号4桁>_<氏名>_面談質問.md   … 1人1ファイル
    <学年>_面談質問リスト_全員.md       … 全員分
    ../<フォルダ名>_面談で押さえる点.csv … 学籍番号・氏名・面談で押さえる点（BOM付きUTF-8）

questions.json の形:
    {"学年": "30B", "対象": "1年次秋学期", "ページ": "9〜11",
     "students": {"0003": {"要点": "...", "押さえる点": "...",
                           "1": ["質問", ...], "2": [...], ..., "6": [...], "確認": [...]}}}
    "1"〜"6" は面談アプリと同じ6ステップ。「確認」は確認事項・相談への回答。
"""
import csv
import json
import re
import sys
from pathlib import Path

STEPS = [("1", "GPA・出席率の確認"), ("2", "達成できたこと"), ("3", "達成できなかったこと"),
         ("4", "今学期の行動目標"), ("5", "資格取得の計画"), ("6", "インターンシップ・将来")]

# 冒頭の表に出す項目（抽出データのフィールド名 → 表示名）。ある項目だけを表示する
HEADER_FIELDS = [
    ("1通年出席率", "1年次 出席率", "%"), ("1通年GPA", "1年次 GPA", ""),
    ("1春GPA", "1年次春学期 GPA", ""), ("1秋目標GPA", "1年次秋学期の目標GPA", ""),
    ("1春成長目標DP", "1年次春学期の成長目標DP", ""), ("1秋成長目標DP", "1年次秋学期の成長目標DP", ""),
    ("2春目標GPA", "2年次春学期の目標GPA", ""), ("2春成長目標DP", "2年次春学期の成長目標DP", ""),
    ("2春出席率", "2年次春学期 出席率", "%"), ("2春GPA", "2年次春学期 GPA", ""),
    ("2秋目標GPA", "2年次秋学期の目標GPA", ""), ("2秋成長目標DP", "2年次秋学期の成長目標DP", ""),
]


def field(s, k):
    m = re.search(rf"^### {re.escape(k)}\n(.+?)\n", s, flags=re.M)
    return m.group(1).strip() if m else None


def build(sid, q, s, name, grade, h):
    fb = s.split("## アドバイザー教員からのフィードバック")[1].strip() if "## アドバイザー教員からのフィードバック" in s else "（フィードバックなし）"
    rows = []
    for k, label, unit in HEADER_FIELDS:
        v = field(s, k)
        if v:
            rows.append(f"| {label} | {v}{unit if v.replace('.', '').isdigit() else ''} |")
    L = [f"{h} 面談質問リスト — {name}（{grade}{sid}）", "", "| 項目 | 内容 |", "|---|---|", *rows,
         f"| 要点 | {q['要点']} |", "", f"{h}# 質問"]
    n = 0
    for k, title in STEPS:
        L += ["", f"{h}## Step {k}：{title}"]
        for x in q.get(k, []):
            n += 1
            L.append(f"{n}. {x}")
    L += ["", f"{h}## 確認事項・相談"]
    for x in q.get("確認", []):
        n += 1
        L.append(f"{n}. {x}")
    L += ["", f"{h}# 面談で伝えること（フィードバックより）", "", fb, "", f"{h}# 面談メモ", "", "- ", ""]
    return "\n".join(L), n


def main(folder):
    base = Path(folder).resolve()
    src = base / "抽出データ_FB"
    out = base / "面談質問リスト"
    spec = json.loads((out / "questions.json").read_text(encoding="utf-8-sig"))
    grade = spec["学年"]
    students = spec["students"]
    mds = {p.stem.split("_", 1)[0]: p for p in src.glob("*.md")}
    missing = sorted(set(mds) - set(students))
    extra = sorted(set(students) - set(mds))
    if extra:
        sys.exit(f"抽出データにない学籍番号が questions.json にあります: {extra}")

    whole = [f"# 面談質問リスト（{grade}・{spec.get('対象', '')}）", "",
             f"> 学びの軌跡NOTE（{spec.get('ページ', '')}ページ）とフィードバックをもとに作成。各学生 6ステップ＋確認事項・相談。", ""]
    csv_rows = []
    for sid in sorted(students):
        q = students[sid]
        md = mds[sid]
        s = md.read_text(encoding="utf-8")
        name = md.stem.split("_", 1)[1]
        one, n = build(sid, q, s, name, grade, "#")
        (out / f"{sid}_{name}_面談質問.md").write_text(one, encoding="utf-8")
        two, _ = build(sid, q, s, name, grade, "##")
        whole += [two, "---", ""]
        csv_rows.append([f"{grade}{sid}", name, q.get("押さえる点", q["要点"])])
        print(f"  {grade}{sid} {name}: {n} 問")
    (out / f"{grade}_面談質問リスト_全員.md").write_text("\n".join(whole), encoding="utf-8")
    cpath = base / f"{base.name}_面談で押さえる点.csv"
    with open(cpath, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["学籍番号", "氏名", "面談で押さえる点"])
        w.writerows(csv_rows)
    print(f"完了: {len(students)} 名 → {out}")
    print(f"CSV: {cpath}")
    if missing:
        print(f"※ questions.json に質問がない学生: {missing}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1])
