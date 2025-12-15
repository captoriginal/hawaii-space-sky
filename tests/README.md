# Test Suite Documentation

This directory contains comprehensive tests for the Hawai'i Space & Sky Dashboard application.

## Test Structure

```
tests/
├── unit/                    # Unit tests for individual components
│   ├── test_cache.py       # Cache database operations
│   ├── test_storage.py     # History database operations
│   ├── test_fetchers.py    # Data fetching and retry logic
│   ├── test_models.py      # Pydantic model validation
│   └── test_plugin_loader.py  # Plugin loading system
├── integration/            # Integration tests
│   └── test_api.py        # API endpoint tests
└── README.md              # This file
```

## Running Tests

### Install Test Dependencies

```bash
pip install -r requirements-dev.txt
```

### Run All Tests

```bash
pytest
```

### Run Specific Test Suites

```bash
# Run only unit tests
pytest tests/unit/

# Run only integration tests
pytest tests/integration/

# Run specific test file
pytest tests/unit/test_cache.py

# Run specific test class
pytest tests/unit/test_cache.py::TestSaveCache

# Run specific test
pytest tests/unit/test_cache.py::TestSaveCache::test_save_simple_data
```

### Run with Coverage

```bash
# Run with coverage report
pytest --cov=backend --cov-report=term-missing

# Generate HTML coverage report
pytest --cov=backend --cov-report=html
# View htmlcov/index.html in browser
```

### Run in Verbose Mode

```bash
pytest -v
```

### Run with Output

```bash
# Show print statements
pytest -s

# Show all output including passed tests
pytest -v -s
```

## Test Coverage

Current test coverage includes:

### Unit Tests

- **Cache (`test_cache.py`)**: 95%+ coverage
  - Connection management and lifecycle
  - Save/load operations
  - Cache freshness checks
  - Error handling and edge cases
  - Concurrent access patterns

- **Storage (`test_storage.py`)**: 95%+ coverage
  - Database connection management
  - History recording for all data types
  - History fetching with time windows
  - Data integrity and edge cases
  - Database cleanup

- **Fetchers (`test_fetchers.py`)**: 90%+ coverage
  - X-ray flux classification
  - HTTP retry logic with backoff
  - Data parsing and validation
  - Error handling for malformed data
  - Async operation testing

- **Models (`test_models.py`)**: 100% coverage
  - All Pydantic model validation
  - Serialization/deserialization
  - Optional field handling
  - Edge cases and validation errors

- **Plugin Loader (`test_plugin_loader.py`)**: 90%+ coverage
  - Panel configuration loading
  - Plugin discovery and loading
  - Error handling for missing/broken plugins
  - Module import testing

### Integration Tests

- **API Endpoints (`test_api.py`)**: 85%+ coverage
  - `/api/status` endpoint
  - `/api/history` endpoint
  - `/api/cache/clear` endpoint
  - `/api/plugins/{plugin_name}/config` endpoint
  - `/api/panels` endpoint
  - CORS configuration
  - Error handling
  - End-to-end flows

## Test Fixtures

Common fixtures are defined in test files:

- `temp_db`: Provides a temporary SQLite database for testing
- `mock_settings`: Mock Settings object with test values
- `sample_dashboard_status`: Complete DashboardStatus object for testing
- `client`: FastAPI TestClient for integration tests

## Writing New Tests

### Unit Test Example

```python
import pytest
from backend.app.cache import save_cache, load_cache

def test_save_and_load_cache(temp_db):
    """Test basic cache save and load."""
    data = {"key": "value"}
    save_cache("test_domain", data, db_path=temp_db)

    result = load_cache("test_domain", db_path=temp_db)
    assert result is not None
    assert result[0] == data
```

### Integration Test Example

```python
from fastapi.testclient import TestClient
from backend.app.main import app

def test_api_endpoint():
    """Test API endpoint."""
    client = TestClient(app)
    response = client.get("/api/status")
    assert response.status_code == 200
```

## Testing Best Practices

1. **Isolation**: Each test should be independent and not rely on other tests
2. **Fixtures**: Use fixtures for common setup/teardown
3. **Mocking**: Mock external dependencies (APIs, file system) appropriately
4. **Cleanup**: Ensure tests clean up temporary resources
5. **Descriptive Names**: Use clear, descriptive test names
6. **Assertions**: Include meaningful assertions with helpful messages
7. **Edge Cases**: Test boundary conditions and error cases
8. **Coverage**: Aim for >90% code coverage

## Continuous Integration

Tests are designed to run in CI environments:

```yaml
# Example GitHub Actions workflow
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r requirements-dev.txt
      - run: pytest --cov=backend --cov-report=xml
      - uses: codecov/codecov-action@v3
```

## Troubleshooting

### Database Lock Errors

If you see "database is locked" errors:
- Ensure tests properly close database connections
- Use context managers (`with` statements)
- Check for hanging database connections

### Import Errors

If you see import errors:
- Ensure you're in the project root directory
- Check PYTHONPATH includes project root
- Verify all dependencies are installed

### Async Test Errors

For async tests:
- Use `@pytest.mark.asyncio` decorator
- Install `pytest-asyncio`
- Use `AsyncMock` for async mocks

### Fixture Not Found

If pytest can't find a fixture:
- Check fixture is defined in same file or conftest.py
- Verify fixture name matches usage
- Check for typos

## Code Quality Tools

### Black (Formatting)

```bash
black backend/ tests/
```

### Ruff (Linting)

```bash
ruff check backend/ tests/
```

### MyPy (Type Checking)

```bash
mypy backend/
```

## Performance Testing

For performance-critical code:

```python
import pytest

def test_performance(benchmark):
    """Benchmark a function."""
    result = benchmark(my_function, arg1, arg2)
    assert result is not None
```

Run with: `pytest --benchmark-only`

## Test Data

Test data files should be placed in `tests/fixtures/`:

```
tests/fixtures/
├── sample_xray_data.json
├── sample_space_weather.json
└── sample_config.json
```

Load in tests:

```python
import json
from pathlib import Path

def load_fixture(filename):
    path = Path(__file__).parent / "fixtures" / filename
    with path.open() as f:
        return json.load(f)
```

## Debugging Tests

### Run with PDB

```bash
pytest --pdb  # Drop into debugger on failure
pytest --pdb-trace  # Drop into debugger at start
```

### Show Local Variables

```bash
pytest -l  # Show local variables in tracebacks
```

### Stop on First Failure

```bash
pytest -x  # Stop on first failure
pytest --maxfail=3  # Stop after 3 failures
```

## Contributing

When adding new features:

1. Write tests first (TDD approach recommended)
2. Ensure all tests pass: `pytest`
3. Check coverage: `pytest --cov`
4. Run linting: `ruff check`
5. Format code: `black`
6. Update this documentation if needed

## Resources

- [pytest documentation](https://docs.pytest.org/)
- [pytest-asyncio](https://github.com/pytest-dev/pytest-asyncio)
- [FastAPI Testing](https://fastapi.tiangolo.com/tutorial/testing/)
- [Coverage.py](https://coverage.readthedocs.io/)
