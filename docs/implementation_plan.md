# 実装計画 - Slack ファシリテーターエージェント

## 概要
Slack上の議論を整理し、適切な専門家エージェントにタスクを振り分ける「ファシリテーターAI」を構築する。
Google ADK (Agent Development Kit) を基盤とし、将来的な FastAPI ビルドおよび他システム連携を見据えた設計とする。

## ⚠️ ユーザーレビュー必須 items

> [!IMPORTANT]
> **アーキテクチャ変更: カスタムエージェントクラスの採用**
> 標準の `LlmAgent` + 外部ランタイム (`runtime.py`) の構成から、**カスタムエージェントクラス (`FacilitatorAgent`)** にロジックを集約する方針へ変更します。
> これにより、`adk web` や将来の FastAPI サーバー化の際も、共通のルーティングロジック (Sticky Session) が適用されます。

## 変更内容 (Proposed Changes)

### 1. Facilitator Agent (Custom Class)
#### [NEW] [custom_agent.py](file:///home/tyamane/work/facilitator_agent/facilitator/custom_agent.py)
- `google.adk.agents.Agent` を継承。
- `_run_async_impl` を実装し、以下のロジックをカプセル化する:
  1. `Session` から `ThreadState` を復元。
  2. `active_agent` が存在する場合、LLMをバイパスしてツールを直接実行 (Sticky Session)。
  3. 存在しない場合、内部の `LlmAgent` (`self.llm_router`) に委譲。

### 2. Main Entrypoint & Configuration
#### [MODIFY] [agent.py](file:///home/tyamane/work/facilitator_agent/facilitator/agent.py)
- `LlmAgent` のファクトリ関数を `FacilitatorAgent` (カスタム) を返すように変更。
- `root_agent` をカスタムエージェントのインスタンスに差し替え。

### 3. Future FastAPI Considerations
- **SessionManager**: ADK `App` 初期化時に `GcsSessionService` (または Firestore) を注入可能にする。
- **Webhooks/PubSub**: ADKが提供する FastAPI インスタンスに、カスタムルーター (`APIRouter`) をマウントする設計とする。

## 検証計画
### Automated Tests
- `simulation.py` を更新し、`FacilitatorRuntime` (旧ロジック) ではなく、新しい `FacilitatorAgent` クラスを直接呼び出して動作検証を行う。

### Manual Verification
- `adk web .` を起動し、Web UI 上で:
  1. 通常の対話 (LLM経由) ができるか。
  2. Ops Agent への依頼後に、LLMを経ずに会話が継続 (Sticky) するかを確認。
