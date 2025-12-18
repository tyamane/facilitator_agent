# 実装計画 - Slack ファシリテーターエージェント

## ゴール
Slack のスレッド内での会話状況に応じて、ファシリテーターエージェントがタスクを適切なサブエージェントに委譲し、議論やタスクを遂行するマルチエージェントシステムを構築する。

## ユーザーレビュー事項
- [ ] エージェント間通信用の JSON スキーマの確認
- [ ] フォルダ構成の確認

## 提案する変更内容

### アーキテクチャ設計
- **パターン**: 中央集権型オーケストレーション (Centralized Orchestration)
- **プロジェクトルート**: `/home/tyamane/work/facilitator_agent`
- **技術スタック**: Python, LLM (Vertex AI / Gemini)

### アーキテクチャ決定 (Architecture Decisions)

#### 専門家エージェントの実装: FunctionTool vs SubAgent
本システムでは、専門家エージェントを **`FunctionTool` (Python関数)** として実装し、ファシリテーターから呼び出す方式を採用します。

**理由とメリット:**
1. **インターフェースの統一と型安全性**: 
   - `FunctionTool` は入出力が Python の型ヒント (Pydantic) で定義されるため、ファシリテーターは確実に構造化されたデータ (`AgentResponse`) を受け取ることができます。
   - LLMベースの `SubAgent` そのものを用いると、自然言語でのやり取りになりがちで、厳密なデータ受け渡し（Handoffなど）の制御が難しくなります。
2. **状態管理の集約 (Stateless Worker Pattern)**:
   - 要件である「ファシリテーターが状態を管理・永続化する」という設計において、専門家エージェントは「状態を受け取って、結果と新状態を返す」純粋な関数として振る舞うのが最適です。
   - 独自のライフサイクルを持つ `SubAgent` インスタンスを使うと、状態の二重管理や同期の問題が発生しやすくなります。
3. **柔軟な実装**:
   - `FunctionTool` の内部で LLM API を呼ぶことは可能です。つまり「AI機能」を持ちつつ、「外部インターフェースは関数」という構成にできます。これにより、単純な検索ロジックのエージェントと、高度な思考を行うOpsエージェントを、ファシリテーターからは同じように扱うことができます。

### フォルダ構成案 (ADK Best Practices)
```text
/facilitator_agent
  /facilitator
    /__init__.py
    /agent.py       # Facilitator LlmAgent definition
    /prompts.py     # System instructions
    /tools.py       # Tools to call sub-agents
  /specialists
    /__init__.py
    /search_agent
      /__init__.py
      /agent.py     # Search Agent definition
      /tools.py     # Search tools
    /ops_agent
      /__init__.py
      /agent.py     # Ops Agent definition
      /tools.py     # Operations tools
  /models
    schema.py       # Shared Pydantic models
  /main.py          # Custom entry point (optional)
  /simulation.py    # Simulation script
  /.env             # Environment variables
```

### コンポーネント詳細

#### 1. データモデル (`models/schema.py`)
- **ThreadState**: 手話履歴、現在のステータス (OPEN, IN_PROGRESS, RESOLVED)、現在のゴールを保持。
- **AgentResponse**: サブエージェントからファシリテーターへ返す標準フォーマット。
  - `agent_name`: str
  - `content`: str (または JSON オブジェクト)
  - `confidence`: float

#### 2. ファシリテーターエージェント (`agents/facilitator/core.py`)
- **分析ループ**:
  1. 最新メッセージの取得
  2. `ThreadState` (状態) の更新 (LLM 使用)
  3. `NextAction` (次アクション) の決定 (ユーザーへの返信、エージェント X への委譲、待機)
  4. 委譲の場合: サブエージェント呼び出し -> 結果取得 -> 応答生成 -> Slack 投稿

#### 3. 専門家エージェント (Specialist Agents)
- **インターフェース**: `process(query: str, context: dict) -> AgentResponse`
- **検索エージェント**: RAG または単純なキーワード検索をシミュレート。

## 検証計画

### 自動テスト
- **ユニットテスト**: ファシリテーターのルーティングロジック (例: "AWSアカウントが必要" という発言が Ops Agent にルーティングされるか) をテスト。
- **シミュレーション**: `simulation.py` を作成し、Slack 風のメッセージ入力をシステムに与え、正しいエージェントが応答するか検証する。

### 手動検証
- `python simulation.py` を実行し、コンソール出力で会話フローが適切か確認する。
