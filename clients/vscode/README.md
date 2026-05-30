# llove VS Code extension (α PoC)

> **日本語のかみ砕いた説明**: これは llove を VS Code 上から使うための拡張機能(クライアント)の説明書です。ローカルで動く llove のエンジンに HTTP で接続し、バージョン情報の表示・依存関係の監査・オフライン状態の確認といった「読み取り専用の観測」機能を IDE に持ち込みます。VS Code マーケットプレイスに依存せず、VSIX ファイルの直接インストールでも導入できる設計です。
>
> → 用語集: [../../docs/GLOSSARY.md](../../docs/GLOSSARY.md)

> Phase-1 skeleton — talks to a locally-running `llove-engine` via HTTP.
> **Marketplace-independent distribution by default.**

## Goal

Bring llove's read-only observation surface (engine info / deps audit /
offline-check / future Research IDE pane) into VS Code so developers in
regulated enterprises (L1-L3 markets) can use the same tooling whether
they're at a terminal or in an IDE.

## Why VSIX-direct distribution?

L1-L3 markets (regulated enterprises, primarily in East Asia and
sanction-affected regions) frequently restrict access to the VS Code
Marketplace by corporate policy or network rules. This extension is
designed from day one to be installed via:

- **VSIX direct**: download `.vsix` from GitHub Release or gitee mirror,
  `code --install-extension llove-vscode-X.Y.Z.vsix`
- **gitee mirror**: synced automatically from GitHub (see
  `.github/workflows/gitee-mirror-sync.yml`)
- **Internal company marketplace**: see `docs/deployment/internal-marketplace.md`
  (Phase 2)
- **Docker image**: bundled with the engine
- **VS Code Marketplace**: optional, not required

Strategy reference: `[[project-marketplace-independent-distribution]]` memory.

## Phase-1 commands

| Command | Description | Endpoint |
|---------|-------------|----------|
| `llove: Show engine info` | Display version / phase / capabilities | `GET /api/v1/engine` |
| `llove: Run dependency audit` | Origin + supply-risk breakdown | `GET /api/v1/audit/deps` |
| `llove: Check offline status` | Verify no outbound calls | `GET /api/v1/audit/offline-check` |

## Configuration

| Setting | Default | Description |
|---------|---------|-------------|
| `llove.engineUrl` | `http://127.0.0.1:8765` | URL of the local engine |
| `llove.autoStartEngine` | `true` | Spawn engine subprocess on activation |

## Phase-2 (planned)

- Webview-based Research IDE pane (5-pane multi-view, see PART5 §2.3)
- LSP integration (memory query, annotation subscribe, HITL Approval Bus)
- Engine subprocess auto-management
- Cursor / Windsurf compatibility (VS Code fork detection)

## Building

```bash
npm install
npm run compile
# Package as VSIX (requires vsce):
# npm install -g @vscode/vsce
# vsce package
```

## Strategy references

- `D:/projects/audit/STRATEGY_EAR_LOCAL_LLM_2026-05-17_PART5_ENGINE.md`
- `D:/projects/audit/STRATEGY_EAR_LOCAL_LLM_2026-05-17_PART4_TABBY.md`
- `[[project-llove-editor-extensions]]` memory
- `[[project-marketplace-independent-distribution]]` memory

## License

MIT — same as llove core.
