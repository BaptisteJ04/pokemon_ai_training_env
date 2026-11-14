# Pokemon Agent Platform

**A training environment and desktop interface for AI agents that play Pokemon Red.**

You write the agent. The platform runs the game, shows what is happening, and gives your agent
the same information a human player would have: the map it has explored, its team, its bag, the
dialog on screen. Nothing more.

![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue)
![License MIT](https://img.shields.io/badge/license-MIT-green)

## Why this project?

Pokemon Red is a good playground for decision-making agents: long-term goals, a big world to
explore, turn-based battles, resources to manage. But connecting an agent to an emulator is a lot
of plumbing. This project does the plumbing:

- **The emulator** (PyBoy) runs the real game from your own ROM.
- **Memory reading** turns raw RAM into a clean Python object: position, team, bag, battle,
  dialogs and menus.
- **A knowledge firewall** hides everything a player could not know: unvisited maps, future story
  flags, the opponent's hidden moves and stats. The agent only learns what it discovers.
- **A Gym-style environment** (`reset`, `observe`, `step`) lets you train in a loop.
- **A desktop interface** lets you watch your agent play, or play yourself with the keyboard.

## About this project

I am a Master's student in AI. I built this environment to experiment with the algorithms we
study in class on a real game, instead of toy problems like :

- **Reinforcement learning**, such as Q-learning.
- **Search algorithms** for navigation, such as A*.
- **Game-tree search** for battles, such as MCTS or Expectiminimax.

The platform only provides the game side: the environment and the interface. The algorithms are
the agents you plug in, so you can compare different approaches on the same game. If you are
a student or a hobbyist with the same idea, feel free to use it for your own experiments.

## Quick start

You need [uv](https://docs.astral.sh/uv/) (it installs Python 3.12 for you) and your own legally
obtained **Pokemon Red (USA, Europe)** ROM.

```bash
git clone <this repository>
cd <this repository>
uv sync
```

Put the ROM in the `ROM/` folder (the expected file name and SHA-1 are in
`config/emulator.yaml`), then:

```bash
uv run pokemon-ai                                  # open the interface and play with the keyboard
uv run pokemon-ai --agent random --autonomous      # watch the built-in random agent
```

### Write your first agent

Save this as `my_agent.py`:

```python
from pokemon_ai.agents.base import Agent
from pokemon_ai.core.actions import Action


class MyAgent(Agent):
    name = "my_agent"

    def act(self, observation):
        state = observation.state  # what a player can see: position, team, bag, map, battle...
        if state.interface.has_text:  # a dialog is open
            return Action.PRESS_A
        return Action.MOVE_DOWN
```

Run it:

```bash
uv run pokemon-ai --agent my_agent.py:MyAgent --autonomous
```

That is all: `act` receives an observation and returns an action. Everything else
(`observe_result`, `save`, `load`...) is optional and meant for agents that learn.

## The interface

```
+---------------------------+---------------------------+
|        Game View          |         Map View          |
|    the emulator screen    |   the map discovered so   |
|                           |   far, with NPCs, items   |
+---------------------------+---------------------------+
|       Agent Status        |     Logs and events       |
|  goal, team, bag, badges, |   what the agent and the  |
|  position, frame          |   game are doing          |
+---------------------------+---------------------------+
```

- The toolbar starts, stops and pauses the game, switches between **manual** and **autonomous**
  mode, changes the speed (x1, x2, x4, unlimited) and the zoom, and saves or loads savestates.
- **Manual mode:** click on the game, then use the arrows, `A`/`X` (A button), `B`/`Z` (B button),
  `Enter` (START) and `Backspace` (SELECT).
- **Autonomous mode:** your agent plays. If it supports navigation, double-click a known tile on
  the map to send it there.
- Savestates saved from the interface go to `assets/states/`.

On Wayland the interface runs through XWayland (`QT_QPA_PLATFORM=xcb`) because the Qt 6.12
Wayland plugin crashes on Ubuntu 22.04. Set `QT_QPA_PLATFORM` to choose another platform.

## Other ways to run an agent

```bash
uv run pokemon-ai --headless --frames 3600 --agent my_agent.py:MyAgent   # no window, 1 minute of game
uv run pokemon-ai --state my_state --agent my_agent.py:MyAgent           # start from a savestate
uv run pokemon-ai --agent my_package.my_module:MyAgent                   # an agent from a package
uv run pokemon-ai --set game.reveal_mode=full_map_on_entry               # change any setting
uv run pokemon-ai --print-config                                         # show the final settings
```

Settings are loaded from `config/default.yaml`, then `config/emulator.yaml`, then the files given
with `--config`, then the `--set section.key=value` options.

You can also skip the `Agent` class and drive the environment yourself, like a Gym environment.
See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for a ready-to-run example.

## What your agent sees

`observation.state` is a `GameState`:

| Field | Content |
|---|---|
| `game_status` | `INTRO`, `OVERWORLD` or `BATTLE` |
| `player` | name, position (map, x, y), facing |
| `party` | team: species, level, HP, moves, PP, status |
| `inventory` | bag, key items and money |
| `world` | current map and the discovered world map (tiles, transitions, NPCs, items) |
| `progress` | badges, story events that already happened, Pokedex |
| `battle` | the battle in progress (the opponent shows only what a player can see) |
| `interface` | on-screen text, menu entries and cursor, whether the player can move |

Any section can be `Unavailable(reason)` when the memory read was inconsistent. The agent answers
with an `Action` (`MOVE_UP`, `MOVE_DOWN`, `MOVE_LEFT`, `MOVE_RIGHT`, `PRESS_A`, `PRESS_B`,
`PRESS_START`, `PRESS_SELECT`, `WAIT`) or with a sequence of button presses for finer control.

## Documentation

| Document | For |
|---|---|
| [`docs/agents.md`](docs/agents.md) | Writing an agent: life cycle, observation, actions, interface hooks |
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | How the platform works, code layout, using the environment directly |
| [`docs/memory_mapping.md`](docs/memory_mapping.md) | The memory addresses and structures that are read |

## Project layout

| Folder | Content |
|---|---|
| `src/pokemon_ai/core` | Configuration, events, interface commands, observation types |
| `src/pokemon_ai/emulator` | PyBoy wrapper, ROM loading, savestates |
| `src/pokemon_ai/game` | Memory reading, game models, knowledge firewall, map building |
| `src/pokemon_ai/env` | `GameEnvironment` (`reset`, `observe`, `step`) and the game session |
| `src/pokemon_ai/agents` | `Agent` base class, registry, `random` and `idle` agents |
| `src/pokemon_ai/runtime` | Session loop and headless mode |
| `src/pokemon_ai/ui` | PySide6 interface |

## Development

```bash
uv run ruff check .     # lint
uv run ruff format .    # format
```

## Credits and legal

- Memory addresses and game data come from the [pret/pokered](https://github.com/pret/pokered)
  disassembly. Check its own terms if you reuse that data.
- The emulation is done by [PyBoy](https://github.com/Baekalfen/PyBoy).
- Pokemon is a trademark of Nintendo, Creatures Inc. and Game Freak. This project is not
  affiliated with or endorsed by them. It does not include or distribute any ROM: you must
  provide your own legally obtained copy.
- The code is released under the [MIT license](LICENSE).
