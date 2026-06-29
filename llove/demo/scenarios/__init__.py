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
from llove.demo.scenarios.blackjack import BlackjackScenario
from llove.demo.scenarios.chat import ChatStreamScenario
from llove.demo.scenarios.coin_toss import CoinTossScenario
from llove.demo.scenarios.connect_four import ConnectFourScenario
from llove.demo.scenarios.cost import CostBudgetScenario
from llove.demo.scenarios.draw_poker import DrawPokerScenario
from llove.demo.scenarios.drift import ModelDriftScenario
from llove.demo.scenarios.firewall import FirewallScenario
from llove.demo.scenarios.highlow import HighLowScenario
from llove.demo.scenarios.incident import IncidentScenario
from llove.demo.scenarios.interactive import InteractiveScenario
from llove.demo.scenarios.mancala import MancalaScenario
from llove.demo.scenarios.mcp_call import MCPCallScenario
from llove.demo.scenarios.memory import MemoryScenario
from llove.demo.scenarios.mindmap import MindmapScenario
from llove.demo.scenarios.multimodal import MultimodalSPCScenario
from llove.demo.scenarios.nim import NimScenario
from llove.demo.scenarios.pointcloud import PointCloudScenario
from llove.demo.scenarios.rag import RAGStoresScenario
from llove.demo.scenarios.reliability import ReliabilityScenario
from llove.demo.scenarios.reversi import ReversiScenario
from llove.demo.scenarios.scada import SCADAScenario
from llove.demo.scenarios.shogi import ShogiScenario
from llove.demo.scenarios.snap import SnapScenario
from llove.demo.scenarios.tictactoe import TicTacToeScenario
from llove.demo.scenarios.triage import TriageScenario
from llove.demo.scenarios.twentyone import TwentyOneScenario
from llove.demo.scenarios.vision import VisionScenario
from llove.demo.scenarios.war import WarScenario

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
    "blackjack": BlackjackScenario,
    "war": WarScenario,
    "highlow": HighLowScenario,
    "draw_poker": DrawPokerScenario,
    "memory": MemoryScenario,
    "snap": SnapScenario,
    "tictactoe": TicTacToeScenario,
    "connect_four": ConnectFourScenario,
    "nim": NimScenario,
    "mancala": MancalaScenario,
    "twentyone": TwentyOneScenario,
    "reversi": ReversiScenario,
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
    "BlackjackScenario",
    "ChatStreamScenario",
    "CoinTossScenario",
    "ConnectFourScenario",
    "CostBudgetScenario",
    "DemoScenario",
    "DrawPokerScenario",
    "FirewallScenario",
    "HighLowScenario",
    "IncidentScenario",
    "InteractiveScenario",
    "LLMBackendsScenario",
    "MCPCallScenario",
    "MancalaScenario",
    "MemoryScenario",
    "MindmapScenario",
    "ModelDriftScenario",
    "MultimodalSPCScenario",
    "NimScenario",
    "PointCloudScenario",
    "RAGStoresScenario",
    "ReliabilityScenario",
    "ReversiScenario",
    "SCADAScenario",
    "ShogiScenario",
    "SnapScenario",
    "TicTacToeScenario",
    "TriageScenario",
    "TwentyOneScenario",
    "VisionScenario",
    "WarScenario",
    "get_scenario",
    "narrate",
]
