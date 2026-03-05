# flowManager
orchestrates LLM agents to build complex software

## 🧪 Testing

We maintain a rigorous test suite comprising **fast** and **slow** unit tests, plus integration and quality gates.

### Test Structure

| Directory | Contents | Speed |
|:---|:---|:---:|
| `tests/unit/` | Core logic — domain, engine, tools, atoms, llm, skills | ~8 s |
| `tests/unit_slow/` | Threading, timeouts, stress, concurrency tests | ~40 s |
| `tests/integration/` | End-to-end lifecycle verification | varies |
| `tests/quality/` | Black, Isort, complexity constraints | ~2 s |

### Running Tests

Both runners accept **combinable flags** — use one, the other, or both:

#### PowerShell

```powershell
.\scripts\run_suite.ps1              # fast only (default)
.\scripts\run_suite.ps1 -Fast        # fast only
.\scripts\run_suite.ps1 -Slow        # slow only
.\scripts\run_suite.ps1 -Fast -Slow  # all tests
```

#### Bash

```bash
./scripts/run_suite.sh               # fast only (default)
./scripts/run_suite.sh --fast        # fast only
./scripts/run_suite.sh --slow        # slow only
./scripts/run_suite.sh --fast --slow # all tests
./scripts/run_suite.sh --all         # all tests (shortcut)
```

Both scripts run `pytest`, parse the JUnit XML report, and print a colour-coded summary table grouped by package.

### Manual Execution

```bash
poetry run pytest tests/unit                    # fast tests
poetry run pytest tests/unit_slow               # slow tests
poetry run pytest tests/unit tests/unit_slow    # all unit tests
poetry run pytest tests/integration             # integration tests
poetry run pytest tests/quality                 # quality gates
```

### Quality Standards

If quality tests fail, auto-fix with:

```bash
poetry run black .
poetry run isort .
```
