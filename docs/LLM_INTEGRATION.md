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
| 汎用ゲーム→TUI | `games/base/source.py` `GameSource`(`ShogiSource` の一般化 DataSource) | LoveApp ペインに汎用 `run_game` のイベントを載せる |
| shogi | `shogi/players/llm.py` `LLMShogiPlayer`、`shogi/players/base.make_player` で配線 | `llove play shogi --sente anthropic:… --gote ollama:…` |
| シナリオ | `demo/scenarios/backends.py`(合成全廃・実呼出) | 設定済み全バックエンドに同一プロンプト |
| パレット `:peer` | `app.py` `resolve_peer_command`(config 検証・fail-closed) | LLM peer の状態表示・選択 |
| パレット `:play` | `app.py` `_cmd_play_game`/`_start_game`(builtin 置換・`@peer` 解決) | TUI 内で実 LLM ゲーム対局を起動(shogi/chess) |

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

:play chess                # 選択中の :peer 同士で chess 対局(p1/p2 省略=@peer)
:play chess @peer mock:…   # 片側を選択 peer、もう片側を明示指定(mock は shogi のみ)
:play chess ollama:qwen2.5:14b anthropic:claude-haiku-4-5  # 明示 LLM 対 LLM
:play shogi @peer mock:script  # shogi は mock 相手のオフライン対局も可
```

対局は audit ペインに着手(notation + コメンタリ)が流れ、`game.end` で完結する
(実対局は盤面描画なし=demo 限定。棋譜は `--log` の JSONL に署名付きで残る)。

## TUI で実 LLM 対局を完結(`:play` + `GameSource`)

北極星「TUI 内で実 LLM 対局を完結」の実体。2 系統のゲームスタックがあり、両方が
LoveApp の同じペインに載る:

- **shogi 系**(`llove.shogi`): 独自 `Engine`/`Player(think(engine))`/専用 `run_game`/
  `ShogiSource`。MVP2a の 1 ファイル単位開発の名残で独立している。
- **汎用系**(`llove.games.base`): `GameEngine`/`GamePlayer(think(observation))`/汎用
  `run_game(engine, players)`/`LLMGamePlayer`。chess が `ChessEngine` で実装済み。
  **今回追加した `GameSource`** が汎用 `run_game` を LoveApp の `DataSource` として
  駆動する(`ShogiSource` の一般化)。ゲーム名→エンジンは `games/registry.py`。

`:play` の解決(`app.py`):

- `:play <game> [<p1>] [<p2>]` — p1/p2 を省略すると選択中の `:peer` を相手に据える
  (`@peer` トークンでも明示指定可)。`@peer` は `active_peer_spec` が未選択なら
  **fail-closed でエラー**(`:peer` を先に、と案内)。
- `game == "shogi"` は shogi スタック、それ以外(chess)は `registry.make_engine` +
  `make_game_player` + `GameSource`。未知ゲームは shogi/chess を列挙して拒否。
- 起動失敗(peer 未選択 / 未知ゲーム / 設定不足 / extras 欠如)は全て人間可読な
  `CommandResult(ok=False)` に落とし、**TUI を落とさない**。

CLI(パレットと同じ配線・ヘッドレス検証や CI/バッチ eval 用):

```
llove play chess --white ollama:qwen2.5:14b --black ollama:qwen2.5:14b --max-ply 200
llove play chess --no-tui --white ollama:qwen2.5:7b --black ollama:qwen2.5:7b --max-ply 8
```

**実経路 e2e(honest)**: 実 `ollama` qwen2.5:7b 同士で chess を実走 →
`e2e4 g8f6 d1e2 f6d5 e2g4 …` と **合法手 8 手**を指し、各手を did:key で署名、
FEN を記録、`max_ply` で終局、JSONL 棋譜を出力(2026-07-11 実測)。
LLM のチェス棋力自体は低い(合法手リストで幅を絞っても凡手が多い)が、
「実 LLM が実エンジン上で対局を最後まで完結する」経路は成立している。

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

## 敵対レビューで修正した欠陥(6 レンズ・24 エージェント / 13 CONFIRMED)

「単体テストは緑だが実経路で誤り」型を重点的に狩り、以下を修正済み(全て回帰テスト付き):

- **[HIGH] anthropic temperature**: `temperature` 無条件送信 → Opus 4.7+/Sonnet 5/Fable 5 で
  HTTP 400。該当モデルでは省くよう修正(既定 haiku-4-5 は許容で無害だった)。
- **[HIGH] transport 例外の取りこぼし**: `http.client.HTTPException`(RemoteDisconnected 等)・
  不正 URL の bare `ValueError` が素通り → ループクラッシュ。すべて `LLMBackendError` に
  正規化(`Request()` 構築も try 内へ)。
- **[MED] 着手抽出の王手接尾**: chess で "d1h5+"(合法リストは UCI "d1h5")が一致せず誤 resign。
  装飾(+#!?)を右境界として許容。将棋 USI 成り "7g7f+" は「長い手優先」で正しく選ぶ。
- **[MED] OLLAMA_HOST scheme-less**: `127.0.0.1:11434`(ollama ネイティブ形式)→ 稼働中でも
  到達不能誤報。`http://` を補完。
- **[LOW] fail-closed 完全性**: プロンプト構築を try 内へ + 基底 `LLMError` 捕捉(不正 system_prompt/
  max_tokens で loop がクラッシュしない)。
- **[LOW] 非先頭 system 脱落**: `ChatRequest` が非先頭 system を fail-closed で拒否(provider 間の
  実効プロンプト乖離を防止)。
- **[LOW] llmesh cost 捏造**: 有料コールを $0 / 無料ローカルを課金と誤報 → 課金元不明の peer は
  `None`(N/A)を返す(honest)。
- **[LOW] fence 言語タグ誤認**: `first_move_token` が "```usi" の "usi" を着手と誤認 → フェンス行をスキップ。

## 既知の限界(honest)

- anthropic / llmesh peer は **live 疎通未検証**(ollama qwen2.5:14b のみ実サーバで e2e 確認)。
  anthropic は temperature ゲーティングを claude-api skill(一次情報)+ fake で検証済みだが、
  実 API コールは課金のため未実行(ユーザー go 待ち)。
- 複数合法手が散文で列挙された場合、`extract_move` は最も早い出現を選ぶ(モデルが明示的に
  却下した手を指しうる)。明確な正解挙動が無いヒューリスティックのため現状維持(低頻度)。
- backends シナリオの `available_providers()` は「設定済み」判定で、疎通は実行時。
- shogi プレイヤは fake engine でテスト(python-shogi 非依存)。実対局は
  `llove play shogi` で要実機確認。
- push は human-go(llove は auto-commit hook が動くが、公開反映はユーザー判断)。
