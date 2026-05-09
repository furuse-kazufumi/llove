# Contributing demo scenarios to llove

llove ships a small set of scenarios under `llove/demo/scenarios/`. Each one is
**fully self-contained**, **offline**, and ~100–150 lines of Python. This guide
shows you how to add your own in **about 5 minutes**.

## TL;DR

```bash
cp llove/demo/scenarios/_template.py llove/demo/scenarios/my_thing.py
# edit name / title / description / events()
# then add the import + registry entry in llove/demo/scenarios/__init__.py
llove demo --scenario my_thing
```

That's it. The Textual app + narration pane + tests pick up your scenario
automatically.

---

## Anatomy of a scenario

Every scenario subclasses `DemoScenario` and yields llove `Event`s. The
narration pane is driven by `EventKind.NARRATION` events (use the `narrate()`
helper).

```python
from llove.demo.scenarios.base import DemoScenario, narrate
from llove.events import Event, EventKind


class MyThingScenario(DemoScenario):
    name = "my_thing"
    title = "My thing — 10-word description"
    description = "What feature does this teach? Why should I run it?"
    default_pause = 0.4   # seconds between events

    async def events(self):
        yield narrate("**Hello!** what we're about to show", title="Scenario: my_thing")
        yield Event(
            kind=EventKind.SENSOR,
            source_id="my_source",
            payload={"sensor_id": "s1", "value": 12.3},
        )
        yield narrate("Take-away — what should the user remember?", title="Take-away")
```

### Event kinds you can use

| Kind | What pane shows it | Typical payload |
|---|---|---|
| `SENSOR` | sensor stream pane | `{"sensor_id": ..., "value": float, "quality": "good"}` |
| `SPC_ALARM` | SPC chart pane | `{"sensor_id": ..., "cusum": float, "threshold": float}` |
| `AUDIT` | audit log pane | `{"event": str, ...arbitrary keys}` |
| `LLM_CALL` | audit log pane | `{"tokens": int, "latency_ms": int, "model": ...}` |
| `RAG_HIT` | audit log pane | `{"score": float, "text": str, "doc_id": ...}` |
| `NARRATION` | narration pane (bottom) | use `narrate(text, title=...)` helper |
| `INFO` | audit log pane | free-form |

You can add fields freely — views only look at the keys they care about.

### Lite Markdown in narration

The narration pane supports two Markdown-flavoured shortcuts inside the `text`
argument:

- `**bold**` → bold
- `` `code` `` → inverted background (terminal-friendly highlight)

Anything else is plain text. Other Rich-style `[tag]…[/tag]` markers are
escaped automatically — this is intentional so unsanitised user data can't
bleed Rich tags into the UI.

---

## Step-by-step walkthrough

### 1. Copy the template

```bash
cp llove/demo/scenarios/_template.py llove/demo/scenarios/my_thing.py
```

The template is fully runnable — you can register it as-is and verify the
scaffolding works before you replace the body.

### 2. Edit the class

Open `my_thing.py` and update:

- `name` — short identifier the CLI takes
- `title` — one-liner shown in the menu
- `description` — 1–2 sentences for `llove demo --list`
- `default_pause` — typical 0.3–0.6, lower for noisy fast streams
- `events()` — your own async generator

Keep scenarios **fully offline**. If you want randomness, pass a `seed`
parameter to the `__init__` and use `random.Random(seed)` for determinism.

### 3. Register the scenario

Open `llove/demo/scenarios/__init__.py` and add:

```python
from llove.demo.scenarios.my_thing import MyThingScenario

SCENARIOS = {
    # ... existing entries ...
    "my_thing": MyThingScenario,
}
```

(Order matters — it controls the order in `llove demo --list`.)

### 4. Run it

```bash
pip install -e ".[dev]"
llove demo --scenario my_thing
```

If anything is malformed, Click and Textual give you actionable errors:
import failures, unknown keys, etc.

### 5. Add a test (optional but encouraged)

`tests/test_scenarios.py` parametrises over `SCENARIOS`, so the smoke test
that "every scenario yields events and at least one narration entry" runs
automatically. Add a more specific test if your scenario should emit a
particular kind:

```python
@pytest.mark.asyncio
async def test_my_thing_emits_alarm():
    scenario = get_scenario("my_thing")
    scenario.default_pause = 0.0
    kinds = [ev.kind async for ev in scenario.events()]
    assert EventKind.SPC_ALARM in kinds
```

### 6. Document

Add a row to the table in `REQUIREMENTS.md` (§5.5) describing what your
scenario covers. That table is the single source of truth for "what does
llove demo show?".

---

## Style guide

- **Keep it short.** 100–150 lines is the sweet spot. If you need more, you're
  probably teaching too much in one scenario — split it.
- **Open and close with narrate().** Users need a "what is this" at the start
  and a "so what" at the end.
- **Speak to the operator, not the implementor.** "When the cumulative sum
  crosses threshold, an alarm fires" is better than `cusum.update_chart()`.
- **Show, don't tell.** Yield Events first, narrate the meaning second.
- **Be deterministic for tests.** Accept a `seed` parameter; default to `42`.

## Things to avoid

- **No real network calls.** Mock data or hard-coded payloads only.
- **No filesystem writes.** The scenario should not leave artifacts in the
  user's directory. (`llove export` is the dedicated path for that.)
- **No imports of LLMesh.** Scenarios should run on a clean
  `pip install llove`. If you want to demonstrate a real LLMesh feature, fake
  the data. We supply `llmesh.export.LloveJSONLExporter` on the LLMesh side
  for users who want to feed real data via JSONL.

## Where to ask

- Open an Issue: <https://github.com/furuse-kazufumi/llove/issues>
- PRs welcome — small, focused additions are easiest to merge.

---

Made with **llove**. 💗
