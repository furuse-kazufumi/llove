/**
 * llove VS Code extension — Phase-1 PoC skeleton.
 *
 * Strategy reference:
 * - D:/projects/audit/STRATEGY_EAR_LOCAL_LLM_2026-05-17_PART5_ENGINE.md (engine protocol)
 * - D:/projects/audit/STRATEGY_EAR_LOCAL_LLM_2026-05-17_PART4_TABBY.md (competitor analysis)
 * - D:/projects/llmesh/docs/market/customer-personas.md (L1 market personas)
 *
 * Design decisions:
 * - Marketplace-independent distribution by default (VSIX direct, gitee
 *   mirror, internal company marketplace). See project_marketplace_
 *   independent_distribution memory.
 * - Talks to the llove engine over HTTP localhost (Pattern B/C from PART5).
 * - LSP integration is Phase 2 once the read-only HTTP surface is stable.
 * - Webview pane (Research IDE F27) is Phase 2.
 *
 * Phase 1 commands:
 * - llove.showEngineInfo    — GET /api/v1/engine
 * - llove.runDepsAudit      — GET /api/v1/audit/deps
 * - llove.checkOffline      — GET /api/v1/audit/offline-check
 *
 * Phase 2 (planned):
 * - Webview Research IDE pane (5-pane multi-view)
 * - LSP-based memory query / annotation subscribe
 * - HITL Approval Bus integration
 */

import * as vscode from 'vscode';
import * as http from 'http';

interface EngineInfo {
    name: string;
    version: string;
    phase: string;
    python: string;
    platform: string;
    capabilities: string[];
}

interface DepsAuditResult {
    metadata: { tool: string; phase: string };
    summary: {
        total: number;
        origin_breakdown: Record<string, number>;
        supply_risk: Record<string, number>;
    };
    dependencies: unknown[];
    note?: string;
}

interface OfflineCheckResult {
    outbound_calls_detected: boolean;
    phase: string;
    note?: string;
}

/**
 * Minimal HTTP GET helper. Deliberately uses node:http rather than fetch
 * to keep dependencies zero (US-dependency surface stays minimal).
 */
function fetchJson<T>(url: string): Promise<T> {
    return new Promise((resolve, reject) => {
        http.get(url, (res) => {
            if (res.statusCode !== 200) {
                reject(new Error(`HTTP ${res.statusCode} from ${url}`));
                return;
            }
            let body = '';
            res.setEncoding('utf-8');
            res.on('data', (chunk: string) => { body += chunk; });
            res.on('end', () => {
                try {
                    resolve(JSON.parse(body) as T);
                } catch (e) {
                    reject(e);
                }
            });
        }).on('error', reject);
    });
}

function engineUrl(): string {
    const config = vscode.workspace.getConfiguration('llove');
    return config.get<string>('engineUrl') ?? 'http://127.0.0.1:8765';
}

export function activate(context: vscode.ExtensionContext): void {
    const showEngineInfo = vscode.commands.registerCommand(
        'llove.showEngineInfo',
        async () => {
            try {
                const info = await fetchJson<EngineInfo>(`${engineUrl()}/api/v1/engine`);
                const message =
                    `llove engine — ${info.version} (phase ${info.phase})\n` +
                    `Python ${info.python} on ${info.platform}\n` +
                    `Capabilities: ${info.capabilities.join(', ')}`;
                await vscode.window.showInformationMessage(message);
            } catch (err) {
                const msg = err instanceof Error ? err.message : String(err);
                await vscode.window.showErrorMessage(`llove engine unreachable: ${msg}`);
            }
        }
    );

    const runDepsAudit = vscode.commands.registerCommand(
        'llove.runDepsAudit',
        async () => {
            try {
                const result = await fetchJson<DepsAuditResult>(
                    `${engineUrl()}/api/v1/audit/deps`
                );
                const summary = result.summary;
                const origin = Object.entries(summary.origin_breakdown)
                    .map(([k, v]) => `${k}=${v}`)
                    .join(' | ');
                const risk = Object.entries(summary.supply_risk)
                    .map(([k, v]) => `${k.toUpperCase()}=${v}`)
                    .join(' | ');
                const message =
                    `deps audit — ${summary.total} packages\n` +
                    `Origin: ${origin || '(none)'}\n` +
                    `Supply risk: ${risk}`;
                await vscode.window.showInformationMessage(message);
            } catch (err) {
                const msg = err instanceof Error ? err.message : String(err);
                await vscode.window.showErrorMessage(`deps audit failed: ${msg}`);
            }
        }
    );

    const checkOffline = vscode.commands.registerCommand(
        'llove.checkOffline',
        async () => {
            try {
                const result = await fetchJson<OfflineCheckResult>(
                    `${engineUrl()}/api/v1/audit/offline-check`
                );
                if (result.outbound_calls_detected) {
                    await vscode.window.showWarningMessage(
                        '⚠ outbound network calls detected; engine is NOT offline-clean'
                    );
                } else {
                    await vscode.window.showInformationMessage(
                        '✓ offline-clean — no outbound calls detected'
                    );
                }
            } catch (err) {
                const msg = err instanceof Error ? err.message : String(err);
                await vscode.window.showErrorMessage(`offline check failed: ${msg}`);
            }
        }
    );

    context.subscriptions.push(showEngineInfo, runDepsAudit, checkOffline);
}

export function deactivate(): void {
    // No-op for Phase 1; Phase 2 will kill the engine subprocess here.
}
