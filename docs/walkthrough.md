# ファシリテーターエージェント実装 Walkthrough

## 目的
ADK (Agent Development Kit) を用いて、ユーザーごとのコンテキストを維持し、適切な専門家エージェントにルーティングし続ける「Sticky Session」機能を持つファシリテーターエージェントを実装・検証すること。

## 実施内容

### 1. カスタムエージェント実装 (`FacilitatorAgent`)
- ADK標準の `Agent` クラスを継承した `FacilitatorAgent` を作成。
- **構成**:
  - `llm_router`: 初回ルーティングを担当する内部 `LlmAgent`。
  - `_run_async_impl`: メイン実行ループ。`ThreadState` をチェックし、Sticky Session が有効な場合は LLM をバイパスして直接ツールを実行するロジックを実装。
  - `_after_tool_callback`: 標準フロー（LLM Router経由）の結果をインターセプトし、状態 (`active_agent`, `agent_state`) を更新・永続化するロジック。

### 2. 状態永続化 (State Persistence) の課題と解決
- **課題**: ADK の `InMemorySessionService` と `Runner` の仕様上、エージェント内で `session.state` を更新しても、次のターンでロードされるセッションオブジェクトに反映されない（コピーが渡される、または `Event` 経由での更新のみが反映されるため）問題が発生。
- **解決策**:
  - **Sticky Flow**: `Event` を yield する際に `EventActions(stateDelta=...)` を含めることで、`Runner` 経由で正規に状態を更新。
  - **Standard Flow & Manual Backup**: `_run_async_impl` およびコールバック内で、`InvocationContext` から `session_service` にアクセスし、手動でセッションオブジェクトを同期 (`service.sessions[app][user][id] = session`) することで、即時かつ確実な永続化を実現。

### 3. シミュレーション検証 (`simulation.py`)
- `InMemorySessionService` を使用したローカルシミュレーションスクリプトを作成。
- **検証シナリオ**:
  1. **Turn 1**: ユーザー "Create account..." -> Router -> OpsAgent (Mock) -> "Plan create... (Confirming)"
  2. **Turn 2**: ユーザー "yes, please" -> Facilitator (Sticky Logic) -> OpsAgent (Direct) -> "HANDOFF: Account created"
- **結果**:
  - Turn 1 で `active_agent="OpsAgent"` および `agent_state` が正しく保存されることを確認。
  - Turn 2 で Sticky Session ロジックが発動し、LLM Router を呼び出さずに OpsAgent が実行されることを確認。
  - OpsAgent が前回の状態 (`agent_state`) を復元し、パラメータ再入力を求めずに処理を完了 (Handoff) することを確認。

## 成果物
- `facilitator/custom_agent.py`: Sticky Session 実装済みエージェント
- `facilitator/runtime.py`: (旧プロトタイプ、現在は `custom_agent.py` 推奨)
- `specialists/ops_agent/tools.py`: ステートフルな業務エージェントロジック
- `simulation.py`: 検証用スクリプト

## 次のステップ
- FastAPI アプリケーション (`main.py`) 経由での動作確認 (`adk web` 利用)
- 実際の Slack / PubSub 連携に向けたインターフェース整備
