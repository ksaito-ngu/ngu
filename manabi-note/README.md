# 学びの軌跡NOTE スキル

名古屋学院大学の「学びの軌跡NOTE」（PDFフォーム）を読み取り、アドバイザー面談の準備をするための Claude Code スキルです。

| スキル | すること |
|---|---|
| `/portfolio-feedback <PDFフォルダ> [ページまたは学期] [文字数]` | PDFのフォーム欄を学生ごとのMarkdownに抽出し、フィードバックコメント（CSV・MD）を作る |
| `/mendan-questions <PDFフォルダ>` | 抽出データとフィードバックから、学生ごとの面談質問リストと「面談で押さえる点」CSVを作る |

## 構成
```
manabi-note/
├── skills/
│   ├── portfolio-feedback/SKILL.md
│   └── mendan-questions/SKILL.md
└── py/
    ├── extract_portfolio.py      … PDF → 学生ごとのMD（学期名で指定するとPDFごとにページを自動判定）
    └── make_mendan_questions.py  … questions.json → 面談質問リスト・CSV
```

## 使い方
1. Python と PyMuPDF を入れる：`pip install pymupdf`
2. `skills/` の中のフォルダを、使うプロジェクトの `.claude/skills/` にコピーする
3. SKILL.md の `<manabi-note のフォルダ>` を、このフォルダの場所に読み替える（またはこのフォルダで Claude Code を起動する）
4. 学生の PDF を `学び/30/` などのフォルダに置き、`/portfolio-feedback 学び 1年秋 400` のように実行する

## 注意
- 学生の PDF・抽出データ・CSV は個人情報です。**このリポジトリには入れないでください**（.gitignore で除外しています）
- 学期名での指定（`1年春` `2S` `Ⅰ秋` など）は、各学期シートの先頭にある黄色の見出し「◯年次◯学期分」でページを決めます。29B様式（3ページ/学期）・30B様式（2ページ/学期）のどちらにも対応しています
