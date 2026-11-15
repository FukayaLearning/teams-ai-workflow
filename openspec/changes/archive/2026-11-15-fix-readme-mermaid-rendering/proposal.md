## Why

`README.md` の「1. システムアーキテクチャ概要」に含まれる Mermaid 図（flowchart）が、GitHub などの Mermaid レンダラーでパースエラーとなり表示できない。原因は `subgraph` のタイトルをクォートせずに記述しており、タイトル中の括弧 `(` `)` やハイフン `-` が Mermaid の構文トークンとして解釈されるためである。README は本プロジェクトの構成を説明する主要な入口であり、図が壊れていると利用者が全体像を把握できない。

## What Changes

- `README.md` の Mermaid 図における `subgraph` タイトルを、引用符付き文字列として記述する形に修正する。
  - `subgraph Microsoft 365 クラウド (24時間稼働)` → `subgraph "Microsoft 365 クラウド (24時間稼働)"`
  - `subgraph Windows PC (社内イントラネット内)` → `subgraph "Windows PC (社内イントラネット内)"`
  - `subgraph teams-ai-workflow (本アプリ)` → `subgraph "teams-ai-workflow (本アプリ)"`
  - `subgraph LM Studio (Local Server)` → `subgraph "LM Studio (Local Server)"`
- ノード、エッジ、ラベル、図の階層構造（ネストした subgraph）は変更しない。表示内容と意味は現状維持とする。
- ドキュメントのみの修正であり、アプリケーションコード・設定・依存関係には変更を加えない。

## Capabilities

### New Capabilities

なし（ドキュメント表示の修正のみで、システムの振る舞いに関する要求の追加はない）。

### Modified Capabilities

なし（既存の要求仕様の変更はない）。

> 本変更はドキュメント（README の Mermaid 記法）のみの修正であり、仕様レベルの振る舞いに影響しないため、`.openspec.yaml` に `skip_specs: true` を設定して spec 成果物を省略する。

## Impact

- 影響ファイル: `README.md`（Mermaid コードブロックのみ）
- 影響コード: なし
- 影響 API・依存関係・設定: なし
- 検証: Mermaid パーサー（GitHub プレビュー / `mmdc` 等）で図がエラーなくレンダリングされることを確認する
