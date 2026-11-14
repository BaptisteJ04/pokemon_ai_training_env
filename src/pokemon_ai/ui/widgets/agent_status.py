"""Agent Status: current goal, team, resources and situation.

The goal comes from the optional `GOAL_SELECTED` event, whose payload has a `goal` text.
"""

from __future__ import annotations

from html import escape

from PySide6.QtWidgets import QTextBrowser, QVBoxLayout, QWidget

from pokemon_ai.core.state import Unavailable
from pokemon_ai.game.models.game_state import GameState, PlayerState
from pokemon_ai.game.queries import POTIONS

NO_GOAL = "-"


class AgentStatus(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.text = QTextBrowser()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.text)
        self.goal = NO_GOAL
        self.mode = ""
        self.state: GameState | None = None
        self.render()

    def on_goal_event(self, payload: dict) -> None:
        self.goal = str(payload.get("goal", NO_GOAL))
        self.render()

    def set_mode(self, mode: str) -> None:
        self.mode = mode
        self.render()

    def set_state(self, state: GameState) -> None:
        self.state = state
        self.render()

    def render(self) -> None:
        left = [_section("GOAL", [self.goal])]
        right = []
        if self.state is not None:
            left.append(_section("TEAM", team_lines(self.state)))
            right.append(_section("RESOURCES", resource_lines(self.state)))
            right.append(_section("SITUATION", situation_lines(self.state, self.mode)))
        self.text.setHtml(
            "<table width='100%'><tr>"
            f"<td valign='top' width='55%'>{''.join(left)}</td>"
            f"<td valign='top'>{''.join(right)}</td>"
            "</tr></table>"
        )


def team_lines(state: GameState) -> list[str]:
    if isinstance(state.party, Unavailable):
        return [f"unavailable ({state.party.reason})"]
    if not state.party:
        return ["no Pokemon"]
    lines = []
    for mon in state.party:
        if isinstance(mon, Unavailable):
            lines.append(f"unavailable ({mon.reason})")
            continue
        status = f", {mon.status}" if mon.status else ""
        lines.append(
            f"{mon.nickname.title()}: level {mon.level}, HP {mon.current_hp}/{mon.max_hp}{status}"
        )
    return lines


def resource_lines(state: GameState) -> list[str]:
    inventory = state.inventory
    if isinstance(inventory, Unavailable):
        return [f"unavailable ({inventory.reason})"]
    potions = sum(inventory.items.get(item, 0) for item in POTIONS)
    balls = sum(inventory.pokeballs.values())
    return [
        f"Potions: {potions}",
        f"Poke Balls: {balls}",
        f"Money: {inventory.money:,} P$".replace(",", " "),
        f"Badges: {len(state.progress.badges)}",
    ]


def situation_lines(state: GameState, mode: str) -> list[str]:
    lines = [f"Mode: {mode}"] if mode else []
    lines.append(f"Status: {state.game_status.value}")
    if isinstance(state.player, PlayerState):
        position = state.player.position
        lines.append(f"Map: {state.world.current_map_name} ({position.x}, {position.y})")
    lines.append(f"Frame: {state.frame} ({state.frame / 3600:.1f} min of game)")
    lines.extend(f"Issue: {issue.field}: {issue.reason}" for issue in state.issues)
    return lines


def _section(title: str, lines: list[str]) -> str:
    body = "<br>".join(f"&nbsp;&nbsp;{escape(line)}" for line in lines)
    return f"<p style='margin:0 0 6px 0'><b>{escape(title)}</b><br>{body}</p>"
