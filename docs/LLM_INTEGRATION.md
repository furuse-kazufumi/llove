# llove 実 LLM 連携 (`llove.llm`)

llove の合成デモを卒業させ、**実 LLM バックエンド**(anthropic / ollama / llmesh
peer)を games / scenario / palette に配線したモジュール `llove.llm` の設計・
使い方・正直な限界。

> 北極星: llove =「ターミナル上の LLM 連携ランタイム」。カートリッジ(対話
> プログラム)をロードし、ユーザーが選択肢で操り、各プログラムが LLM と連携する。
> 本モジュールはその「LLM 連携(肝)」の実体。詳細 = memory
> `project_llove_llm_runtime_vision`。

## 設計原則

- **ゼロ新規ハード依存**: stdlib `urllib` を `asyncio.to_thread` で包む。anthropic /
  httpx / openai の SDK は使わない(Apache-2.0 コア wheel を汚さない・mypy
  `ignore_missing_imports=false` を壊さない・`llove.mcp.client` の実証済み流儀)。
- **transport DI**: `HttpTransport` Protocol を 1 つ満たせば fake / 本物を差し替え可。
  テストは実 HTTP を踏まない。
- **fail-closed の型分離**: 設定不足 = `LLMConfigError`(そもそも使えない)/
  実行時失敗 = `LLMBackendError`(使えるはずが失敗)。ゲームでは後者を resign に
  落とし、ループを例外で巻き込まない。TUI を凍結させない。
- **honest**: 合成データを出さない。トークン/コスト不明は `None`(N/A 表示)、
  価格表に無いモデルは `None`。ローカル(ollama/llmesh peer)は `0.0` を明示。

## アーキテクチャ

```
llove/llm/
  types.py       ChatMessage / ChatRequest / ChatResponse / Usage + エラー階層
  transport.py   HttpTransport Protocol / UrllibHttpTransport / fake
  client.py      LLMClient ABC / timed_call / estimate_cost_usd + 価格表
  config.py      LLMConfig(env 解決・fail-closed・available_providers)
  parsing.py     extract_move / first_move_token(応答→着手, 境界付き一致)
  factory.py     make_client("provider:model", config, transport?)
  providers/
    anthropic.py AnthropicClient   (POST /v1/messages)
    ollama.py    OllamaClient      (POST /api/chat, ローカル)
    llmesh.py    LlmeshPeerClient  (POST /v1/chat/completions, OpenAI 互換)
```

**配線先(サーフェス)**:

| サーフェス | 実装 | 相手 |
|---|---|---|
| 汎用ゲーム | `games/base/llm_player.py` `LLMGamePlayer` + `make_game_player` | `run_game` に乗る任意 `GameEngine`(chess 等) |
| shogi | `shogi/players/llm.py` `LLMShogiPlayer`、`shogi/players/base.make_player` で配線 | `llove play shogi --sente anthropic:… --gote ollama:…` |
| シナリオ | `demo/scenarios/backends.py`(合成全廃・実呼出) | 設定済み全バックエンドに同一プロンプト |
| パレット | `app.py` `:peer`(未配線→実配線) | LLM peer の状態表示・選択(config 検証) |

## 状態(正直な区別)

`feedback_benchmark_honest_disclosure` に従い誇張しない。

| 項目 | 状態 | 根拠 |
|---|---|---|
| **ollama クライアント**(`complete`) | **works_now(live 検証済み)** | 実 `ollama` qwen2.5:14b に実 HTTP で completion 成功(text/usage/latency 実測、cost 0.0) |
| **汎用 `LLMGamePlayer.think`** | **works_now(live 検証済み)** | 実 LLM が legal_moves から合法手を選択(tic-tac-toe で `b1`)。`run_game` 実ループ e2e も緑 |
| **`make_client`/`make_game_player`/`LLMConfig`** | **works_now(live 検証済み)** | 上記 live スモークで実使用 |
| **anthropic クライアント** | **works_now(契約正確・fake transport 検証)** — live 未実行 | Messages API 契約(x-api-key/anthropic-version/system/stop_sequences/content[].text/usage)を fake で検証。**Opus 4.7+/Sonnet 5/Fable 5 は temperature を送ると 400** なので該当モデルでは temperature を省く(claude-api skill 一次情報で確認)。**実 API は課金のため本セッションでは呼ばず**(キーは存在) |
| **llmesh peer クライアント** | **partial(OpenAI 互換で実装・fake 検証)** — live 未検証 | 稼働中 llmesh を立てて未疎通。エンドポイント形状が将来変わりうる |
| **shogi `LLMShogiPlayer`** | **works_now(fake transport + fake engine 検証)** — live 未実行 | 汎用プレイヤと同じ client/parsing 経路(それは live 検証済み)を共有 |
| **backends シナリオ** | **works_now(fake 検証)/ 実行時は実呼出** | テストは offline(DI)。`llove demo --scenario backends` で実バックエンドを叩く |
| **`:peer` パレット** | **works_now(config レベル)** | 設定検証・選択保存・表示のみ。endpoint 疎通は未確認(設計通り) |

