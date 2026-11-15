## 1. README の Mermaid 図修正

- [x] 1.1 `README.md` の Mermaid 図（`flowchart TD`）内で、括弧やハイフンを含む `subgraph` タイトル4箇所を引用符付き文字列に修正する（`subgraph "Microsoft 365 クラウド (24時間稼働)"`、`subgraph "Windows PC (社内イントラネット内)"`、`subgraph "teams-ai-workflow (本アプリ)"`、`subgraph "LM Studio (Local Server)"`）。
  - 検証: `grep -n 'subgraph "' README.md` で4箇所すべてが引用符付きになっていること、`grep -n 'subgraph [^"]' README.md` が0件であることを確認する。
- [x] 1.2 ノード定義・エッジ・エッジラベル・ネスト構造に変更が入っていないことを差分で確認する。
  - 検証: `git diff README.md` を確認し、変更が `subgraph` 行のみに限定されていること。

## 2. レンダリング検証

- [x] 2.1 README の Mermaid 図をパーサーで検証し、構文エラーが出ないことを確認する。
  - 検証: `npx -y @mermaid-js/mermaid-cli -i README.md -o /tmp/readme-diagram.svg`（または Mermaid Live Editor / GitHub のプレビュー）で図がエラーなくレンダリングされること。エラー出力に `Parse error` が含まれないこと。
- [x] 2.2 README 内に他に壊れた Mermaid ブロックがないことを確認する。
  - 検証: `grep -n '```mermaid' README.md` で検出される全ブロック（現状1件）を上記と同じ方法で検証する。

## 3. 変更の確定

- [x] 3.1 OpenSpec の検証コマンドで変更が整合していることを確認する。
  - 検証: `openspec validate --change fix-readme-mermaid-rendering` が成功すること。
- [x] 3.2 変更内容をレビュー用に提示し、コミットはユーザーの指示があるまで行わない。
  - 検証: 修正後の README の該当箇所と `git diff` を提示する。
