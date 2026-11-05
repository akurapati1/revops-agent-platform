"""Agent registry and DAG definitions."""
from app.agents.base import Agent
from app.agents.impl import Enricher, Personalizer, ReplyTriage, Researcher, Sequencer

_AGENTS: dict[str, Agent] = {a.name: a for a in (Researcher(), Enricher(), Personalizer(), Sequencer(), ReplyTriage())}

OUTREACH_DAG: tuple[str, ...] = ("researcher", "enricher", "personalizer", "sequencer")
TRIAGE_DAG: tuple[str, ...] = ("triage",)
DAGS = {"outreach": OUTREACH_DAG, "triage": TRIAGE_DAG}


def get_agent(name: str) -> Agent:
    return _AGENTS[name]


def list_agents() -> list[Agent]:
    return list(_AGENTS.values())


def topo_order(names: tuple[str, ...]) -> list[list[str]]:
    """Group agents into dependency layers (Kahn). Raises on cycles / missing deps."""
    remaining = {n: set(_AGENTS[n].depends_on) for n in names}
    for deps in remaining.values():
        if not deps <= set(names):
            raise ValueError(f"unknown dependency in DAG: {deps - set(names)}")
    layers: list[list[str]] = []
    done: set[str] = set()
    while remaining:
        ready = sorted(n for n, d in remaining.items() if d <= done)
        if not ready:
            raise ValueError("cycle in agent DAG")
        layers.append(ready)
        done.update(ready)
        for n in ready:
            del remaining[n]
    return layers
