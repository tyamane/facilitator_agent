# ファシリテーターエージェント詳細設計書

## 1. 概要
ファシリテーターエージェントは、Slack スレッド内の会話を監視し、状況に応じて適切な「専門家エージェント」にタスクを委譲、その結果を統合してユーザーに応答する「司令塔」として機能します。

## 2. 状態管理 (State Management)
Google ADK の `Session` および `State` 機能を利用して、以下の情報を管理します。

### 2.1 ThreadState (スレッド状態)
`session.state["thread_state"]` に格納される辞書オブジェクト。

```python
class ThreadState(BaseModel):
    status: Literal["OPEN", "IN_PROGRESS", "WAITING_FOR_USER", "RESOLVED"]
    goal: str  # 現在の解決目標
    context_summary: str # これまでの会話の要約
    last_action: str # 直前のエージェントのアクション
    active_agent: Optional[str] = None # 現在対応中の専門家エージェント名 (Stationary / Sticky)
    agent_state: Optional[dict] = None # 専門家エージェントが保持している内部状態 (ADK Sessionに保存)
```

## 3. ルーティングおよびメインロジック

### 3.1 処理フロー
1. **イベント受信**: ユーザーからの Slack メッセージを受信。
2. **状態分析 (Think)**: 会話履歴を読み込み、`ThreadState` を更新する。
   - "現在の状況は？"
   - "ユーザーの意図は？"
   - "次にすべきことは？"
3. **ルーティング (Decide)**: 次のアクションを決定する。
   - **Direct Reply**: 挨拶や単純な応答など、ファシリテーター自身が返す。
   - **Delegate**: 専門家エージェント (Tool) を呼び出す。
     - `call_search_agent(query)`
     - `call_ops_agent(command)`
4. **応答生成 (Act)**:
   - 委譲した場合、Tool からの戻り値 (JSON) を受け取る。
   - **Handoff Check**: 戻り値のタイプが `HANDOFF` の場合、ユーザーへは応答せず、指定された次のエージェントにデータを渡して再度ステップ3 (Delegate) を実行する (Chain of Agents)。
   - 戻り値のタイプが `ANSWER` の場合、JSON 内の `content` と `confidence` を基に、ユーザーへの自然言語応答を生成する。
   - 必要に応じて Slack Block Kit の JSON を生成する。

## 4. プロンプト設計

### 4.1 System Instruction
```text
あなたは、社内 Slack チャンネルの有能なファシリテーター "Sudach" です。
あなたの役割は、ユーザーの問い合わせや依頼を整理し、適切な専門家エージェントに仕事を振り分け、その結果をユーザーに分かりやすく伝えることです。

## 振る舞いのルール
1. **直接回答の制限**: あなた自身は具体的な業務知識やFAQの答えを持っていません。推測で回答せず、必ず専門家エージェントを使用してください。
2. **ルーティング**:
   - 質問・相談と思われる場合 -> `call_search_agent`
   - 作業依頼・設定変更と思われる場合 -> `call_ops_agent`
3. **トーン＆マナー**: 丁寧かつ簡潔に。ビジネスチャットに適した言葉遣いで。
```

### 4.2 状態更新用プロンプト (Internal Reasoning)
※ ADK の `Planner` または Chain-of-Thought を利用して実装。

```text
現在の会話履歴:
{history}

現在の状態: {current_state}

タスク:
1. 最新のユーザー発言の意図を分類してください (QUESTION, REQUEST, CHAT, OTHER)。
2. スレッドの新しいステータスとゴールを更新してください。
3. 次に呼ぶべきツールがあれば選定してください。
```

### 4.3 応答生成用プロンプト
```text
専門家エージェントからの報告:
{tool_output}

タスク:
上記のエージェントからの報告を元に、次のアクションを決定してください。

Type A: ユーザーへの回答 (Result Type: ANSWER)
- 報告が最終的な回答を含んでいる場合、ユーザーへの回答を作成してください。
- 報告が「情報不足」なら、ユーザーに必要な追加情報を質問してください。

Type B: 別エージェントへの引き継ぎ (Result Type: HANDOFF)
- 報告が「次の処理に必要な中間データ」を含んでいる場合、このデータをユーザーには見せず、次の適切なエージェントに渡すためのツール呼び出しを行ってください。
- 例: "Ops Agent" が作成した「実行計画」を "Approval Agent" に渡すなど。

出力形式:
- 回答の場合: 自然言語メッセージ (必要ならBlock Kit)
- 引き継ぎの場合: 次のツール呼び出し
```

## 5. ADK 実装イメージ
`LlmAgent` を使用し、専門家エージェントを `FunctionTool` として登録します。

```python
facilitator = LlmAgent(
    name="facilitator",
    model="gemini-2.5-flash",
    instruction=SYSTEM_INSTRUCTION,
    tools=[call_search_agent, call_ops_agent],
    # ...
)
```
