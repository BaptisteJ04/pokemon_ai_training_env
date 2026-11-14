# Architecture

This repository is a platform that lets **autonomous agents play Pokemon Red (USA)** on an
emulated Game Boy. The game state is read from the emulator memory, but it is given to the agent
through a *knowledge firewall*: an agent only sees what a human player could see (maps already
visited, enemy moves already used, events that already happened). Everything else in RAM (future
event flags, unvisited maps, the opponent's hidden moves and stats) is filtered out.

It contains the training environment and the interface only. Agent implementations live outside
of it. You connect yours through the `Agent` class (see [`agents.md`](agents.md)).

| Part | What it is |
|---|---|
| **Environment** | PyBoy emulator, memory reading, `GameEnvironment` (`reset`, `observe`, `step`) |
| **Interface** | PySide6 desktop window (game, map, agent status, logs) |
| **Agents** | Anything that subclasses `Agent`. Only `random` and `idle` ship here |

## Data flow

```
PyBoy emulator --> WRAM snapshot --> parsers --> KnowledgeBase --> GameState --> Observation
      ^                                         (firewall)                          |
      |                                                                             v
 button presses <-- Action / InputStep sequence <------------------------------- Agent.act()
```

1. The emulator runs the ROM. A single 8 KiB snapshot of WRAM is read after each step.
2. Parsers turn raw bytes into typed models. An inconsistent reading is **never** passed on: the
   section becomes `Unavailable(reason)`.
3. The `KnowledgeBase` merges the observation into what the agent has *discovered so far*.
4. The result is an immutable `GameState`, wrapped in an `Observation`.
5. The agent answers with an `Action` (or a sequence of `InputStep`). The environment plays it
   frame by frame and returns a `StepResult` (new observation and game events).

## Code layout

```
src/pokemon_ai/
├── core/       Config (pydantic), event bus, events, interface commands, Observation, Unavailable
├── emulator/   PyBoy wrapper, buttons and InputStep, ROM loading and SHA-1 check, savestates
├── game/       Everything specific to Pokemon Red
│   ├── state/      Memory reading: addresses, snapshot, parsers, screen text
│   ├── models/     GameState, PokemonState, BattleState, InventoryState, WorldMap...
│   ├── data/       Rules (species, moves, items), catalog, charmap, movement rules, stat formulas
│   ├── knowledge.py, battle_knowledge.py   the knowledge firewall
│   ├── cartography.py   builds the discovered map from observations
│   └── adapter.py       the only game-specific entry point (to support other games)
├── env/        GameEnvironment, PokemonEnv, GameSession, actions, game events
├── agents/     Agent base class, registry, reference agents (random, idle)
├── runtime/    Session loop, agent adapter, headless run, savestates
├── ui/         PySide6 interface (main window, widgets, controllers)
└── main.py     Command-line entry point (`pokemon-ai`)

assets/data/    Rules extracted from the ROM (rules.json, overworld.json, catalog.json)
assets/states/  Savestates
config/         default.yaml and emulator.yaml
docs/           This file, the agent guide, the memory map
```

## Main pieces

**Emulator** (`emulator/`): `GameEmulator` is the interface, `PyBoyEmulator` the only
implementation. The ROM is checked against its expected SHA-1 (`config/emulator.yaml`) and is
never committed. Savestates are `<name>.state` plus a `<name>.json` file with the ROM SHA-1.

**Memory reading** (`game/state/`): `memory_addresses.py` is the single source of truth for
addresses (see [`memory_mapping.md`](memory_mapping.md)). One parser per section: player, team,
bag, battle, map, interface (text and menus read from the screen tiles).

**Knowledge firewall** (`game/knowledge.py`): keeps the maps visited, the events seen, the
discovered world map (tiles, transitions, points of interest) and what a player sees of the
opponent in battle. The agent cannot list events that did not happen.

**Environment** (`env/`): the whole contract between a game and an agent.

| Method | Purpose |
|---|---|
| `reset(start, knowledge)` | Restart from a savestate (blank or given knowledge) |
| `observe()` | Current `Observation[GameState]` |
| `step(action)` | Play an `Action` or `InputStep` sequence and return a `StepResult` |
| `screen()` | Screen image (numpy array) |
| `save_state()` / `load_state()` | Savestates (knowledge is not part of them) |

**Runtime** (`runtime/`): `SessionLoop` handles commands, frame pacing and the manual and
autonomous modes. `AgentController` adapts an `Agent` to the loop, so the agent sees the same
observations as in step-by-step mode. `run_headless` plays without the interface.

**Interface** (`ui/`): the window is a 2x2 grid. The agent runs in its own thread and sends the
interface immutable copies (screen image, state, world map). The interface sends commands through
a queue. It never contains decision logic.

| Area | Shows |
|---|---|
| **Game View** (top left) | The emulator screen: what a human would see |
| **Map View** (top right) | The discovered map: tiles, player, NPCs and items, transitions. Agents can also publish an A* search to draw (explored cells in blue, path in red, travelled path in green). Double-click a known tile to send a compatible agent there |
| **Agent Status** (bottom left) | Goal, team, bag, badges, position and frame |
| **Logs and events** (bottom right) | Event table with a filter by type, and the log messages |

The toolbar starts, stops and pauses, picks the mode (manual or autonomous), the speed (x1, x2, x4,
unlimited), the zoom, "Explore", and saves or loads a savestate. In manual mode, click on the game
and use the arrows, A/X, B/Z, Enter (START) and Backspace (SELECT).

## Running it

```bash
uv sync                                          # install (needs uv; Python 3.12 is installed for you)
uv run pokemon-ai                                # interface, manual mode
uv run pokemon-ai --agent random --autonomous    # an agent plays
uv run pokemon-ai --agent path/to/my_agent.py:MyAgent
uv run pokemon-ai --headless --frames 3600       # no interface
uv run pokemon-ai --print-config                 # resolved configuration
```

Put the ROM in `ROM/` (path and SHA-1 in `config/emulator.yaml`). Configuration is loaded from
`config/default.yaml`, then `config/emulator.yaml`, then the files given with `--config`, then
`--set section.key=value`.

| Key | Meaning |
|---|---|
| `run.agent` | Agent to run (also `--agent`) |
| `run.data_dir` | Where agents keep what they learn |
| `game.reveal_mode` | `viewport` (only what is on screen) or `full_map_on_entry` |
| `emulator.speed`, `emulator.scale`, `emulator.sound` | Emulator behaviour |
| `emulator.savestate_dir` | Folder of the savestates |
| `ui.*` | Refresh rates of the interface |

## Using the environment directly (Gym-style)

```python
from pokemon_ai.core.actions import Action
from pokemon_ai.core.config import load_config
from pokemon_ai.emulator.pyboy_adapter import PyBoyEmulator
from pokemon_ai.emulator.rom import load_rom
from pokemon_ai.env.pokemon import PokemonEnv
from pokemon_ai.runtime.savestates import savestate_manager

config = load_config()
rom = load_rom(config.emulator.rom_path, config.emulator.rom_sha1)
start = savestate_manager(config).load("my_state", rom_sha1=rom.sha1)

with PyBoyEmulator(rom, headless=True) as emulator:
    env = PokemonEnv(emulator, rom_sha1=rom.sha1)
    observation = env.reset(start)
    for _ in range(100):
        result = env.step(Action.MOVE_DOWN)
        print(result.state.player, result.events)
```

`my_state` is a savestate in `assets/states/`: save one from the interface first.

## Another game

Everything specific to Pokemon Red sits behind `game/adapter.py`. See [`agents.md`](agents.md).
