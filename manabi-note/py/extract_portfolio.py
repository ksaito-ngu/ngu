"""
学びの軌跡NOTE PDFからフォームフィールドを抽出 → 学生ごとのMDファイルに保存
使い方: python extract_portfolio.py <PDFフォルダ> [--pages 9,10]
  ページ1（学籍番号・氏名等）は常に読み取る。--pages で追加の対象ページを指定。
"""

import argparse
import io
import re
import sys
import unicodedata
from pathlib import Path

import fitz

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

BASIC_FIELDS = {"学籍番号", "名前", "SubmitButton1"}


def extract_one(pdf_path, target_pages):
    doc = fitz.open(str(pdf_path))

    sid, sname = "", ""
    basic_fields = {}
    content_fields = {}

    for page_idx, page in enumerate(doc):
        page_num = page_idx + 1
        for w in page.widgets():
            fn = w.field_name or ""
            fv = (w.field_value or "").strip()
            if not fn or not fv:
                continue
            if re.fullmatch(r"R\d+-\d+", fn):   # 数値欄（R3-1〜33、R4-1〜33 など）は不要（先生の指示 2026-10-06）
                continue

            if page_num == 1:
                if fn == "学籍番号":
                    sid = fv
                elif fn == "名前":
                    sname = fv
                elif fn not in BASIC_FIELDS:
                    basic_fields[fn] = fv
            elif page_num in target_pages:
                content_fields[fn] = fv

    doc.close()
    return sid, sname, basic_fields, content_fields


def build_markdown(sid, sname, basic_fields, content_fields, src_filename, target_pages):
    pages_str = ",".join(str(p) for p in sorted(target_pages))
    lines = [
        f"# 学びの軌跡NOTE - {sname}({sid})",
        "",
        "## 基本情報",
        f"- 学籍番号: {sid}",
        f"- 氏名: {sname}",
        f"- 元ファイル: {src_filename}",
    ]
    for k, v in basic_fields.items():
        lines.append(f"- {k}: {v}")

    lines.append("")
    lines.append(f"## ページ{pages_str}の記入内容")
    lines.append("")

    for fn, fv in content_fields.items():
        lines.append(f"### {fn}")
        lines.append(fv.replace("\r", "\n"))
        lines.append("")

    return "\n".join(lines)


# 学期名での指定（先生の指定 2026-10-10）
# 各学期の振り返りシートの先頭ページには、1〜2行目に黄色背景で「1年次春学期分」「1年次秋学期分」…が昇順に入っている。
# 様式は2種類あり（29B=45ページ・3ページごと、30B=36ページ・2ページごと）、ページ番号を固定できないため、
# PDFごとに黄色の見出しを読み取り「見出しのページ〜次の見出しの直前」をその学期のページとする。
# 学年は 1〜4・Ⅰ〜Ⅳ（NFKCで I〜IV になる）・一〜四 のどれでもよい。
# 学期は 春/S/前期/Spring、秋/A/後期/Fall/Autumn。英語の「1st year Fall」「Year 1 Fall」も可
SPRING = ("春", "前期", "S", "SPRING")
SEMESTER_RE = re.compile(
    r"^(?:YEAR\s*)?(IV|III|II|I|[1-4]|[一二三四])\s*(?:年次|年|ST|ND|RD|TH)?\s*(?:YEAR)?[\s_-]*"
    r"(SPRING|FALL|AUTUMN|春|前期|S|秋|後期|A)(?:学期|\s*SEMESTER|\s*TERM)?$", re.I)
GRADE = {"I": 1, "II": 2, "III": 3, "IV": 4, "一": 1, "二": 2, "三": 3, "四": 4}
HEADING_RE = re.compile(r"([1-4])年次(春|秋)学期分")


def parse_semester(text):
    """「1年春」「1春」「1S」「1年秋」「1A」「2年前期」などを (学年, '春'|'秋') に。該当しなければ None。"""
    m = SEMESTER_RE.match(unicodedata.normalize("NFKC", text).strip())
    if not m:
        return None
    g = m.group(1).upper()
    grade = int(g) if g.isdigit() else GRADE[g]
    return grade, ("春" if m.group(2).upper() in SPRING else "秋")


def _yellowish(c):
    return bool(c) and len(c) >= 3 and c[0] > 0.85 and c[1] > 0.75 and c[2] < 0.55


