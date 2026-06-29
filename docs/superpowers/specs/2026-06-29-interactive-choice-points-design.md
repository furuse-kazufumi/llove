# Interactive Choice-Points — 設計 (2026-06-29)

> llove を「台本どおりに流れる固定再生 (fixed playback)」から「**人間が分岐させて AI
> の振る舞いを検証する** ハーネス」へ昇格させる additive 機能。ユーザー指針:
> 「決まった動き以外に、選択肢を与えるような動きができる方が良い」/「AI としての
> 機能検証用のものが llove」。

## 背景 / 問題

現在の llove は完全に **一方向**:

```
source.stream() ──Event──► LoveApp._consume() ──► Views   (app.py:204)
```

`DemoScenario.events()` は台本どおり流れる async generator。ユーザー操作は
pause / reset / quit / command-palette のみで、**シナリオの進路を分岐させる経路が
構造的に存在しない**。これが「決まった動き」の正体。

## ゴール

シナリオが途中で停止してユーザーに選択肢を提示し、**選んだ枝だけが流れる**。
完全 additive(既存シナリオ・既存挙動・公開 PyPI 互換を一切壊さない)。

## アーキテクチャ — asker 注入方式

イベントモデル(`source.stream()`)は不変のまま、**側チャネル**で「質問して選択を
待つ」を実現する。`push_screen_wait` は Textual worker 文脈を要求するため使わず、
`push_screen(screen, callback)` + 自前 `asyncio.Future` で解決する(consume タスクの
task モデルを変えない)。

```
InteractiveScenario.events()
   │  await self.ask(prompt, options)        ← generator は ask 地点で suspend
   ▼
LoveApp.ask_choice(prompt, options)
   │  future = loop.create_future()
   │  push_screen(ChoiceScreen, on_dismiss)  ← モーダル表示
   │  chosen = await future                  ← UI が回り、ユーザーが選ぶと resolve
   │  dispatch(AUDIT: llove.choice ...)       ← 質問と選択を JSONL に記録
   ▼
ChoiceScreen(ModalScreen[str|None]) ── ↑↓ / 数字 / Enter ──► dismiss(option_id)
```

選択は AUDIT イベントとして記録され `--log` の JSONL に残り、`llove tail` で再生可。
(グローバル MCP 規約「監査可能性」。)

## コンポーネント(単一責務)

| file (新規/追記) | 責務 |
|---|---|
| `llove/events.py` 追記 | `EventKind.CHOICE = "choice"` を additive 追加 |
| `llove/term/choice.py` 新規 | 純粋 `ChoiceOption` / `ChoicePrompt` / `render_choice()`、`ChoiceAsker` Protocol、`ChoiceScreen(ModalScreen[str|None])` |
| `llove/demo/scenarios/interactive.py` 新規 | `InteractiveScenario(DemoScenario)` + `async def ask(...)`。**asker 未注入時は既定枝**(headless / CI / test 決定的) |
| `llove/demo/scenarios/incident.py` 新規 | flagship 分岐シナリオ。各枝が AI の別機能を検証(説明=LLM / 観測=SPC / 隔離=Audit) |
| `llove/app.py` 追記 | `async ask_choice(...)` + `on_mount`/`action_reset` で `isinstance(InteractiveScenario)` 時のみ asker 注入 |
| `llove/demo/scenarios/__init__.py` 追記 | `SCENARIOS["incident"]` 登録 |
| `llove/i18n/locales/{en,ja}.toml` 追記 | `[scenario.incident]` + 選択肢 / narration 文字列 |

### 主要インターフェース

```python
@dataclass(frozen=True)
class ChoiceOption:
    id: str
    label: str
    description: str = ""

@dataclass(frozen=True)
class ChoicePrompt:
    prompt: str
    options: tuple[ChoiceOption, ...]
    default_id: str | None = None      # None → options[0].id
    # __post_init__: options 非空 / default_id は options に含まれること (fail-closed)

class ChoiceAsker(Protocol):
    async def __call__(
        self, prompt: str, options: list[ChoiceOption], *, default_id: str | None = None
    ) -> str: ...

class InteractiveScenario(DemoScenario):
    _asker: ChoiceAsker | None = None
    async def ask(self, prompt, options, *, default_id=None) -> str:
        if self._asker is None:
            return default_id or options[0].id     # 決定的フォールバック
        return await self._asker(prompt, options, default_id=default_id)
```

## flagship: incident シナリオ(AI 機能検証ハーネス)

1. intro narrate → 正常センサー → drift → CUSUM alarm + AUDIT
2. **決定 1**「どう対応する?」: `explain` / `observe` / `quarantine`
   - `explain` → `LLM_CALL`(原因仮説)+ AUDIT → **決定 2**「次は?」: `apply_fix` / `rollback` / `escalate`
   - `observe` → さらにセンサー悪化 + 第2 alarm(SPC 継続検証)
   - `quarantine` → AUDIT quarantine + 復旧 narrate
3. takeaway narrate(枝ごとに別)

各枝は「AI の別機能を検証する」: 説明=LLM 生成、観測=SPC 継続、隔離=監査連鎖。
**選択肢提示で複数の AI/LLMesh 機能を検証**できる = 「AI 機能検証用」の体現。

## 安全性 / 非機能

- **additive**: asker 注入は `isinstance` ガード。既存 16 シナリオ・既存テストは無変更で同一挙動。
- **fail-closed / 決定的**: asker 無し → 既定枝。`pytest` / piped / `--list` でも完走。
- **監査可能**: 質問 + 選択を AUDIT 化。
- **fail-closed UI**: `ChoiceScreen` の Escape → `dismiss(None)` → app callback が既定枝へ。

## テスト(TDD・回帰ゼロ)

- `test_choice.py` — 純粋 option/prompt 検証 / render / 既定選択 / Protocol fallback
- `test_interactive_scenario.py` — fake asker(DI)で分岐駆動 / asker 無し既定枝 / 各枝が決定的
- `test_incident_scenario.py` — 枝ごとの期待イベント種 / SCENARIOS 登録 / i18n キー解決 / 既存 smoke(narration ≥1)
- app 統合 — `run_test()` pilot で ChoiceScreen が push され、選択で枝が流れ AUDIT が出る
- 全スイート緑 + ruff + mypy strict 維持。

## スコープ外(YAGNI / 次回に続く)

- `HumanPlayer`(対局で人が着手)= 同 choice プリミティブの上に後載せ
- おせっかい proactive(idle 時に能動提示)= 同上
- 記事ではこの 2 つを「次回に続く」布石にする。
