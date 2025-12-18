# 専門家エージェント機能設計書

## 1. 概要
専門家エージェント (Specialist Agents) は、特定のドメイン知識やツール操作能力を持つ、より小規模なエージェントです。ファシリテーターから呼び出され、特定のタスクを実行し、結果を構造化データで返します。基本的にステートレスとして振る舞いますが、タスク遂行に必要な一時的なコンテキストは引数として受け取ります。

## 2. 基本構造
Google ADK の `LlmAgent` をベースに実装しますが、外部のツールとして見えるように `FunctionTool` ラッパーを介してファシリテーターに公開されます。

```python
# 概念図
class SpecialistAgent:
    def process(self, query: str, context: dict) -> AgentResponse:
        # 1. コンテキストの理解
        # 2. ツールの実行 (必要なら)
        # 3. 結果の生成 (ANSWER or HANDOFF)
        return response
```

### 2.1 データモデル (AgentResponse)
```python
class AgentResponse(BaseModel):
    agent_name: str
    result_type: Literal["ANSWER", "HANDOFF", "ERROR"]
    content: str | dict  # ユーザー向けの回答、または次のエージェントへの引き継ぎデータ
    confidence: float
    next_agent_hint: Optional[str] = None # HANDOFFの場合、推奨する次のエージェント名
```

## 3. 基本プロンプト設計

### 3.1 System Instruction テンプレート
```text
あなたは {AGENT_NAME} です。
あなたの役割は、ユーザーからの {DOMAIN} に関する問い合わせに対し、ツールを使用して正確な情報を提供することです。

## 制約事項
- あなたはユーザーと直接会話しているわけではありません。ファシリテーターへの報告書を作成していると考えてください。
- 自身の担当範囲外のことは「範囲外」として回答するか、適切なエージェントへの引き継ぎを提案してください。

## 出力フォーマット
必ず以下のJSONスキーマに従って出力してください。
{json_schema}
```

### 3.2 Handoff (引き継ぎ) の判断ロジック
プロンプト内で、「自分の処理は終わったが、タスク完了には別のプロセスが必要」と判断した場合、`result_type: HANDOFF` を選択します。

**例: Ops Agent の場合**
```text
もしユーザーが「設定変更」を依頼してきた場合:
1. 現在の権限や設定を確認する (Read Tool)。
2. 変更のための「実行計画 (Execution Plan)」を作成する。
3. **重要**: あなた自身には承認権限がありません。作成した実行計画を `result_type: HANDOFF` で返し、承認担当エージェント (Approval Agent) への転送を要求してください。
```

## 4. ステートフルエージェント実装ガイドライン

単発の回答ではなく、ユーザーとの複数回のやり取り（パラメータ収集、確認、承認など）が必要なエージェントの実装パターンです。

### 4.1 基本コンセプト: ADK SessionManagerへの依存
Google ADKの構造上、エージェントやツールのインスタンスはHTTPリクエスト間で再生成されるため、メモリ上の変数は保持されません。
状態を永続化するために、**ADKの `Session` 機能 (`session.state`)** を利用します。

**「ファシリテーターが内部状態を預かる」仕組み:**
1. 専門家エージェント (Function Tool) はステートレスな関数として実行されます。
2. 実行結果 (`AgentResponse`) の中に `agent_state` (次のステップに必要な状態データ) を含めて返します。
3. 呼び出し元であるファシリテーターは、この `agent_state` を受け取り、**自身の `session.state` (ThreadState内)** に保存します（これが「預かる」の意味です）。
4. ユーザーからの次のメッセージが届くと、ファシリテーターは `session.state` から `agent_state` を読み出し、専門家エージェントの引数として渡します。

これにより、ステートレスなツール実装でありながら、ユーザーからは「文脈を覚えているエージェント」として振る舞うことが可能になります。

### 4.2 インターフェース定義 (改訂版)

