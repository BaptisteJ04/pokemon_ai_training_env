"""What a player knows about the opposing Pokemon (part of the knowledge firewall).

The game memory holds everything: moves, exact HP, DVs and stats of the opponent. A player only
sees the species, the level, the status, the announced stat changes ("ATTACK fell!"), the HP
bar and the moves used in front of them. So the agent receives:
- the moves announced by "Enemy X used Y!" (remembered per species and level: wild Pokemon of
  the same species and level know the same moves);
- HP estimated from the bar (48 pixels);
- stats estimated from the species base stats and the level (average DVs of 8, no stat
  experience), then changed by the announced stages and the status.
"""

from __future__ import annotations

import re
from dataclasses import replace

from pokemon_ai.game.data.game_data import GameRules
from pokemon_ai.game.data.stat_formulas import calc_stat, stage_stat
from pokemon_ai.game.models.battle import BattlePokemon, BattleState
from pokemon_ai.game.models.game_state import GameStatus
from pokemon_ai.game.models.move import MoveState
from pokemon_ai.game.models.pokemon import PokemonStats
from pokemon_ai.game.state.reader import MemoryObservation

HP_BAR_PIXELS = 48
AVERAGE_DV = 8
ENEMY_MOVE = re.compile(r"Enemy (.+?) used (.+?)!")


def hp_bar_pixels(hp: int, max_hp: int) -> int:
    """Length of the displayed HP bar (GetHPBarLength)."""
    if max_hp <= 0:
        return 0
    pixels = hp * HP_BAR_PIXELS // max_hp
    return 1 if pixels == 0 and hp > 0 else pixels


class BattleKnowledge:
    def __init__(self, rules: GameRules) -> None:
        self.rules = rules
        self._moves_by_name = {m.name: m.id for m in rules.moves.values()}
        self.seen: dict[tuple[int, int], set[int]] = {}  # (species, level) -> moves seen
        self.uses: dict[tuple[int, int], int] = {}  # announcements seen
        self._last_text = ""

    def observe(self, observation: MemoryObservation) -> None:
        """Remember the moves the opponent announced on screen."""
        text = " ".join(observation.interface.text.replace("│", " ").replace("─", " ").split())
        if observation.status != GameStatus.BATTLE or text == self._last_text:
            self._last_text = text if observation.status == GameStatus.BATTLE else ""
            return
        self._last_text = text
        battle = observation.battle
        if not isinstance(battle, BattleState) or not isinstance(battle.enemy, BattlePokemon):
            return
        match = ENEMY_MOVE.search(text)
        move_id = self._moves_by_name.get(match.group(2)) if match else None
        if move_id is None:
            return
        key = (battle.enemy.species_id, battle.enemy.level)
        self.seen.setdefault(key, set()).add(move_id)
        self.uses[key] = self.uses.get(key, 0) + 1

    def visible(self, battle: BattleState) -> BattleState:
        enemy = battle.enemy
        if not isinstance(enemy, BattlePokemon):
            return battle
        key = (enemy.species_id, enemy.level)
        return replace(
            battle,
            enemy=self.estimate(enemy),
            enemy_moves_observed=self.uses.get(key, 0),
        )

    def estimate(self, enemy: BattlePokemon) -> BattlePokemon:
        base = self.rules.species[enemy.species_id].base_stats
        level = enemy.level
        max_hp = calc_stat(base.hp, AVERAGE_DV, 0, level, is_hp=True)
        pixels = hp_bar_pixels(enemy.current_hp, enemy.max_hp)
        hp = round(pixels * max_hp / HP_BAR_PIXELS)
        hp = max(1, hp) if enemy.current_hp > 0 else 0
        mods = enemy.modifiers
        values = []
        for base_value, stage in (
            (base.attack, mods.attack),
            (base.defense, mods.defense),
            (base.speed, mods.speed),
            (base.special, mods.special),
        ):
            values.append(stage_stat(calc_stat(base_value, AVERAGE_DV, 0, level), stage))
        attack, defense, speed, special = values
        if enemy.status == "PAR":
            speed = max(1, speed // 4)
        elif enemy.status == "BRN":
            attack = max(1, attack // 2)
        seen = sorted(self.seen.get((enemy.species_id, level), set()))
        infos = [self.rules.moves[move_id] for move_id in seen]
        moves = tuple(MoveState(info.id, info.name, info.pp, info.pp) for info in infos)
        return replace(
            enemy,
            current_hp=hp,
            max_hp=max_hp,
            stats=PokemonStats(max_hp, attack, defense, speed, special),
            moves=moves,
            estimated=True,
        )