def semester_map(doc):
    """PDFの黄色見出しから {(学年, 学期): [ページ番号, ...]} を作る。"""
    heads = []
    for i, page in enumerate(doc):
        for dr in page.get_drawings():
            if not _yellowish(dr.get("fill")):
                continue
            t = unicodedata.normalize("NFKC", page.get_textbox(dr["rect"])).replace(" ", "")
            m = HEADING_RE.search(t)
            if m:
                heads.append((i + 1, (int(m.group(1)), m.group(2))))
                break
    result = {}
    for k, (pg, key) in enumerate(heads):
        nxt = heads[k + 1][0] if k + 1 < len(heads) else pg + (pg - heads[k - 1][0] if k else 3)
        result[key] = list(range(pg, nxt))
    return result


def parse_pages(pages_str):
    """「9,10,11」「11-14」「1年春」「２年秋」「17、18，19」などを受け付ける（全角・読点も可）。
    戻り値: (ページ番号の集合, 学期の集合)。学期はPDFごとにページへ変換する（resolve_pages）。"""
    pages, sems = set(), set()
    s = unicodedata.normalize("NFKC", pages_str).replace("、", ",")
    for part in s.split(","):
        part = part.strip()
        if not part:
            continue
        sem = parse_semester(part)
        if sem:
            sems.add(sem)
        elif re.fullmatch(r"\d+\s*-\s*\d+", part):
            start, stop = part.split("-", 1)
            pages.update(range(int(start), int(stop) + 1))
        elif part.isdigit():
            pages.add(int(part))
        else:
            raise SystemExit(f"「{part}」はページ番号としても学期名としても読めません。"
                             "例: 9,10,11 / 11-14 / 1年秋・1秋・1A・Ⅰ秋・一年秋・1Fall・1 Autumn（学年は1〜4）")
    return pages, sems


def resolve_pages(pdf_path, pages, sems):
    """学期指定をこのPDFのページ番号に変換して、数値指定と合わせて返す。"""
    if not sems:
        return set(pages)
    smap = semester_map(fitz.open(str(pdf_path)))
    result = set(pages)
    for sem in sems:
        if sem not in smap:
            raise SystemExit(f"{pdf_path.name}: 「{sem[0]}年次{sem[1]}学期分」の黄色見出しが見つかりません")
        result.update(smap[sem])
    return result


def main():
    parser = argparse.ArgumentParser(description="学びの軌跡NOTE PDF抽出")
    parser.add_argument("folder", help="PDFフォルダ")
    parser.add_argument("--pages", default="9,10",
                        help="対象ページ番号（カンマ区切り、範囲指定可。例: 9,10 / 5 / 11-14）。"
                             "学期名も可（1年春・1春・1S・1年前期・1年秋・1A … 4年秋）。ページはPDFごとに黄色の見出しから決める。"
                             "ページ1は常に読み取り。")
    args = parser.parse_args()

    folder = Path(args.folder)
    if not folder.exists():
        print(f"フォルダが見つかりません: {folder}")
        sys.exit(1)

    pages, sems = parse_pages(args.pages)
    if sems:
        names = "・".join(f"{g}年{t}" for g, t in sorted(sems))
        print(f"対象: 1(固定) + {names}（ページはPDFごとに黄色の見出しから決定）"
              + (f" + {','.join(map(str, sorted(pages)))}" if pages else ""))
    else:
        print(f"対象ページ: 1(固定) + {','.join(str(p) for p in sorted(pages))}")

    out_dir = folder / "抽出データ"
    out_dir.mkdir(exist_ok=True)

    pdfs = sorted(folder.glob("*.pdf"))
    print(f"対象PDF: {len(pdfs)} 件")

    results = {}
    for pdf in pdfs:
        target_pages = resolve_pages(pdf, pages, sems)
        sid, sname, basic_fields, content_fields = extract_one(pdf, target_pages)
        if not sid:
            print(f"  SKIP (学籍番号なし): {pdf.name}")
            continue

        md = build_markdown(sid, sname, basic_fields, content_fields, pdf.name, target_pages)
        out_path = out_dir / f"{sid}_{sname}.md"
        out_path.write_text(md, encoding="utf-8")

        n = len(content_fields)
        pg = ",".join(str(x) for x in sorted(target_pages))
        print(f"  OK: {sid} {sname} (ページ{pg}, {n} fields) -> {out_path.name}")
        results[sid] = sname

    print(f"\n完了: {len(results)} 名分 -> {out_dir}")


if __name__ == "__main__":
    main()
