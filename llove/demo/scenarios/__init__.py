"""Interactive demo scenarios that showcase LLMesh features through llove.

Each scenario is a self-contained generator of llove ``Event``s plus narration.
All scenarios run **fully offline** with synthetic data — no network, no real
LLMesh node required. Use ``--seed`` for deterministic playback.
"""

from __future__ import annotations

from llove.demo.scenarios.audit import AuditChainScenario
from llove.demo.scenarios.backends import LLMBackendsScenario
from llove.demo.scenarios.base import DemoScenario, narrate
from llove.demo.scenarios.bench import BenchmarkScenario
from llove.demo.scenarios.chat import ChatStreamScenario
from llove.demo.scenarios.coin_toss import CoinTossScenario
from llove.demo.scenarios.cost import CostBudgetScenario
from llove.demo.scenarios.drift import ModelDriftScenario
from llove.demo.scenarios.firewall import FirewallScenario
from llove.demo.scenarios.incident import IncidentScenario
from llove.demo.scenarios.interactive import InteractiveScenario
from llove.demo.scenarios.mcp_call import MCPCallScenario
from llove.demo.scenarios.mindmap import MindmapScenario
from llove.demo.scenarios.multimodal import MultimodalSPCScenario
from llove.demo.scenarios.pointcloud import PointCloudScenario
from llove.demo.scenarios.rag import RAGStoresScenario
from llove.demo.scenarios.reliability import ReliabilityScenario
from llove.demo.scenarios.scada import SCADAScenario
from llove.demo.scenarios.shogi import ShogiScenario
from llove.demo.scenarios.triage import TriageScenario
from llove.demo.scenarios.vision import VisionScenario

# Registry — order matters for the menu display.
SCENARIOS: dict[str, type[DemoScenario]] = {
    "firewall": FirewallScenario,
    "scada": SCADAScenario,
    "incident": IncidentScenario,
    "triage": TriageScenario,
    "multimodal": MultimodalSPCScenario,
    "rag": RAGStoresScenario,
    "backends": LLMBackendsScenario,
    "audit": AuditChainScenario,
    "reliability": ReliabilityScenario,
    "cost": CostBudgetScenario,
    "chat": ChatStreamScenario,
    "bench": BenchmarkScenario,
    "drift": ModelDriftScenario,
    "mcp_call": MCPCallScenario,
    "vision": VisionScenario,
    "pointcloud": PointCloudScenario,
    "mindmap": MindmapScenario,
    "coin_toss": CoinTossScenario,
    "shogi": ShogiScenario,
}


def get_scenario(name: str) -> DemoScenario:
    """Look up and instantiate a scenario by short name."""
    if name not in SCENARIOS:
        valid = ", ".join(SCENARIOS)
        raise ValueError(f"unknown scenario {name!r}; choose from: {valid}")
    return SCENARIOS[name]()


__all__ = [
    "SCENARIOS",
    "AuditChainScenario",
    "BenchmarkScenario",
    "ChatStreamScenario",
    "CoinTossScenario",
    "CostBudgetScenario",
    "DemoScenario",
    "FirewallScenario",
    "IncidentScenario",
    "InteractiveScenario",
    "LLMBackendsScenario",
    "MCPCallScenario",
    "MindmapScenario",
    "ModelDriftScenario",
    "MultimodalSPCScenario",
    "PointCloudScenario",
    "RAGStoresScenario",
    "ReliabilityScenario",
    "SCADAScenario",
    "ShogiScenario",
    "TriageScenario",
    "VisionScenario",
    "get_scenario",
    "narrate",
]
