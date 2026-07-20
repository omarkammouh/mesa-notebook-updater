# Mesa version history — the migration ladder

**This file is the skill's source of truth on what is current.** It records, in
release order, everything Mesa changed: added, deprecated, removed. Place a
model on this ladder (via the scanner + era estimate), then apply every rung
between its era and the target. When Mesa releases a new version, append its
section here and mirror any new deprecations/removals into `api-registry.json`
(see "Maintaining the version history" in SKILL.md).

**Last updated:** 2026-07-16 · **covers through Mesa 3.5.1** (+ Mesa 4.0.0a0 preview)

> **Every release, machine-readable:** [references/version-catalog.json](version-catalog.json)
> lists all 88 PyPI releases (one of which, `0.7.8`, has no installable files)
> plus the GitHub-only `2.0.0` changelog ghost — 89 records in all — with date,
> `requires_python`, the curated `python_pin` and `install`
> string, and the modernization `band`. The scanner validates any `--target`
> against it; the runner reads `python_pin`/`install` from it. This narrative file
> is the deep-dive; the catalog is the index. Regenerate it with
> `scripts/update_catalog.py` when Mesa ships a new version.

**Targets other than latest:** this ladder reads in both directions. Migrating to
a *mid* target (say 3.3.0) applies every rung **up to and including** that target
and **no rung beyond it** — at 3.3 portrayal dicts and `iterations=` are current,
while `run_for`/`to_list`/`rng=` do not exist yet. Migrating *down* (3.5 code to a
3.3 lab machine) is the same ladder read right-to-left; see §15c.

## Table of contents

- §0 Current state, install commands, version timeline table
- §1 Python version requirements
- §2 `Model.__init__` (super().__init__, seed/rng, reserved names, initialize_data_collector, mesa.flat)
- §3 `Agent.__init__` (unique_id auto-assignment, create_agents)
- §4 Schedulers → AgentSet (replacement table, AgentSet API)
- §5 Step counter and simulation time
- §6 Spaces: legacy `mesa.space` vs `mesa.discrete_space` (mapping table §6.3, ContinuousSpace §6.4, PropertyLayer §6.5)
- §7 DataCollector (agenttype_reporters)
- §8 `batch_run` (iterations → rng)
- §9 Visualization: ModularServer → SolaraViz → SpaceRenderer (Jupyter usage §9.5)
- §10 Randomness (`self.random`, `self.rng`, seed → rng)
- §11 Mesa 3.5 event scheduling (`run_for`, `schedule_recurring`, new `mesa.time`)
- §12 **Deprecation/removal timeline cheat sheet** ← quickest overview
- §13 **Common runtime errors with exact messages** ← when execution fails
- §14 Minimal complete before/after example
- §15 Migration checklist 2.x → latest
- §15b **Current-best idioms — the TARGET-CONDITIONED modernization checklist** (band table) ← applied after the ladder fixes
- §15c **Downgrades — reading the ladder right-to-left** ← when target is older than the code
- §16 Sources

---

**Research method:** Official migration guide, `HISTORY.md` changelog and release notes from the Mesa repo (now `github.com/mesa/mesa`, formerly `projectmesa/mesa`), PyPI metadata, exact source signatures from the `v3.5.1` git tag, the official tutorial notebooks, plus **empirical verification** — Mesa 3.5.1 was installed in a venv (Python 3.14) and all "NEW" code examples and error messages below were executed and confirmed.

---

## 0. Current state of Mesa (as of July 2026)

| Item | Value | Source |
|---|---|---|
| **Latest stable release** | **Mesa 3.5.1** (released 2026-03-15) | https://pypi.org/project/Mesa/ |
| Latest pre-release | Mesa 4.0.0a0 (2026-03-14) — alpha, breaking | https://github.com/mesa/mesa/releases |
| Python requirement (3.5.x) | **Python >= 3.12** (3.12 / 3.13 / 3.14 tested) | PyPI classifiers, `pyproject.toml` @ v3.5.1 |
| GitHub org | Moved `projectmesa` → **`mesa`** in Mesa 3.4.0 (old URLs redirect) | HISTORY.md 3.4.0 |
| Docs | https://mesa.readthedocs.io/stable/ (= 3.5.1); `/latest/` now tracks the 4.0 dev branch | readthedocs |
| Migration guide | https://mesa.readthedocs.io/latest/migration_guide.html (source: `docs/migration_guide.md` in the repo) | |

### Install (verified from `pyproject.toml` @ v3.5.1)

```bash
pip install -U mesa                  # core only (numpy, pandas, tqdm, scipy)
pip install -U "mesa[rec]"           # RECOMMENDED bundle = mesa[network,viz]
pip install -U "mesa[viz]"           # matplotlib, solara, altair, starlette<1.0
pip install -U "mesa[network]"       # networkx
pip install -U "mesa[all]"           # network,viz,dev,examples,docs
```

Extras defined in `pyproject.toml` @ v3.5.1:
```toml
rec = ["mesa[network,viz]"]
all = ["mesa[network,viz,dev,examples,docs]"]
network = ["networkx"]
viz = ["matplotlib", "solara", "altair", "starlette<1.0"]
```

> **Gotcha (verified empirically on 3.5.1):** a bare `pip install mesa` produces a package whose top-level `import mesa` **fails** with `ModuleNotFoundError: No module named 'networkx'` (because `mesa/__init__.py` imports `mesa.discrete_space`, whose `network.py` imports networkx unconditionally). **Always install at least `"mesa[rec]"`** — this is also the officially recommended install. Visualization additionally needs the `viz` extra (`solara`, `matplotlib`, `altair`).

### Version timeline (from `HISTORY.md`, dates verified)

| Version | Date | Python | Key changes |
|---|---|---|---|
| 2.3.x (last 2.x) | 2024-07 | >=3.9 | Deprecation warnings for schedulers etc.; experimental SolaraViz/JupyterViz |
| **3.0.0** | 2024-11-09 | >=3.10 | Mandatory `super().__init__()`; auto `unique_id`; AgentSet replaces schedulers (`mesa.time` deprecated); SolaraViz (experimental); `agenttype_reporters`; `mesa.flat` removed |
| **3.1.0** | 2024-12-04 | **>=3.11** | **`mesa.time` (schedulers) REMOVED**; other deprecated 2.x functionality removed; `Agent.create_agents()`; experimental cell-space property layers; logging |
| 3.1.1–3.1.5 | 2024-12 → 2025-03 | >=3.11 | Bugfixes; experimental new ContinuousSpace (3.1.3); viz fixes |
| **3.2.0** | 2025-05-08 | >=3.11 | **Cell space stabilized as `mesa.discrete_space`**; PropertyLayer stabilized; SolaraViz command console, dark mode, async updates; experimental meta-agents; JOSS "Mesa 3" paper |
| **3.3.0** | 2025-09-06 | >=3.11 | **New visualization API**: `SpaceRenderer`, `AgentPortrayalStyle`, `PropertyLayerStyle`, full Altair+Matplotlib backends, multipage dashboards (backwards compatible) |
| 3.3.1 | 2025-11-07 | >=3.11 | Viz bugfixes; portrayal-dict deprecation documented |
| **3.4.0** | 2025-12-24 | **>=3.12** | `model.time` universal clock; `batch_run(rng=...)` replaces `iterations`; FutureWarnings; org rename to `mesa`; **experimental `cell_space` module deleted** (use `mesa.discrete_space`) |
| 3.4.1 | 2026-01-10 | >=3.12 | Many `batch_run`/`DataCollector` fixes (incl. `agenttype_reporters` support in batch_run); **`mesa.space` marked maintenance-only** |
| 3.4.2 | 2026-01-23 | >=3.12 | Critical memory-leak fix (`Agent._ids` → `Model.register_agent()`) |
| **3.5.0** | 2026-02-15 | >=3.12 | **Event scheduling API on Model** (`run_for`, `run_until`, `schedule_event`, `schedule_recurring`); event system stabilized as **new `mesa.time`**; deprecates: `seed` param, Simulator classes, AgentSet indexing, portrayal dicts |
| **3.5.1** | 2026-03-15 | >=3.12 | **Current stable.** Backported fixes/perf from 4.0 dev; `EventGenerator.pause()/resume()` |
| 4.0.0a0 | 2026-03-14 | >=3.12 | **Removes:** `seed` param, `model.steps`, `batch_run`, `mesa.space` + `agent.pos`, `PropertyLayer` class, Simulator classes. Experimental `Action` system |

Sources: https://github.com/mesa/mesa/blob/main/HISTORY.md, https://github.com/mesa/mesa/releases

### Official upgrade strategy (from the migration guide)

> - Update to the latest Mesa 2.x release (`mesa<3`).
> - Update to the latest Mesa 3.0.x release (`mesa<3.1`).
> - Update to the latest Mesa 3.x release (`mesa<4`).
>
> With each update, resolve all errors and warnings, before updating to the next one.

---

## 1. Python version requirements

| Mesa | Python |
|---|---|
| 2.x | >= 3.9 (2.3.x: 3.9–3.12) |
| 3.0.x | >= 3.10 |
| 3.1.x – 3.3.x | >= 3.11 |
| **3.4.0+ (incl. 3.5.1)** | **>= 3.12** (3.12, 3.13, 3.14 supported) |