**「設定済み」≠「到達可能」**: `available_providers()` は静的設定(キー/エンドポイント)の
充足を返すだけ。ollama は既定 localhost を持つので常に「設定済み」だが、実際に
起動しているかは呼んで初めて分かる(失敗は `LLMBackendError` で fail-closed)。

## 設定(環境変数)

秘密情報はコードに埋めない。すべて env から読む:

| 変数 | 用途 | 既定 |
|---|---|---|
| `ANTHROPIC_API_KEY` | anthropic 認証(必須) | (無ければ anthropic 使用不可) |
| `ANTHROPIC_BASE_URL` | anthropic ゲートウェイ差替 | `https://api.anthropic.com` |
| `OLLAMA_HOST` / `LLOVE_OLLAMA_URL` | ローカル ollama | `http://localhost:11434` |
| `LLMESH_PEER_URL` / `LLOVE_LLMESH_URL` | llmesh peer(OpenAI 互換) | (無ければ llmesh 使用不可) |
| `LLMESH_PEER_API_KEY` | llmesh peer 認証(任意) | (なし) |
| `LLOVE_LLM_TIMEOUT` / `LLM_TIMEOUT` | HTTP タイムアウト秒 | `60` |

> **タイムアウト注意**: 14B 級ローカルモデルの CPU コールドロードは 60s を超える
> (実測 qwen2.5:14b 初回 57s)。大型ローカルモデルを使うなら
> `LLOVE_LLM_TIMEOUT=300` 等に延ばす。

## 使い方

```python
from llove.llm import LLMConfig, make_client, ChatMessage, ChatRequest

cfg = LLMConfig.from_env()
client = make_client("ollama:qwen2.5:14b", config=cfg)
resp = await client.complete(
    ChatRequest(messages=(ChatMessage("user", "hello"),), model=client.model)
)
print(resp.text, resp.usage, resp.latency_ms, resp.cost_usd)
```

ゲームで実 LLM を相手にする:

```python
from llove.games.base import make_game_player          # 汎用(chess 等)
from llove.shogi.players.base import make_player        # shogi

p = make_game_player("anthropic:claude-haiku-4-5", game="chess", player_id="white")
s = make_player("ollama:qwen2.5:14b", side="sente")     # shogi
```

TUI パレット:

```
:peer                      # 現選択 + 各 provider の設定状態(✓/✗)
:peer ollama:qwen2.5:14b   # 選択(config 検証・fail-closed)
```

## 着手抽出(parsing)

LLM は「7g7f が最善です」のように前置き付きで返す。`extract_move` は合法手リストとの
**境界付きトークン一致**で拾う(部分文字列一致だと "Ne4" 中の "e4" を誤検出するため
前後が着手文字でないことを確認)。同位置なら成り接尾を拾うため長い手を優先
(`7g7f+` > `7g7f`)。合法手が渡されていて一致が無ければ、ゴミ手で違法ストライクを
浪費するより即 resign(fail-closed)。

## テスト

- `test_llm_config.py` / `test_llm_providers.py` / `test_llm_parsing.py` — コア(fake transport)
- `test_llm_game_player.py` / `test_shogi_llm_player.py` — プレイヤ配線 + `run_game` 統合
- `test_llm_backends_scenario.py` — 実呼出シナリオ(DI で offline、偽データ非復活を検証)
- `test_command_palette_peer.py` — `:peer` 配線
- スイート全体は offline(`conftest.py` の `llm_backends_offline` で backends を DI 固定)。
  **どのテストも実ネットワーク/実 API 課金を踏まない。**

## 既知の限界(honest)

- anthropic / llmesh peer は **live 疎通未検証**(ollama のみ実サーバで確認)。
- backends シナリオの `available_providers()` は「設定済み」判定で、疎通は実行時。
- shogi プレイヤは fake engine でテスト(python-shogi 非依存)。実対局は
  `llove play shogi` で要実機確認。
- push は human-go(llove は auto-commit hook が動くが、公開反映はユーザー判断)。
