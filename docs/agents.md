# Writing an agent

The platform separates the **game** (the environment), the **interface** and the **agents**. An
agent only uses the environment interface: it receives an observation, answers with an action, and
then receives the result of that action. Neither the game nor the interface depends on any agent.

## The minimum

```python
from pokemon_ai.agents.base import Agent
from pokemon_ai.core.actions import Action


class MyAgent(Agent):
    name = "my_agent"

    def act(self, observation):
        state = observation.state  # GameState: what a player can see
        return Action.MOVE_UP      # or a sequence of InputStep
```

Run it without changing anything else:

```bash
uv run pokemon-ai --agent path/to/my_agent.py:MyAgent              # interface
uv run pokemon-ai --headless --frames 0 --agent my_package.my_module:MyAgent
```

The `random` and `idle` agents in `src/pokemon_ai/agents/simple.py` are the smallest working
examples.

## Life cycle

| Call | When | Use |
|---|---|---|
| `create(setup)` | once | Build the agent. `setup` has the configuration, the agent options, the event bus, the game rules and the data folder |
| `load(folder)` | after creation | Reload what was learned in previous runs |
| `reset(observation)` | start of an episode | New game or loaded savestate |
| `act(observation)` | every step | **Choose the action** |
| `observe_result(result)` | after every step | Learn from the new observation and the game events |
| `save(folder)` | end of a run | Keep what was learned |

The same cycle is used in the interface (through `runtime/agent_controller.py`) and in headless
runs. You can also skip the `Agent` class and drive `PokemonEnv` yourself (see
[`ARCHITECTURE.md`](ARCHITECTURE.md)).

## What the agent receives

- **`Observation.state`** (`GameState`): game status (intro, overworld, battle), player (map,
  position, facing), team, bag, money, badges, story events that already happened, the world map
  discovered so far (tiles seen, transitions taken, NPCs and items spotted), on-screen text and
  menus, and the battle in progress. Everything goes through the `KnowledgeBase`: the agent only
  sees what a player sees. The opponent only has the moves it has already used, and maps never
  visited are unknown.
- **`StepResult`**: the new observation, the frames played, and the game events (`env/events.py`:
  map discovered, story event, badge, key item, capture, level up, battle, team fainted).
- **The screen image**: `env.screen()`, in step-by-step mode.

Any of `player`, `party`, `inventory` and `battle` can be an `Unavailable(reason)` instead of a
value, when the memory read was inconsistent.

## What the agent can answer

- an **elementary `Action`**: `MOVE_UP`, `MOVE_DOWN`, `MOVE_LEFT`, `MOVE_RIGHT`, `PRESS_A`,
  `PRESS_B`, `PRESS_START`, `PRESS_SELECT` or `WAIT`. A move toward a blocked tile only turns the
  player, which is how you face an NPC or a sign. A step lasts 16 frames and its effect is seen in
  the next observation;
- a **sequence of `InputStep`** for finer control: each item gives a button, how long to hold it
  and how long to wait afterwards (`emulator/controls.py`). For example
  `[tap(Button.UP, hold=4, wait=16)]` plays a whole step.

## Options and saved data

Each agent has a free section `agents.<name>` in the configuration, passed as `setup.options`:

```bash
uv run pokemon-ai --agent random --set agents.random.seed=4
```

Its data folder is `run.data_dir/<name>` (default `data/agents/<name>`): `save` and `load` keep
what it learns there from one run to the next.

## The interface

The interface shows the game, the discovered map, the team and the logs for any agent. Optional
things an agent can do to show more:

- `self.publish_decision(action, reason)` adds a line to the event log;
- publish `GOAL_SELECTED` with a `goal` text to fill the goal line of Agent Status;
- publish `SEARCH_COMPLETED` (`path`, `expanded`, `destination`, `success`) to draw an A* search on
  the Map View;
- list `NAVIGATE` in `capabilities` and handle the `Navigate` and `Explore` commands in `handle`
  to enable the "Explore" button and the double-click on the map.

Events and commands are defined in `core/events.py` and `core/commands.py`.

## Another game

Everything specific to Pokemon Red (memory reading, catalog of maps and events, engine rules)
sits behind `game/adapter.py` (`GameAdapter`). A new game needs its own adapter, and the rest of
the platform does not change since it works with the common `GameState` model. Blue and Yellow
share most of the engine with Red, while Gold and Silver would need a new memory reader.