Source: Mesa 3.0 release notes ("Python 3.10+ required"), 3.1.0 notes (PR #2474 "Drop support for Python 3.10, require Python >= 3.11"), 3.4.0 notes (PR #2842 "Drop Python 3.11, require Python 3.12+"), PyPI `Requires: Python >=3.12`.

---

## 2. `Model.__init__` changes

### 2.1 `super().__init__()` is now mandatory

```python
# OLD (Mesa 2.x) — calling super() was optional/implicit
import mesa

class MyModel(mesa.Model):
    def __init__(self, n_agents):
        self.schedule = mesa.time.RandomActivation(self)
        ...

# NEW (Mesa 3.x) — super().__init__() REQUIRED; pass seed (or rng in >=3.4)
class MyModel(mesa.Model):
    def __init__(self, some_arg_I_need, seed=None, some_kwarg_I_need=True):
        super().__init__(seed=seed)  # calling super is now required, passing seed is highly recommended
        ...
```

Exact `Model.__init__` signature in **v3.5.1** (from `mesa/model.py`):

```python
def __init__(
    self,
    *args: Any,
    seed: float | None = None,
    rng: RNGLike | SeedLike | None = None,
    scenario: S | None = None,   # scenario param added in 3.5 (experimental Scenario support)
    **kwargs: Any,
) -> None:
```
Docstring notes: *"you have to pass either seed or rng, but not both."* (Passing both raises `ValueError: you have to pass either rng or seed, not both` — verified.)

- `seed`: seeds `self.random` (a **stdlib** `random.Random`). **Deprecated in 3.5.0** in favor of `rng` (emits `FutureWarning: The use of the 'seed' keyword argument is deprecated, use 'rng' instead. No functional changes.` — verified). Removed in 4.0.
- `rng`: seeds `self.rng` (a **numpy** `numpy.random.Generator`); "When `rng` is None, a new `numpy.random.Generator` is created using entropy from the operating system. Types other than `numpy.random.Generator` are passed to `numpy.random.default_rng`". Present since 3.0.0.
- Both `self.random` and `self.rng` exist on every model and are seeded consistently from whichever argument you pass (bugfix in 3.1.3, PR #2598).

What `super().__init__()` sets up (v3.5.1 source): `self.running = True`, `self.steps = 0`, `self.time = 0.0`, `self.agent_id_counter = 1`, agent registries (`self._agents`, `self._agents_by_type`, `self._all_agents`), event list, and the RNGs.

### 2.2 Reserved / private variables (Mesa 3.0+)

From the migration guide:
> - Model: `agents`, `current_id`, `random`, `running`, `steps`, `time`.
> - Agent: `unique_id`, `model`.
>
> You can use (read) any reserved variable, but Mesa may update them automatically and rely on them, so modify/update at your own risk. Any variables starting with an underscore (`_`) are considered private.

Setting `model.agents = ...` raises (verified on 3.5.1):
```
AttributeError: You are trying to set model.agents. In Mesa 3.0 and higher, this attribute is used by Mesa itself, so you cannot use it directly anymore. Please adjust your code to use a different attribute name for custom agent storage.
```

### 2.3 `initialize_data_collector` removed

```python
# OLD
self.initialize_data_collector(model_reporters=..., agent_reporters=...)

# NEW
self.datacollector = mesa.DataCollector(model_reporters=..., agent_reporters=...)
```

### 2.4 `mesa.flat` namespace removed (3.0)

```python
# OLD
from mesa.flat.visualization import ...
# NEW — use full namespaces; import mesa.flat now raises ModuleNotFoundError
```

Source: https://mesa.readthedocs.io/latest/migration_guide.html (sections "Mandatory Model initialization", "Reserved and private variables", "Removal of Model.initialize_data_collector", "Removal of mesa.flat namespace")

---

## 3. `Agent.__init__` changes — `unique_id` removed from the signature

`unique_id` is auto-assigned in Mesa 3.0+ (an `int`, starting from 1, unique **per model**). `Model.next_id()` is removed.

```python
# OLD (Mesa 2.x)
class MyAgent(mesa.Agent):
    def __init__(self, unique_id, model, wealth):
        super().__init__(unique_id, model)
        self.wealth = wealth

agent = MyAgent(self.next_id(), self, wealth=1)

# NEW (Mesa 3.x)
class MyAgent(mesa.Agent):
    def __init__(self, model, wealth):
        super().__init__(model)          # no unique_id
        self.wealth = wealth

agent = MyAgent(self, wealth=1)          # or MyAgent(model=self, wealth=1)
```

Exact `Agent.__init__` signature in v3.5.1 (`mesa/agent.py`):
```python
def __init__(self, model: M, *args, **kwargs) -> None:
    """Create a new agent.

    Args:
        model (Model): The model instance in which the agent exists.
        args: Passed on to super.
        kwargs: Passed on to super.
    """
```

Key facts:
- Creating an agent **automatically registers** it with the model (`model.register_agent(self)` is called inside `Agent.__init__`); it appears in `model.agents` and `model.agents_by_type[type]`. No `schedule.add()` anymore.
- `agent.remove()` removes and deregisters the agent (replaces `self.model.schedule.remove(self)`).
- Every agent has `self.model`, `self.unique_id`, `self.random` (= `model.random`), `self.rng` (= `model.rng`), and (until 4.0) `self.pos` for the legacy `mesa.space` grids.
- If you previously used custom `unique_id` values, store them in your own attribute.

### Bulk creation helpers (Mesa 3.1+ / 3.5+)

```python
# Mesa 3.1+: create n agents at once; each kwarg is a single value or a length-n sequence
agents = MyAgent.create_agents(model, n, wealth=1)
# exact signature (v3.5.1): create_agents[T: Agent](cls: type[T], model: Model, n: int, *args, **kwargs) -> AgentSet[T]

# Mesa 3.5+: create agents from a pandas DataFrame (columns -> constructor args)
agents = MyAgent.from_dataframe(model, df)
```

**Custom constructor parameters + cell placement together** — the pattern that
trips people up. Every extra arg/kwarg is broadcast: a scalar goes to all n
agents, a length-n sequence is distributed element-wise. Prefer keywords for
clarity; `cell` is an ordinary kwarg here:

```python
class MoneyAgent(CellAgent):
    def __init__(self, model, max_init_money, cell=None):
        super().__init__(model)          # only model goes to super()
        self.cell = cell                 # set cell yourself
        self.wealth = self.random.randrange(max_init_money)

MoneyAgent.create_agents(
    self, n,
    max_init_money=10,                                        # scalar → same for all
    cell=self.random.choices(self.grid.all_cells.cells, k=n), # length-n → one each
)
```

Notes: positional broadcasting works too, but keywords survive signature
reordering. Under this skill's current-best-idiom policy, hand-rolled creation
loops are rewritten to `create_agents` (see the modernization checklist below;
pedagogy exception applies). When picking cellmates later, guard empties
before `random.choice` (`if cellmates:`) — `choice([])` raises.

Source: migration guide "Automatic assignment of unique_id to Agents"; `mesa/agent.py` @ v3.5.1.

---

## 4. Schedulers removed → AgentSet API

**The entire 2.x `mesa.time` module (all schedulers) was deprecated in 3.0 and REMOVED in 3.1.0** (PR #2476). Since Mesa 3.5, the name `mesa.time` exists again but contains the *event system* (`Event`, `EventGenerator`, `EventList`, `Priority`, `Schedule`) — **not** schedulers. So `from mesa.time import RandomActivation`:
- Mesa 3.0.x: works with a deprecation warning
- Mesa 3.1–3.4.x: `ModuleNotFoundError: No module named 'mesa.time'`
- Mesa 3.5+: `ImportError: cannot import name 'RandomActivation' from 'mesa.time'` (verified)

There is no `self.schedule` in 3.x — you drive activation yourself in `Model.step()` using the AgentSet API, and the step counter increments automatically.

### 4.1 Replacement table (verbatim from the migration guide)

**BaseScheduler**
```python
# OLD
self.schedule = BaseScheduler(self)
self.schedule.step()
# NEW
self.agents.do("step")
```

**RandomActivation**
```python
# OLD
self.schedule = RandomActivation(self)
self.schedule.step()
# NEW
self.agents.shuffle_do("step")
```

**SimultaneousActivation**
```python
# OLD
self.schedule = SimultaneousActivation(self)
self.schedule.step()
# NEW
self.agents.do("step")
self.agents.do("advance")
```

**StagedActivation**
```python
# OLD
self.schedule = StagedActivation(self, ["stage1", "stage2", "stage3"])
self.schedule.step()
# NEW
for stage in ["stage1", "stage2", "stage3"]:
    self.agents.do(stage)

# with shuffle / shuffle_between_stages options:
stages = ["stage1", "stage2", "stage3"]
if shuffle:
    self.random.shuffle(stages)
for stage in stages:
    if shuffle_between_stages:
        self.agents.shuffle_do(stage)
    else:
        self.agents.do(stage)
```

**RandomActivationByType**
```python
# OLD
self.schedule = RandomActivationByType(self)
self.schedule.step()
# NEW
for agent_class in self.agent_types:
    self.agents_by_type[agent_class].shuffle_do("step")

# step_type equivalent:
# OLD: self.schedule.step_type(AgentType)
# NEW:
self.agents_by_type[AgentType].shuffle_do("step")
```

### 4.2 Other scheduler-attribute replacements (migration guide "General Notes")

| OLD (2.x) | NEW (3.x) |
|---|---|
| `self.schedule.agents` | `self.agents` |
| `self.schedule.get_agent_count()` | `len(self.agents)` |
| `self.schedule.agents_by_type` | `self.agents_by_type` (dict: agent class → AgentSet) |
| `self.schedule.add(agent)` | *(automatic on agent creation)* |
| `self.schedule.remove(agent)` | `agent.remove()` |
| `self.model.schedule.remove(self)` (in Agent) | `self.remove()` |
| `self.schedule.steps` / `self.schedule.time` | `self.steps` / `self.time` (3.4+) |

### 4.3 AgentSet API (exact signatures from `mesa/agentset.py` @ v3.5.1)

`model.agents` is an AgentSet (concretely a `_HardKeyAgentSet` since 3.5); `model.agents_by_type[SomeAgent]` gives the per-class AgentSet; `model.agent_types` lists the classes.

```python
select(filter_func: Callable[[A], bool] | None = None, at_most: int | float = float("inf"),
       inplace: bool = False, agent_type: type[A] | None = None) -> AgentSet
shuffle(inplace: bool = False) -> AgentSet
sort(key: Callable[[A], Any] | str, ascending: bool = False, inplace: bool = False) -> AgentSet
do(method: str | Callable, *args, **kwargs) -> AgentSet          # call method on each agent
shuffle_do(method: str | Callable, *args, **kwargs) -> AgentSet  # shuffled, faster than shuffle().do()
map(method: str | Callable, *args, **kwargs) -> list[Any]        # collect return values
agg(attr_name: str, func: Callable | list[Callable])             # aggregate an attribute (multiple funcs since 3.2)
get(attr_names, handle_missing="error", default_value=None)      # list of attribute values
set(attr_name: str, value: Any) -> AgentSet
groupby(by: Callable | str, result_type: str = "agentset") -> GroupBy   # .map/.do/.count/.agg on groups
add(agent) / discard(agent) / remove(agent)
to_list() -> list[Agent]                                          # NEW in 3.5; use instead of indexing
```

> **Not on AgentSet:** `select_random_agent()` is a **`CellCollection`** method
> (`grid.all_cells.select_random_agent()`, `cell.neighborhood.select_random_agent()`),
> **not** an `AgentSet` method — `model.agents.select_random_agent()` raises
> `AttributeError` on 3.5.1 (verified). For a random agent from an AgentSet use
> `model.random.choice(model.agents.to_list())`.

Examples (from the 3.0 release notes, verified):
```python
wealthy = model.agents.select(lambda a: a.wealth > 1000)
model.agents.select(lambda a: a.energy > 0).do("move")
stats = model.agents.groupby("state").agg({"count": len, "avg_age": ("age", np.mean)})
total = model.agents.agg("wealth", sum)
```

> **Deprecated in 3.5.0 (removed in 4.0):** indexing/slicing an AgentSet.
> ```python
> # OLD (deprecated) : model.agents[0], model.agents[1:5]
> # NEW              : model.agents.to_list()[0], model.agents.to_list()[1:5]
> ```
> Verified warning on 3.5.1: `PendingDeprecationWarning: AgentSet.__getitem__ is deprecated and will be removed in Mesa 4.0. Use AgentSet.to_list()[index] instead.` (fires on derived `AgentSet`s, e.g. results of `select()`; `model.agents[0]` on the top-level set did not warn in 3.5.1.)

Sources: https://mesa.readthedocs.io/latest/migration_guide.html ("Time and schedulers", "AgentSet sequence behavior"); `mesa/agentset.py` @ v3.5.1.

---

## 5. Step counter and simulation time

```python
# OLD (2.x)
self.schedule.steps      # int, number of steps
self.schedule.time       # float or int

# NEW (3.0+)
self.steps               # auto-incremented by 1 at the START of each Model.step() call
# NEW (3.4+)
self.time                # float, universal simulation clock; +1.0 per step by default,
                         # or event-driven under the event scheduler
```

- `Model._steps` was renamed `Model.steps`; `Model._time` and `Model._advance_time()` were removed (3.0). The counter increments automatically — never increment it yourself.
- Mesa 3.4.0 added `model.time` as the "single source of truth" (#2903). `simulator.time` deprecated.
- **Mesa 4.0 removes `model.steps` entirely — use `model.time`.** If you're writing new 3.x code, prefer `model.time` for forward compatibility.
- Mesa 3.5 added time-based run control on Model (see §11): `model.run_for(10)` ≡ ten `model.step()` calls for classic ABMs.

Verified on 3.5.1: after `m.step(); m.step()` → `m.steps == 2`, `m.time == 2.0`; after `m.run_for(5)` → `steps=5, time=5.0`.

Source: migration guide "Automatic increase of the steps counter"; HISTORY.md 3.4.0, 4.0.0a0.

---

## 6. Spaces: `mesa.space` (legacy) vs `mesa.discrete_space` (new)

### 6.1 Status of the old `mesa.space`

- **Mesa 3.x: `mesa.space` still works, unchanged** — `MultiGrid`, `SingleGrid`, `HexSingleGrid/HexMultiGrid`, `ContinuousSpace`, `NetworkGrid`, and the space-level `PropertyLayer` all remain importable and functional through 3.5.1 (verified: constructing a `MultiGrid` on 3.5.1 emits no warnings).
- Since **3.4.1** the module is officially **maintenance-only** (PR #3082). Module docstring @ v3.5.1: *"mesa.space now in maintenance-only mode. While these classes remain fully supported, new development occurs in the discrete space module (`mesa.discrete_space`)"*.
- **Mesa 4.0 REMOVES `mesa.space` and `agent.pos`** (#3337): *"Use `mesa.discrete_space` for grid-based and network models."*

**Conclusion: migrating 2.x → 3.x does NOT require changing your space code.** Moving to `mesa.discrete_space` is optional in 3.x but required for Mesa 4. (`NetworkGrid` requires the `network` extra / networkx in both worlds.)

### 6.2 The new cell-space API: `mesa.discrete_space`

History: introduced as `mesa.experimental.cell_space` in 3.0, **stabilized as `mesa.discrete_space` in 3.2.0** (PR #2610); the experimental alias was deleted in 3.4.0 (#2969) — `from mesa.experimental.cell_space import ...` breaks on 3.4+.

The model is *cell-centric*: the grid is a collection of connected `Cell` objects; agents live **on cells** (`agent.cell`), not at `(x, y)` tuples managed by the grid.

Classes and exact constructor signatures (from https://mesa.readthedocs.io/stable/apis/discrete_space.html, v3.5.1):

```python
from mesa.discrete_space import (
    Cell, CellAgent, CellCollection, FixedAgent, Grid2DMovingAgent,
    HexGrid, Network, OrthogonalMooreGrid, OrthogonalVonNeumannGrid,
    PropertyLayer, VoronoiGrid,
)

OrthogonalMooreGrid(dimensions: Sequence[int], torus: bool = False,
                    capacity: float | None = None, random: Random | None = None,
                    cell_klass: type = Cell)          # 8 neighbors
OrthogonalVonNeumannGrid(...same...)                  # 4 neighbors
HexGrid(...same...)                                   # hexagonal tiling
Network(G, capacity=None, random=None, cell_klass=Cell, layout=spring_layout)  # from a networkx graph
VoronoiGrid(centroids_coordinates, capacity=None, random=None, cell_klass=Cell, capacity_function=round_float)
PropertyLayer(name: str, dimensions: Sequence[int], default_value=0.0, dtype=float)
```

Key API:
- `grid[(x, y)]` → `Cell`; `grid.all_cells` → `CellCollection`; `grid.all_cells.cells` → `list[Cell]`; `grid.empties`; `grid.select_random_empty_cell()`; `grid.width/height` (2D orthogonal grids); `grid.add_cell/remove_cell/add_connection/remove_connection` (dynamic spaces, 3.2+).
- `Cell`: `.coordinate`, `.agents`, `.is_empty`, `.is_full`, `.capacity`, `.neighborhood` (radius-1 `CellCollection`), `.get_neighborhood(radius=1, include_center=False)`, `.position` (3.5+).
- `CellCollection`: `.select_random_cell()`, `.select_random_agent()`, `.select(filter_func=None, at_most=inf)`, `.agents`, `.cells`. (Note: **no** `.to_list()` — that's AgentSet-only; use `.cells`.)
- Agent base classes: **`CellAgent`** (movable; has read/write `.cell` property) and **`FixedAgent`** (immobile "patch"; `.cell` settable once). `Grid2DMovingAgent` adds `move(direction: str, distance: int = 1)` with compass shorthands. Assigning `agent.cell = some_cell` performs the move (registration in cell agent lists is automatic).

### 6.3 OLD → NEW space code

```python
# OLD (Mesa 2.x, mesa.space.MultiGrid)
from mesa.space import MultiGrid

class MyModel(mesa.Model):
    def __init__(self, width, height, n, seed=None):
        super().__init__(seed=seed)
        self.grid = MultiGrid(width, height, torus=True)
        for i in range(n):
            a = MyAgent(self)
            x = self.random.randrange(width); y = self.random.randrange(height)
            self.grid.place_agent(a, (x, y))

class MyAgent(mesa.Agent):
    def move(self):
        neighbors = self.model.grid.get_neighborhood(self.pos, moore=True, include_center=False)
        new_pos = self.random.choice(neighbors)
        self.model.grid.move_agent(self, new_pos)
        cellmates = self.model.grid.get_cell_list_contents([self.pos])
```

```python
# NEW (Mesa 3.2+, mesa.discrete_space) — verified running on 3.5.1
from mesa.discrete_space import CellAgent, OrthogonalMooreGrid

class MyModel(mesa.Model):
    def __init__(self, width=10, height=10, n=10, seed=None):
        super().__init__(seed=seed)
        self.grid = OrthogonalMooreGrid((width, height), torus=True, random=self.random)
        MyAgent.create_agents(
            self, n,
            cell=self.random.choices(self.grid.all_cells.cells, k=n),
        )

class MyAgent(CellAgent):
    def __init__(self, model, cell):
        super().__init__(model)
        self.cell = cell

    def move(self):
        self.cell = self.cell.neighborhood.select_random_cell()  # move = assign .cell
        cellmates = [a for a in self.cell.agents if a is not self]
```

Mapping table:

| OLD `mesa.space` | NEW `mesa.discrete_space` |
|---|---|
| `MultiGrid(w, h, torus)` | `OrthogonalMooreGrid((w, h), torus=torus, capacity=None, random=self.random)` |
| `SingleGrid(w, h, torus)` | `OrthogonalMooreGrid((w, h), torus=torus, capacity=1, random=self.random)` |
| (Moore vs Von Neumann arg `moore=False`) | choose grid class: `OrthogonalVonNeumannGrid` |
| `HexSingleGrid/HexMultiGrid` | `HexGrid((w, h), ...)` |
| `NetworkGrid(G)` | `Network(G, ...)` |
| `grid.place_agent(a, pos)` | `a.cell = grid[pos]` (agent must be a `CellAgent`/`FixedAgent`) |
| `grid.move_agent(a, pos)` | `a.cell = grid[pos]` / `a.move_to(cell)` |
| `grid.remove_agent(a)` | `a.cell = None` or `a.remove()` |
| `agent.pos` | `agent.cell.coordinate` |
| `grid.get_neighborhood(pos, moore, include_center, radius)` | `cell.get_neighborhood(radius=1, include_center=False)` / `cell.neighborhood` |
| `grid.get_neighbors(pos, ...)` | `cell.neighborhood.agents` |
| `grid.get_cell_list_contents([pos])` | `cell.agents` |
| `grid.coord_iter()` | `for cell in grid.all_cells` |
| `grid.empties` / `grid.exists_empty_cells()` | `grid.empties` / `len(grid.empties) > 0` |
| `grid.move_to_empty(agent)` | `agent.cell = grid.select_random_empty_cell()` |
| iterate patches | create one `FixedAgent` per cell, or use `PropertyLayer` |

**Every grid/`Network` constructor takes `random=self.random`** — omit it and Mesa
emits `UserWarning: Random number generator not specified, this can make models
non-reproducible` at runtime (a real, easy-to-miss finding: the scanner cannot see
an *absent* kwarg, so this is a semantic-pass check on every `OrthogonalMooreGrid`/
`OrthogonalVonNeumannGrid`/`HexGrid`/`Network(...)` call).

#### Dynamic `NetworkGrid` → `Network` — the two traps that silently corrupt network models

Network ABMs routinely rewire the graph at runtime (`G.remove_edge`, `remove_node`,
`add_edge` — e.g. an epidemic model that severs contacts). The migration has two
non-obvious hazards, both verified:

- **`Network` snapshots connectivity at construction and aliases the graph object**
  (`grid.G is model.G`). Mutating `self.G` directly does **not** update cell
  neighborhoods (the model runs but is silently wrong), and mutating *both* the graph
  and the grid double-removes and raises `networkx.NetworkXError`. **Route every
  connectivity change through the grid** — `grid.remove_connection(cell_a, cell_b)`,
  `grid.add_connection(...)`, `grid.remove_cell(cell)` — which update the shared graph
  *and* cell adjacency together. Guard with `if G.has_edge(u, v):` to stay idempotent.
- **`get_neighbors` return type changed by era.** Legacy `NetworkGrid.get_neighbors`
  returns **agents** on Mesa 3.x but returned **node ids** on Mesa ≤1.x. A notebook
  written for the old behavior (`get_cell_list_contents(get_neighbors(pos))`) actually
  *errors* on 3.x. Port to `cell.neighborhood.agents` (agents) and drop the
  `get_cell_list_contents` wrapper — don't mechanically translate the wrapper.

### 6.4 ContinuousSpace

- Legacy `mesa.space.ContinuousSpace` still works in all of 3.x (removed in 4.0).
- An **experimental** rewrite lives in `mesa.experimental.continuous_space` since 3.1.3 — agent-centric, n-dimensional:

```python
# experimental (3.1.3+), API may change
from mesa.experimental.continuous_space import ContinuousSpace, ContinuousSpaceAgent
space = ContinuousSpace(dimensions=[[0, 1], [0, 1]], torus=True, random=model.random)
agent = ContinuousSpaceAgent(space, model)
agent.position = [0.5, 0.5]
agent.position += [0.1, 0.1]
neighbors, distances = agent.get_neighbors_in_radius(radius=0.2)
nearest, distances = agent.get_nearest_neighbors(k=5)
```

### 6.5 PropertyLayer

- Stabilized in 3.2.0 (`mesa.discrete_space.PropertyLayer`, attachable to grids; also the older `mesa.space.PropertyLayer`).
- Signature @3.5.1: `PropertyLayer(name, dimensions, default_value=0.0, dtype=float)`; methods `set_cells(value, condition=None)`, `modify_cells(operation, value=None, condition=None)`, `select_cells(condition)`, `aggregate(operation)`. Since 3.4.1 it implements the NumPy array interface directly (standard NumPy syntax works).
- Grids expose layers as attributes: `grid.add_property_layer(layer)`, then `grid.<name>.data` and per-cell access.
- **Mesa 4.0 removes the `PropertyLayer` class** — layers become raw NumPy arrays stored on the grid (`property_layers`).

Sources: https://mesa.readthedocs.io/stable/apis/discrete_space.html; HISTORY.md 3.2.0 / 3.4.0 / 4.0.0a0; `mesa/space.py` @ v3.5.1 docstring.

---

## 7. DataCollector changes

Constructor @ v3.5.1 (`mesa/datacollection.py`):
```python
DataCollector(model_reporters=None, agent_reporters=None, agenttype_reporters=None, tables=None)
```

Changes vs 2.x:
1. **`agenttype_reporters` (available since 2.4.0; verified absent on 2.3.4):** collect different metrics per agent class.
   ```python
   self.datacollector = mesa.DataCollector(
       model_reporters={"total_wealth": lambda m: m.agents.agg("wealth", sum)},
       agent_reporters={"age": "age"},                      # applies to ALL agents
       agenttype_reporters={
           Predator: {"kills": "kills_count"},
           Prey: {"distance_fled": "total_flight_distance"},
       },
   )
   df = self.datacollector.get_agenttype_vars_dataframe(Predator)   # NEW getter
   ```
   **Gotcha (verified):** plain `agent_reporters` are applied to **every** agent in the model. In multi-type models where only some types have the attribute you get `AttributeError: Agent 1 of type Patch has no attribute 'wealth' (reporter: 'Wealth')`. Use `agenttype_reporters` for type-specific attributes.
2. `self.initialize_data_collector(...)` (2.x Model method) → removed; assign `self.datacollector = DataCollector(...)` and call `self.datacollector.collect(self)` yourself (typically at the end of `__init__` and of each `step`).
3. Reporter formats (unchanged plus additions): attribute-name string, lambda, method, `functools.partial`, and `[function, [params]]`. Since 3.4.1, method-reporter validation and multiple `collect()` calls per step work correctly.
4. Getters: `get_model_vars_dataframe()`, `get_agent_vars_dataframe()`, `get_agenttype_vars_dataframe(agent_type)`, `get_table_dataframe(name)`. Agent dataframes are indexed on `(Step, AgentID)` where `AgentID` is the auto-assigned integer `unique_id`.
5. `batch_run` supports `agenttype_reporters` only since **3.4.1** (#3095).
6. (3.5 experimental alternative: `DataRecorder`/`DataRegistry` event-driven collection with memory/SQLite/Parquet/JSON backends — not needed for migration.)

Source: `mesa/datacollection.py` @ v3.5.1; Mesa 3.0 release notes; HISTORY.md 3.4.1.

---

## 8. `batch_run` changes

Exact signature @ v3.5.1 (`mesa/batchrunner.py`):
```python
def batch_run(
    model_cls: type[Model],
    parameters: Mapping[str, Any | Iterable[Any]],
    number_processes: int | None = 1,
    iterations: int | None = None,        # DEPRECATED since 3.4
    data_collection_period: int = -1,
    max_steps: int = 1000,
    display_progress: bool = True,
    rng: SeedLike | Iterable[SeedLike] | None = None,   # NEW in 3.4
) -> list[dict[str, Any]]:
```

- 2.x → 3.0: the call itself is unchanged (`mesa.batch_run(...)`); the old class-based `BatchRunner`/`FixedBatchRunner` (already deprecated in 2.x) are gone. Your model must (a) accept every key in `parameters` as a **keyword argument**, (b) set `self.running`/respect `max_steps`, (c) have a `self.datacollector` (docstring: "batch_run assumes the model has a `datacollector` attribute that has a DataCollector object initialized").
- **3.4.0: `iterations` deprecated → `rng`** (#2841). Rationale: with a fixed model seed, `iterations=n` produced n identical replications. `rng` takes one seed or an iterable of seeds — one model run per seed per parameter combination.

```python
# OLD (2.x / early 3.x)
results = mesa.batch_run(
    MoneyModel,
    parameters={"n": range(10, 100, 10), "width": 10, "height": 10},
    iterations=5,
    max_steps=100,
    number_processes=1,
    data_collection_period=1,
    display_progress=True,
)

# NEW (Mesa 3.4+) — verified on 3.5.1
import numpy as np, sys
rng = np.random.default_rng(42)
rng_values = rng.integers(0, sys.maxsize, size=(5,))   # 5 replications
results = mesa.batch_run(
    MoneyModel,
    parameters={"n": range(10, 100, 10), "width": 10, "height": 10},
    rng=rng_values.tolist(),      # pass the 5 seed values; each iteration uses a different seed
    max_steps=100,
    number_processes=1,
    data_collection_period=1,
    display_progress=True,
)
```

- Errors/warnings (verified): `iterations` + `rng` together → `ValueError: you cannot use both iterations and rng at the same time. Please only use rng.`; `iterations=` alone → `DeprecationWarning: The 'iterations' keyword argument is deprecated. Use 'rng' instead (e.g. 'iterations=5' is equivalent to 'rng=[None] * 5').`
- The seed is passed to your model's `rng` parameter — so your `__init__` should accept/forward `rng` (or at least `seed` pre-3.4-style). Result rows contain `RunId`, `iteration`, `Step`, each parameter, model reporters, and (if agent reporters) `AgentID` + agent reporters (verified keys: `['AgentID', 'Gini', 'RunId', 'Step', 'Wealth', 'height', 'iteration', 'n']`).
- **Gotcha (verified empirically on 3.5.1):** `batch_run` emits **zero rows** when the model's DataCollector defines only `agent_reporters` — its collection steps are derived from model-reporter collections, so an agent-reporters-only collector silently yields an empty result list (2.x returned the agent rows). Fix: add at least one model reporter (e.g. `{"MaxWealth": lambda m: m.agents.agg("wealth", max)}`). A migration that leaves an agent-reporters-only collector feeding `batch_run` has silently changed behavior — check the row count against the pre-migration run.
- **Mesa 4.0 removes `batch_run` entirely** (→ `Scenario`-based experiment management, #3134/#3325).

Source: migration guide "Mesa 3.4.0 — batch run"; `mesa/batchrunner.py` @ v3.5.1.

---

## 9. Visualization: ModularServer → SolaraViz (+ 3.3's SpaceRenderer)

### 9.1 What happened

- **Mesa 2.x:** `mesa.visualization.ModularServer` + `CanvasGrid`, `ChartModule`, etc. (tornado/JS stack; in 2.3 these actually came from the `mesa-viz-tornado` package re-exported under `mesa.visualization`). Portrayal = dict like `{"Shape": "circle", "Filled": "true", "Layer": 0, "Color": "red", "r": 0.5}`. Run via `server.launch()` on port 8521. **All of this is gone in Mesa 3.0** — `from mesa.visualization.ModularVisualization import ModularServer` → `ModuleNotFoundError` (verified).
- **Mesa 3.0:** new Solara-based `SolaraViz` (marked *experimental* in 3.0, stabilizing through 3.1/3.2; the module docstring still carries an experimental note in 3.5.1). Takes a **model instance** (not class), and a list of `components` built with `make_space_component` / `make_plot_component`.
- **Mesa 3.3.0:** visualization overhaul (GSoC): `SpaceRenderer`, `AgentPortrayalStyle`, `PropertyLayerStyle`, full Altair + Matplotlib backend support, multipage dashboards. Backwards compatible; portrayal **dicts** and `make_space_component` keep working but are **deprecated since 3.5.0** (#3144).
- Dependencies: `pip install "mesa[viz]"` → `solara`, `matplotlib`, `altair`, `starlette<1.0`. Without them, `import mesa.visualization` fails (`ModuleNotFoundError: No module named 'matplotlib'` — verified).

### 9.2 OLD (2.x) → NEW (3.x) minimal dashboard

```python
# OLD (Mesa 2.x)
from mesa.visualization.modules import CanvasGrid, ChartModule
from mesa.visualization.ModularVisualization import ModularServer

def agent_portrayal(agent):
    return {"Shape": "circle", "Filled": "true", "Layer": 0,
            "Color": "red" if agent.wealth > 0 else "grey", "r": 0.5}

grid = CanvasGrid(agent_portrayal, 10, 10, 500, 500)
chart = ChartModule([{"Label": "Gini", "Color": "Black"}], data_collector_name="datacollector")
server = ModularServer(MoneyModel, [grid, chart], "Money Model",
                       {"N": 100, "width": 10, "height": 10})
server.port = 8521
server.launch()
```

```python
# NEW (Mesa 3.0–3.2 style; still works in 3.5 but component-factories now superseded by SpaceRenderer)
from mesa.visualization import SolaraViz, make_space_component, make_plot_component

def agent_portrayal(agent):
    return {"color": "red" if agent.wealth > 0 else "grey", "marker": "o", "size": 50}

model = MoneyModel(n=100, width=10, height=10)      # an INSTANCE, not the class
page = SolaraViz(
    model,
    components=[
        make_space_component(agent_portrayal),
        make_plot_component("Gini"),
    ],
    model_params=model_params,
    name="Money Model",
)
page   # in Jupyter: last expression displays the dashboard
```

```python
# NEW (Mesa 3.4+ CURRENT style — verified on 3.5.1)
# ⚠ setup_agents/setup_structure/setup_propertylayer exist only from 3.4.0
#   (verified empirically). At target 3.3.x the current form is
#   renderer = SpaceRenderer(model, backend="matplotlib").render(agent_portrayal)
#   — passing portrayals to render()/draw_agents() warns from 3.4 on.
from mesa.visualization import SolaraViz, SpaceRenderer, make_plot_component
from mesa.visualization.components import AgentPortrayalStyle

def agent_portrayal(agent):
    return AgentPortrayalStyle(
        color="red" if agent.wealth > 0 else "grey",
        marker="o",
        size=50,
    )

model = MoneyModel(n=50, width=10, height=10)

renderer = (
    SpaceRenderer(model, backend="matplotlib")   # or backend="altair"
    .setup_agents(agent_portrayal)               # 3.4+ only
    .render()
)

page = SolaraViz(
    model,
    renderer,
    components=[make_plot_component("Gini")],
    model_params=model_params,
    name="Money Model",
)
page  # "This is required to render the visualization in the Jupyter notebook" (official tutorial)
```

### 9.3 Exact `SolaraViz` signature (v3.5.1, `mesa/visualization/solara_viz.py`)

```python
@solara.component
def SolaraViz(
    model: Model | solara.Reactive[Model],
    renderer: SpaceRenderer | None = None,
    components: list | Literal["default"] = [],
    *,
    play_interval: int = 100,          # ms between steps when playing
    render_interval: int = 1,          # update plots every N steps
    simulator: Simulator | None = None,
    model_params=None,
    name: str | None = None,
    use_threads: bool = False,
    **console_kwargs,
):
```
Docstring example: `>>> model = MyModel()` / `>>> page = SolaraViz(model)` / `>>> page`.

`mesa.visualization` exports @ v3.5.1: `CommandConsole, JupyterViz, Slider, SolaraViz, SpaceRenderer, draw_space, make_plot_component, make_space_altair, make_space_component` (`JupyterViz = SolaraViz` — a plain alias, kept for 2.3-era code). `AgentPortrayalStyle` / `PropertyLayerStyle` are imported from `mesa.visualization.components`.

Component factories (v3.5.1 signatures):
```python
make_space_component(agent_portrayal: Callable | None = None,
                     propertylayer_portrayal: dict | None = None,
                     post_process: Callable | None = None,
                     backend: str = "matplotlib",       # or "altair"
                     **space_drawing_kwargs)
make_plot_component(measure: str | dict[str, str] | list[str] | tuple[str],
                    post_process: Callable | None = None,
                    backend: str = "matplotlib",
                    page: int = 0,                      # multipage support, 3.3+
                    **plot_drawing_kwargs)
make_space_altair(...)   # altair-backend space component
```
(`make_plot_measure` and `make_text` were transitional names in the 3.0 alphas; the stable names are `make_plot_component` and "just pass a function returning a string/solara component directly in `components`".)

### 9.4 Key semantic changes vs 2.x

1. **Model instance, not class:** `SolaraViz(model, ...)` — 2.x passed `model_cls` + params dict. On Reset, SolaraViz re-instantiates the model **with keyword arguments only** (`Model(**model_params)`).
   > Official tutorial warning: "When using SolaraViz, Mesa models must be instantiated using keyword arguments only... `MyModel(10, 10)` not supported; `MyModel(width=10, height=10)` supported." Recommended: define `__init__(self, *, width, height, seed=None)`.
2. **`model_params`** dict — each entry either a fixed value or an input-widget spec:
   ```python
   model_params = {
       "n": {"type": "SliderInt", "value": 50, "label": "Number of agents:",
             "min": 10, "max": 100, "step": 1},
       "width": 10,     # fixed
       "height": 10,
   }
   # or use the helper class:
   from mesa.visualization import Slider
   model_params = {"density": Slider("Agent density", value=0.8, min=0.1, max=1.0, step=0.1)}
   ```
   Slider signature @3.5.1: `Slider(label="", value=None, min=None, max=None, step=1, dtype=None)`. Other input types: `"SliderInt"`, `"SliderFloat"`, `"Select"` (with `"values"`), `"Checkbox"`, `"InputText"`.
3. **Portrayal function returns `AgentPortrayalStyle` (3.3+)** — dataclass fields (v3.5.1): `x, y, color="tab:blue", marker="o", size=50, zorder=1, alpha=1.0, edgecolors, linewidths=1.0, tooltip`. It has an `.update(("color", "red"), ("size", 30))` helper. Dict portrayals still accepted but deprecated (removed in 4.0).
   ```python
   # OLD (3.0–3.2)                                  # NEW (3.3+)
   def agent_portrayal(agent):                      def agent_portrayal(agent):
       return {"color": "white", "marker": "s",         return AgentPortrayalStyle(
               "size": 30}                                  color="white", marker="s", size=30)
   ```
4. **PropertyLayer portrayal is now a function returning `PropertyLayerStyle` (3.3+)** — fields: `colormap, color, alpha=0.8, colorbar=True, vmin, vmax` (exactly one of `color`/`colormap`):
   ```python
   # OLD: dict keyed by layer name                  # NEW:
   propertylayer_portrayal = {                      def propertylayer_portrayal(layer):
       "sugar": {"colormap": "pastel1",                 if layer.name == "sugar":
                  "alpha": 0.75, ...}}                       return PropertyLayerStyle(
                                                                colormap="pastel1", alpha=0.75,
                                                                colorbar=True, vmin=0, vmax=10)
   ```
5. **SpaceRenderer (3.3+):** `SpaceRenderer(model, backend="matplotlib")` with chainable `setup_structure(**kwargs)`, `setup_agents(agent_portrayal)`, `setup_propertylayer(propertylayer_portrayal)`, then `draw_structure()/draw_agents()/draw_propertylayer()` or just `.render(agent_portrayal=None, propertylayer_portrayal=None, **kwargs)`; `post_process` property. Since 3.4/3.5, passing portrayals directly to `draw_agents()` is deprecated — use `setup_*` first: `renderer.setup_agents(agent_portrayal).draw_agents()`.
6. **Multipage dashboards (3.3+):** `make_plot_component("Gini", page=1)`; custom components as `(Component, page)` tuples. Default page is 0.
7. **Text components:** any `def show_steps(model): return f"Steps: {model.steps}"` can be put straight into `components=[show_steps]`.
8. **Custom solara components:** `@solara.component def MyComp(model): ...` and pass `MyComp` in `components`.

### 9.5 Running it

- **Jupyter notebook:** put `page = SolaraViz(...)` in a cell and make `page` the last expression — it renders inline as an ipywidget. (Official tutorials run this way; note: **does not work on Google Colab** — "Due to conflict with Colab and Solara there are no colab links for this tutorial".)
- **Standalone browser app:** put the code in `app.py` ending with `page = SolaraViz(...)` at module level, then:
  ```bash
  solara run app.py     # serves at http://localhost:8765
  ```
- Reactive model in notebooks: `model = solara.reactive(MyModel())`; `model.value.step()` updates plots; `model.value.force_update()` forces a redraw (migration guide, 3.0 section).

Sources: https://mesa.readthedocs.io/latest/migration_guide.html ("Visualisation", "Mesa 3.3.0"); tutorial notebook `docs/tutorials/6_visualization_basic.ipynb` @ v3.5.1; `mesa/visualization/*.py` @ v3.5.1. Tutorial series on stable docs: `0_first_model`, `1_agentset`, `2_agent_activation`, `3_event_scheduling`, `4_adding_space`, `5_collecting_data`, `6_visualization_basic`, `7_visualization_dynamic_agents`, `8_visualization_rendering_with_space_renderer`, `9_visualization_propertylayer_visualization`, `10_visualization_custom`, `11_batch_run`, `12_comparing_scenarios`.

---

## 10. Randomness: `self.random`, `self.rng`, `seed` → `rng`

- **`model.random`** — stdlib `random.Random`, existed in 2.x, still there. Every Agent proxies it: `self.random` inside an agent == `self.model.random`.
- **`model.rng`** — **NEW in 3.0**: a `numpy.random.Generator`. Agents proxy it as `self.rng`. Use for vectorized draws: `self.rng.integers(...)`, `self.rng.normal(...)`.
- Seeding: `super().__init__(seed=42)` (2.x-compatible, deprecated 3.5, removed 4.0) or `super().__init__(rng=42)` (3.4+ recommended). Both seed *both* generators consistently (fixed in 3.1.3 #2598). `model.reset_rng(rng=None)` reseeds.
- Since 3.5, using `seed=` emits `FutureWarning: The use of the 'seed' keyword argument is deprecated, use 'rng' instead. No functional changes.` (verified).
- Reproducibility pattern (verified: same `rng` seed → identical runs):
  ```python
  # OLD                                    # NEW (3.4+)
  class M(mesa.Model):                     class M(mesa.Model):
      def __init__(self, seed=None):           def __init__(self, rng=None):
          super().__init__(seed=seed)              super().__init__(rng=rng)
  ```
- Spaces take `random=self.random` (e.g., `OrthogonalMooreGrid(..., random=self.random)`) — pass it or Mesa warns about a missing RNG.

Source: `mesa/model.py` @ v3.0.0 and v3.5.1; HISTORY.md 3.1.3, 3.5.0 (#3147).

---

## 11. New in 3.5: event scheduling / time advancement (replaces step loops and Simulators)

```python
# OLD
for _ in range(10):
    model.step()

# NEW (3.5+)
model.run_for(10)     # advance 10 time units (identical to 10 steps for classic ABMs)
model.run_until(50.0) # run until absolute time 50

# One-off events
model.schedule_event(callback, at=50.0)     # absolute time
model.schedule_event(callback, after=5.0)   # relative time
event = model.schedule_event(callback, at=100.0); event.cancel()

# Recurring events
from mesa.time import Schedule               # mesa.time is the NEW event module (3.5+)
model.schedule_recurring(func, Schedule(interval=10))            # first run at t=10
model.schedule_recurring(func, Schedule(interval=10, start=0))   # start immediately
gen = model.schedule_recurring(func, Schedule(interval=5.0)); gen.stop()
model.schedule_recurring(func, Schedule(interval=1.0, count=10)) # limit executions
```

- Replaces the experimental `mesa.experimental.devs` Simulators (`ABMSimulator`, `DEVSimulator`) which are deprecated in 3.5 and **removed in 4.0**:
  ```python
  # OLD                                             # NEW
  from mesa.experimental.devs.simulator import ABMSimulator
  simulator = ABMSimulator()                        model.run_for(100)
  simulator.setup(model)
  simulator.run_for(100)
  ```
- `mesa.time` (3.5+) exports: `Event, EventGenerator, EventList, Priority, Schedule`. 3.5.1 adds `EventGenerator.pause()/resume()`, `next_scheduled_time`, `EventList.compact()`.

Source: migration guide "Mesa 3.5.0"; HISTORY.md 3.5.0/3.5.1.

---

## 12. Deprecation/removal timeline cheat sheet ("worked in 3.0, gone later")

| Feature | Deprecated | Removed | Replacement |
|---|---|---|---|
| `mesa.time` schedulers (RandomActivation, etc.) | 3.0 | **3.1.0** | AgentSet: `agents.do/shuffle_do`, `agents_by_type` |
| Old 2.x visualization (ModularServer, CanvasGrid, ChartModule) | 2.3 | **3.0** | SolaraViz |
| `mesa.flat` | 2.3 | **3.0** | full namespaces |
| `Model.next_id()`, `unique_id` arg to Agent | — | **3.0** | auto-assigned `unique_id` |
| `Model.initialize_data_collector` | 2.x | **3.0** | `self.datacollector = DataCollector(...)` |
| `mesa.experimental.cell_space` | 3.2 (stabilized as `mesa.discrete_space`) | **3.4.0** (#2969) | `mesa.discrete_space` |
| `simulator.time` | 3.4 | 4.0 | `model.time` |
| `batch_run(iterations=...)` | **3.4** | 4.0 | `batch_run(rng=[...])` |
| `Model(seed=...)` | **3.5** (FutureWarning) | 4.0 | `Model(rng=...)` |
| AgentSet indexing/slicing (`agents[0]`) | **3.5** | 4.0 | `agents.to_list()[0]` |
| Portrayal dicts (agent & propertylayer) | **3.5** (#3144; introduced 3.3) | 4.0 | `AgentPortrayalStyle` / `PropertyLayerStyle` |
| Portrayal args to `renderer.draw_agents(...)` | 3.4/3.5 (#2893/#3202) | 4.0 | `renderer.setup_agents(p).draw_agents()` |
| `ABMSimulator` / `DEVSimulator` (`mesa.experimental.devs`) | **3.5** | **4.0** | `model.run_for/run_until/schedule_event/schedule_recurring` |
| `mesa.space` (+ `agent.pos`) | maintenance-only 3.4.1 | **4.0** (#3337) | `mesa.discrete_space` |
| `model.steps` | — | **4.0** (#3328) | `model.time` |
| `batch_run` (entire function) | — | **4.0** (#3325) | `Scenario` + direct model control |
| `PropertyLayer` class | — | **4.0** (#3340) | NumPy arrays on grid (`property_layers`) |

Also: all Mesa deprecation warnings use `FutureWarning` since 3.4.0 (#2905) so they're visible by default; formal deprecation policy in CONTRIBUTING.md.

---

## 13. Common runtime errors running Mesa 2.x code on Mesa 3.x

All messages below were **reproduced on Mesa 3.5.1** unless noted.

| Error (exact text) | Cause | Fix |
|---|---|---|
| `RuntimeError: The Mesa Model class was not initialized. You must explicitly initialize the Model by calling super().__init__() on initialization.` (message documented in the migration guide; on 3.0 it surfaced as a `FutureWarning` with self-healing, on 3.5.1 you instead get `AttributeError: 'MyModel' object has no attribute '_all_agents'` when the first agent registers or `model.agents` is touched) | `Model.__init__` override doesn't call `super().__init__()` | Add `super().__init__(seed=seed)` / `super().__init__(rng=rng)` first |
| `TypeError: object.__init__() takes exactly one argument (the instance to initialize)` raised from `Agent.__init__` | 2.x-style `super().__init__(unique_id, model)` — the extra positional/keyword arg falls through Agent to `object` | Remove `unique_id`: `super().__init__(model)` |
| `TypeError: MyAgent.__init__() got an unexpected keyword argument 'unique_id'` (or missing-positional variants) | Call site still passes `unique_id` after class was updated | Create with `MyAgent(self, ...)` |
| `ModuleNotFoundError: No module named 'mesa.time'` (Mesa 3.1–3.4.x) | Importing removed scheduler module | Delete scheduler; use AgentSet API |
| `ImportError: cannot import name 'RandomActivation' from 'mesa.time'` (Mesa 3.5+, where `mesa.time` is the *event* module) | Same, on 3.5+ | Same |
| `AttributeError: 'MyModel' object has no attribute 'schedule'` | Code references `self.schedule` / `model.schedule.step()` / `model.schedule.agents` | `model.agents.shuffle_do("step")`, `model.agents`, `model.steps` |
| `AttributeError: 'MyModel' object has no attribute 'next_id'` | `Model.next_id()` removed in 3.0 | Drop it; `unique_id` is automatic |
| `AttributeError: You are trying to set model.agents. In Mesa 3.0 and higher, this attribute is used by Mesa itself...` | Assigning to reserved `model.agents` | Rename your attribute (e.g. `self.my_agents`) |
| `ModuleNotFoundError: No module named 'mesa.visualization.ModularVisualization'` / `...mesa.visualization.modules'` | 2.x visualization stack removed in 3.0 | Rewrite with SolaraViz (§9) |
| `ModuleNotFoundError: No module named 'matplotlib'` (or `'solara'`, `'altair'`) on `import mesa.visualization` | viz extras not installed | `pip install "mesa[viz]"` (or `mesa[rec]`) |
| `ModuleNotFoundError: No module named 'networkx'` on plain `import mesa` (3.5.x) | bare `pip install mesa` lacks networkx, but `mesa.discrete_space.network` needs it | `pip install "mesa[rec]"` |
| `ModuleNotFoundError: No module named 'mesa.flat'` | `mesa.flat` removed in 3.0 | Full namespace imports |
| `ModuleNotFoundError: No module named 'mesa.experimental.cell_space'` (3.4+) | experimental module deleted after stabilization | `from mesa.discrete_space import ...` |
| `ValueError: you have to pass either rng or seed, not both` | `super().__init__(seed=..., rng=...)` | Pass exactly one |
| `ValueError: you cannot use both iterations and rng at the same time. Please only use rng.` | `batch_run(..., iterations=..., rng=...)` | Use only `rng` |
| `DeprecationWarning: The 'iterations' keyword argument is deprecated. Use 'rng' instead (e.g. 'iterations=5' is equivalent to 'rng=[None] * 5').` | `batch_run(iterations=n)` on 3.4+ | `rng=[seed1, ..., seedn]` |
| `FutureWarning: The use of the 'seed' keyword argument is deprecated, use 'rng' instead. No functional changes.` | `Model(seed=...)` on 3.5+ | switch to `rng=` |
| `PendingDeprecationWarning: AgentSet.__getitem__ is deprecated and will be removed in Mesa 4.0. Use AgentSet.to_list()[index] instead.` | indexing an AgentSet on 3.5+ | `agents.to_list()[i]` |
| `AttributeError: Agent 3 of type Patch has no attribute 'wealth' (reporter: 'Wealth')` | `agent_reporters` applied to all agent types in a multi-type model | use `agenttype_reporters={MoneyAgent: {...}}` |
| SolaraViz: `TypeError: MyModel.__init__() ... positional ...` or wrong param routing on Reset | SolaraViz instantiates the model with `**model_params` (keyword-only) | Keyword args for all model params; keys of `model_params` must match `__init__` kwargs |
| Dashboard shows but agents don't appear / `agent_portrayal` errors under 3.3+ | dict portrayal fields from 2.x (`"Shape"/"Color"/"r"/"Layer"`) don't map | Return `AgentPortrayalStyle(color=..., marker=..., size=...)` |

---

## 14. Minimal complete before/after example (verified running on 3.5.1)

```python
# ===================== OLD: Mesa 2.x =====================
import mesa

class MoneyAgent(mesa.Agent):
    def __init__(self, unique_id, model):
        super().__init__(unique_id, model)
        self.wealth = 1

    def step(self):
        if self.wealth > 0:
            other = self.random.choice(self.model.schedule.agents)
            other.wealth += 1
            self.wealth -= 1

class MoneyModel(mesa.Model):
    def __init__(self, N):
        self.num_agents = N
        self.schedule = mesa.time.RandomActivation(self)
        for i in range(self.num_agents):
            a = MoneyAgent(i, self)
            self.schedule.add(a)
        self.datacollector = mesa.DataCollector(
            agent_reporters={"Wealth": "wealth"})

    def step(self):
        self.datacollector.collect(self)
        self.schedule.step()

model = MoneyModel(100)
for _ in range(20):
    model.step()
```

```python
# ===================== NEW: Mesa 3.x (3.4+/3.5 idioms) =====================
import mesa

class MoneyAgent(mesa.Agent):
    def __init__(self, model):
        super().__init__(model)                  # no unique_id
        self.wealth = 1

    def step(self):
        if self.wealth > 0:
            other = self.random.choice(self.model.agents.to_list())
            other.wealth += 1
            self.wealth -= 1

class MoneyModel(mesa.Model):
    def __init__(self, n=100, rng=None):         # kwargs only (SolaraViz/batch_run need it)
        super().__init__(rng=rng)                # REQUIRED; rng recommended (seed= deprecated in 3.5)
        self.num_agents = n
        MoneyAgent.create_agents(self, n)        # auto-registered in self.agents
        self.datacollector = mesa.DataCollector(
            agent_reporters={"Wealth": "wealth"})

    def step(self):
        self.datacollector.collect(self)
        self.agents.shuffle_do("step")           # replaces RandomActivation

model = MoneyModel(n=100, rng=42)
model.run_for(20)                                # or: for _ in range(20): model.step()
print(model.steps, model.time)                   # 20, 20.0
```

---

## 15. Migration checklist (2.x → latest 3.x)

1. **Environment:** Python >= 3.12; `pip install -U "mesa[rec]"` (+ nothing else needed for headless models; viz already included via rec).
2. **Model:** add `super().__init__(seed=seed)` (or `rng=rng`) as the first line; make all init params keyword args; delete `self.schedule = ...`; replace `self.initialize_data_collector(...)`.
3. **Agents:** drop `unique_id` from `__init__`/`super()`/call sites; delete `schedule.add/remove`; use `agent.remove()`.
4. **Step logic:** in `Model.step()`, use `self.agents.shuffle_do("step")` (or the right AgentSet pattern from §4); replace `schedule.steps/time` with `self.steps` (prefer `self.time` for 4.0-readiness).
5. **Space:** keep `mesa.space` as-is for now (works through 3.5), or move to `mesa.discrete_space` (§6.3) to be 4.0-ready.
6. **DataCollector:** consider `agenttype_reporters` for multi-type models.
7. **batch_run:** replace `iterations=n` with `rng=[...n seeds...]` (3.4+); model must accept `rng` kwarg.
8. **Visualization:** rewrite ModularServer code to SolaraViz + SpaceRenderer + `AgentPortrayalStyle` (§9.2); notebook display = trailing `page`; standalone = `solara run app.py`.
9. **Run and fix every `FutureWarning`** — those are the 4.0 removals (seed=, AgentSet indexing, portrayal dicts, Simulators).

---

## 15b. Current-best idioms — the TARGET-CONDITIONED modernization checklist

Applied AFTER the ladder fixes (SKILL.md Step 4). "Current-best" is a function
of the **target**: the best idiom for 3.1 keeps `mesa.space` (discrete_space was
experimental then); the best idiom for 3.3 uses `AgentPortrayalStyle` but not
`run_for`. Read the band for your target, adopt every item whose `since ≤ target`,
and for any item you do **not** adopt, name it in the report with the reason
(pedagogy, behavior risk, or "newer than target"). "Still works" is never a
reason to keep a dated form *within* the band.

### The band table (pick the row for your target)

| Band (targets) | python_pin | Install | Activation | Agent creation | Space | Seeding | Batch | Visualization | Run loop |
|---|---|---|---|---|---|---|---|---|---|
| **2.1–2.4** | 3.11 | `mesa==V` (no extras) | schedulers (`RandomActivation`, …) | loop + `unique_id` + `schedule.add` | `mesa.space` | `self.random`, own seed plumbing | `batch_run(iterations=)` / `BatchRunner` (≤2.2) | ModularServer/CanvasGrid; 2.3+ experimental SolaraViz | `for _ in range(n): model.step()` |
| **3.0** | 3.12 | `mesa[rec]==V` | AgentSet `do/shuffle_do` | **loop** (no `unique_id`; `create_agents` **absent**) | **keep `mesa.space`** (cell_space experimental) | `seed=` | `iterations=` | SolaraViz + `make_space_component` + lowercase portrayal dicts | loop |
| **3.1** | 3.12 | `mesa[rec]==V` | AgentSet | **`create_agents`** (since 3.1) | **keep `mesa.space`** (discrete_space not stable until 3.2) | `seed=` | `iterations=` | as 3.0 | loop |
| **3.2** | 3.12 | `mesa[rec]==V` | AgentSet (+ `groupby/agg`, since 3.0) | `create_agents` | **`mesa.discrete_space`** + `PropertyLayer` | `seed=` | `iterations=` | portrayal dicts + `make_space_component` (**no SpaceRenderer**) | loop |
| **3.3** | 3.12 | `mesa[rec]==V` | AgentSet | `create_agents` | discrete_space | `seed=` | `iterations=` (**`rng=` absent**) | **`SpaceRenderer(model, backend=…).render(agent_portrayal)`** + `AgentPortrayalStyle`/`PropertyLayerStyle` (**no `setup_*` chain — 3.4+**; dicts still current, not best); **no `run_for`** | loop |
| **3.4** | 3.12 | `mesa[rec]==V` | AgentSet | `create_agents` | discrete_space | **`rng=`** recommended (`seed=` still current) | **`batch_run(rng=[…])`** (`iterations` deprecated) | SpaceRenderer **`setup_*` chain** (new in 3.4; portrayal-to-`render()` now warns) + styles; `model.time` exists | loop |
| **3.5** | 3.12 | `mesa[rec]==V` | AgentSet + `.to_list()` for indexing | `create_agents` / `from_dataframe` | discrete_space | **`rng=` end-to-end** (`seed=` deprecated) | `batch_run(rng=)` | SpaceRenderer `setup_*` chain; dicts + `make_space_component` deprecated | **`run_for`/`run_until`/`schedule_*`** |
| **4.0.0a0** (opt-in) | 3.12 | `mesa[rec]==V` | AgentSet | same | discrete_space only (`mesa.space` gone) | `rng=` only | **no `batch_run`** → `Scenario` | styles only | `run_for`; `model.time` (no `model.steps`) |

(`python_pin`/`install` mirror the catalog's per-release fields — the catalog is
the machine source, this table the human view. Legacy `ContinuousSpace` is kept
in **every** 3.x band — no stable replacement through 3.5.1.)

### Checklist items (each stamped with the target it becomes best-practice)

1. **Agent creation** — *since 3.1*: hand loops → `AgentClass.create_agents(model, n, **kwargs)`
   with broadcast kwargs (`cell=random.choices(grid.all_cells.cells, k=n)`). At a
   **3.0** target keep the loop (`create_agents` doesn't exist). May reorder RNG
   draws vs a per-agent loop — statistically equivalent, seeded trajectories may
   shift; report it.
2. **Run loops** — *since 3.5*: `for _ in range(n): model.step()` → `model.run_for(n)`.
   Below 3.5 the explicit loop **is** current-best.
3. **Filtering/aggregation over agents** — *since 3.0*: comprehensions/accumulators
   → `agents.select(pred)`, `agents.agg("wealth", sum)`, `agents.groupby("state").count()`,
   `agents.get/set/map`. Prime DataCollector-reporter candidates.
4. **Multi-type data collection** — *since 3.0* (in `batch_run` *since 3.4.1*):
   shared `agent_reporters` + hasattr guards → `agenttype_reporters={Type: {...}}`.
5. **Seeding** — *`rng=` recommended since 3.4, mandatory since the 3.5 `seed=`
   deprecation*: at **≤3.3** targets `seed=` is current-best — do **not** rewrite to
   `rng=` (it's a 3.4 idiom; forcing it is overshoot). At **3.4+** move `rng=`
   end-to-end (signature, instantiation, batch_run forwarding).
6. **Model signatures** — *since 3.0*: keyword-friendly `__init__` (SolaraViz Reset
   and batch_run instantiate with kwargs only).
7. **Space access** — *cell-centric since 3.2* (discrete_space stable): `agent.cell`,
   `cell.agents`, `cell.neighborhood.select_random_cell()`, `grid.all_cells`,
   `grid.select_random_empty_cell()`. At **3.0–3.1** targets keep `mesa.space` — do
   not adopt experimental cell_space.
8. **Whole-grid numeric work** — *`PropertyLayer` stable since 3.2*: per-cell loops
   that build arrays → `PropertyLayer` / its NumPy interface, when the notebook
   already treats the grid as a matrix (not when the loop is the lesson).
9. **Visualization** — *`SpaceRenderer`+styles since 3.3; `setup_*` chain since 3.4*:
   at **3.3** the form is `SpaceRenderer(model, backend=…).render(agent_portrayal)`
   (the `setup_*` chain does not exist yet — emitting it at 3.3 crashes); at **3.4+**
   use `setup_agents(p)` then `render()`/`draw_agents()` (portrayal-to-`render()`
   warns from 3.4). At 3.3–3.4 portrayal dicts / `make_space_component` are still
   current (not a finding); at **3.5+** the dicts/factory are deprecated so the move
   is mandatory. Below 3.3 the current-best is `make_space_component` + lowercase dicts.
10. **Bulk attribute updates** — *since 3.0*: `for a in agents: a.x = v` → `agents.set("x", v)`.
11. **Agent base class by mobility** — *cell-space since 3.2*: on `discrete_space`,
    pick the base class that matches how the agent moves — this is a "working is not
    updated" case, because a plain movable `CellAgent` *works* for an immobile agent
    but isn't the current-best form:
    - agents that **never move** (grid patches/sites — a `TreePatch`, a `SugarCell`,
      a `GrassPatch`, terrain) → **`FixedAgent`** (immobile; `.cell` settable once);
    - agents that **move** → **`CellAgent`** (read/write `.cell`);
    - agents that move by **compass direction/distance** → **`Grid2DMovingAgent`**
      (adds `move("N", 2)` shorthands).
    Do **not** default every agent to `CellAgent`, and do **not** keep a plain
    `mesa.Agent` on a `discrete_space` grid. (At a **legacy `mesa.space`** target the
    agents stay plain `mesa.Agent` with `.pos` — `FixedAgent`/`CellAgent` only exist
    in the cell space, so this item applies only once §6.3 has moved the model to
    `discrete_space`.) Immobile agents modelled as a `PropertyLayer` instead of
    per-cell `FixedAgent`s is also fine (item 8) — choose by whether the notebook
    treats them as individuals or as a field.

**Pedagogy exception (binding):** when the dated construct is what the surrounding
text or an exercise teaches (a loop walked through line by line, a lambda the
reader must explain), modernize the API calls inside it but keep the construct —
and note it in the report. The lesson outranks the idiom; everything else within
the band gets modernized.

---

## 15c. Downgrades — reading the ladder right-to-left

Triggered when the notebook's era (scanner `era_lower`) is **newer** than the
target (the scanner prints "DOWNGRADE"). The work list is the
**not-yet-introduced** findings: every API newer than the target must be
rewritten to the target-era form. Each registry entry's `replacement` already
states that form. General mapping (newest → target-era):

| Newer API (era) | Target-era form | Since |
|---|---|---|
| `model.run_for(n)` / `run_until` | `for _ in range(n): model.step()` | 3.5 |
| `model.schedule_event/schedule_recurring` | no pre-3.5 equivalent; Simulator classes (3.0–3.4) for event-driven models | 3.5 |
| `agents.to_list()[i]` | `agents[i]` (indexing is current below 3.5) | 3.5 |
| `Agent.from_dataframe(...)` | `create_agents` (3.1+) or an explicit loop | 3.5 |
| `batch_run(rng=[…])` | `batch_run(iterations=n)` | 3.4 |
| `model.time` | `model.steps` (3.0+) / `schedule.time` (2.x) | 3.4 |
| `renderer.setup_agents(p)` chain | `renderer.render(p)` (portrayal arg; current at 3.3) | 3.4 |
| `SpaceRenderer` + `AgentPortrayalStyle` | `make_space_component` + lowercase portrayal dict | 3.3 |
| `mesa.discrete_space` grids + `CellAgent` | `mesa.space` grids + `mesa.Agent`(+`.pos`) — see reverse table below | 3.2 (stable) |
| `AgentClass.create_agents(...)` | explicit `for i in range(n): AgentClass(model, ...)` | 3.1 |
| `super().__init__(rng=...)` model kwarg | `super().__init__(seed=...)` (rng exists 3.0+, but `seed=` is the ≤3.3 band form; both seed `self.random`) — rename the param and every call site | 3.4 (band pref) |
| auto `unique_id` | manual ids (`Agent(unique_id, model)`) only if target < 3.0 | 3.0 |

**`mesa.discrete_space` → `mesa.space` reverse table** (the NEW→OLD inversion of
§6.3 — a full rewrite of every space call, *the largest chunk* of a sub-3.2
downgrade, on par with SolaraViz→ModularServer; never invert §6.3 mechanically):

| NEW `mesa.discrete_space` | OLD `mesa.space` (target < 3.2) |
|---|---|
| `OrthogonalMooreGrid((w,h), torus=…, random=self.random)` | `MultiGrid(w, h, torus)` — **drop `random=`** (`MultiGrid` has no such kwarg; keeping it crashes) |
| `OrthogonalMooreGrid(..., capacity=1, ...)` | `SingleGrid(w, h, torus)` |
| `OrthogonalVonNeumannGrid(...)` | `MultiGrid/SingleGrid(...)` + `moore=False` on neighbor calls |
| `HexGrid(...)` | `HexSingleGrid/HexMultiGrid(...)` |
| `Network(G, random=self.random)` | `NetworkGrid(G)` |
| agent base `CellAgent`/`FixedAgent` | `mesa.Agent`; positions via `.pos` |
| `agent.cell = grid[(x,y)]` (place) | `grid.place_agent(agent, (x,y))` |
| `agent.cell = new_cell` (move) | `grid.move_agent(agent, (x,y))` |
| `agent.cell = grid.select_random_empty_cell()` | `grid.move_to_empty(agent)` |
| `agent.cell = None` / `agent.remove()` | `grid.remove_agent(agent)` |
| `agent.cell.coordinate` | `agent.pos` |
| `cell.neighborhood` / `cell.get_neighborhood(radius=r, include_center=…)` | `grid.get_neighborhood(pos, moore=…, include_center=…, radius=r)` |
| `cell.neighborhood.agents` | `grid.get_neighbors(pos, moore=…, include_center=…)` |
| `cell.agents` | `grid.get_cell_list_contents([pos])` |
| `for cell in grid.all_cells` | `for contents, (x, y) in grid.coord_iter()` |
| `grid.select_random_empty_cell()` / `grid.empties` | `grid.move_to_empty()` / `grid.empties` |

**Honesty caveats (state these per finding in the report):**

- **RNG has no clean reversal.** `model.rng` (numpy `Generator`) is new in 3.0; a
  downgrade past 3.0 must move numpy draws onto `self.random` (stdlib) — a
  **different draw sequence**, so seeded results shift. Say so.
- **`create_agents` → loop reorders draws** (mirror of the upgrade caveat) —
  statistically equivalent, trajectories may shift.
- **SolaraViz → ModularServer is a rewrite, not a mapping** (only for 2.x targets)
  — flag it as the largest chunk, not a line edit.
- **Behavior-preservation is weaker downhill.** Always execute on the pinned
  target and report any seed-trajectory shift.
- **Never move onto experimental modules to satisfy a downgrade.** Targeting 3.1
  keeps `mesa.space`; it does *not* adopt `experimental.cell_space`.

---

## 16. Sources

- Migration guide (canonical): https://mesa.readthedocs.io/latest/migration_guide.html — source file `docs/migration_guide.md` @ `mesa/mesa@main` (retrieved 2026-07-16)
- Release history: https://github.com/mesa/mesa/blob/main/HISTORY.md and https://github.com/projectmesa/mesa/releases (redirects to `mesa/mesa`)
- PyPI (version/extras/Python req): https://pypi.org/project/Mesa/ — 3.5.1, released 2026-03-15
- API references (stable = 3.5.1): https://mesa.readthedocs.io/stable/apis/model.html, https://mesa.readthedocs.io/stable/apis/agent.html, https://mesa.readthedocs.io/stable/apis/discrete_space.html
- Source code (exact signatures) @ tag `v3.5.1`: `mesa/model.py`, `mesa/agent.py`, `mesa/agentset.py`, `mesa/batchrunner.py`, `mesa/datacollection.py`, `mesa/space.py`, `mesa/time/__init__.py`, `mesa/visualization/{__init__,solara_viz,space_renderer,user_param}.py`, `mesa/visualization/components/{__init__,portrayal_components}.py`, `pyproject.toml`
- Official tutorial (viz in Jupyter): `docs/tutorials/6_visualization_basic.ipynb` @ `v3.5.1` (rendered at https://mesa.readthedocs.io/stable/tutorials/6_visualization_basic.html)
- Mesa 3 paper: Ter Hoeven et al., JOSS 2025, https://doi.org/10.21105/joss.07668
- Empirical verification: Mesa 3.5.1 installed under Python 3.14.3; all error messages and NEW-style examples in this document executed successfully on 2026-07-16.
