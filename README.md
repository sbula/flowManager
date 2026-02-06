# flowManager
orchestrates LLM agents to build complex software

## 🧪 Testing

We maintain a rigorous test suite comprising Unit, Integration, and Quality standard tests.

### Running Tests (Recommended)

Use the dedicated PowerShell script to run the full suite and view a summary report:

```powershell
powershell scripts/run_suite.ps1
```

This script will:
1. Execute `pytest` with coverage and reporting enabled.
2. Check for Unit, Integration, and Quality (Linting/Formatting) failures.
3. Generate a summarized table of results by package.

### Manual Execution

You can also run tests manually using `poetry`:

```bash
# Run all tests
poetry run pytest

# Run specific category
poetry run pytest tests/unit
poetry run pytest tests/integration
poetry run pytest tests/quality
```

### Test Structure

*   **`tests/unit`**: Isolated tests for Domain and Engine logic.
*   **`tests/integration`**: End-to-end lifecycle verification (Hydration -> Persistence).
*   **`tests/quality`**: Enforces standards (Black, Isort, Complexity constraints).

### Quality Standards

If Quality tests fail, you can fix most issues automatically:

```bash
poetry run black .
poetry run isort .
```