```python
class SpecialistAgent:
    def process(self, query: str, agent_state: dict | None, context: dict) -> AgentResponse:
        """
        Args:
            query: ユーザーの最新の入力
            agent_state: 前回のこのエージェントの実行終了時の状態 (初回は None)
            context: スレッド全体の共通コンテキスト
        """
        # 1. 状態の復元 (Pydanticモデルへの変換など)
        state = MyAgentState(**agent_state) if agent_state else MyAgentState()
        
        # 2. ロジック実行 (状態更新)
        new_state, response_content, result_type = self.execute_logic(query, state)
        
        # 3. レスポンス生成
        return AgentResponse(
            agent_name="OpsAgent",
            result_type=result_type, # ANSWER, HANDOFF, or CONTINUE (継続中)
            content=response_content,
            agent_state=new_state.dict() # 更新された状態を返す
        )
```

この `agent_state` は、ファシリテーター側の `ThreadState` 内に保存され、**次回同じエージェントが指名された場合** に再利用されます。

### 4.3 実装例: 業務対応エージェント (Ops Agent)

**要件**:
1. パラメータ収集 (Plan)
2. 実行計画作成 (Draft)
3. ユーザー承認 (Approval)
4. 実行エージェントへ引き継ぎ (Handoff)
5. 中断/変更対応

#### 状態モデル (OpsAgentState)
```python
class OpsAgentState(BaseModel):
    phase: Literal["COLLECTING", "CONFIRMING", "COMPLETED"] = "COLLECTING"
    task_type: Optional[str] = None # 'account_create', 'permission_grant' など
    collected_params: dict = {}
    missing_params: list[str] = []
    execution_plan: Optional[str] = None
```

#### プロンプト戦略 (ReActループ)

System Instruction に以下の状態遷移ルールを記述します。

```text
あなたは業務対応エージェントです。以下のフェーズで動作します。

Current Phase: {phase}

1. COLLECTING:
   - ユーザーの依頼から `task_type` と `collected_params` を抽出してください。
   - 必須パラメータが不足している場合、ユーザーに質問してください (Result: CONTINUE)。
   - 変更依頼があった場合、パラメータを上書きしてください。
   - 全て揃ったら「実行計画」を作成し、ユーザーに承認を求めてください (Phase -> CONFIRMING, Result: CONTINUE)。

2. CONFIRMING:
   - ユーザーが「承認/YES」した場合、承認済み計画を実行エージェントに渡してください (Result: HANDOFF)。
   - ユーザーが「修正/NO」または変更を指示した場合、パラメータを更新し実行計画を再作成してください (Phase -> COLLECTING または CONFIRMING)。
   - ユーザーが「中止/Cancel」した場合、処理を終了してください (Result: ANSWER "中止しました", Phase -> COMPLETED)。

3. 共通ルール:
   - ユーザーへの回答は `content` フィールドに入れてください。
```

## 5. ファシリテーターとの連携フロー (詳細)

ステートフルなやり取りを実現するため、ファシリテーターにもロジック追加が必要です。

1. **Facilitator (Router)**:
   - `ThreadState.active_agent` が存在する場合、ルーティング（分類）を行わずに **即座にそのエージェントを呼び出す** (Sticky Session)。
   - ただし、ユーザー入力が明らかに文脈を変えるもの（「話を変えて」「キャンセル」）などの場合は、ルーティングを再実行する。

2. **呼び出し**:
   - `active_agent` の名前と、保存されている `agent_state` を取り出し、`process(query, agent_state, ...)` をコール。

3. **戻り値処理**:
   - `result_type == CONTINUE`:
      - ユーザーへ `content` を返信。
      - `ThreadState.active_agent` を維持。
      - `ThreadState.agent_state` を更新。
   - `result_type == ANSWER` (完了):
      - ユーザーへ `content` を返信。
      - `ThreadState.active_agent` をクリア。
      - `ThreadState.agent_state` をクリア。
   - `result_type == HANDOFF`:
      - 次のエージェントへデータを渡す（前述の通り）。
      - `ThreadState.active_agent` をクリア（または次のエージェントに切り替え）。

この仕組みにより、Ops Agent は会話の履歴を一貫して保持しているように振る舞うことができます。
