#!/bin/bash
# Test runner script for Hawai'i Space & Sky Dashboard

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Hawai'i Space & Sky Dashboard - Test Suite${NC}"
echo "============================================"
echo ""

# Check if virtual environment is activated
if [[ -z "${VIRTUAL_ENV}" ]]; then
    echo -e "${YELLOW}Warning: Virtual environment not activated${NC}"
    echo "Consider running: source .venv/bin/activate"
    echo ""
fi

# Check if test dependencies are installed
if ! python -c "import pytest" 2>/dev/null; then
    echo -e "${RED}Error: pytest not found${NC}"
    echo "Install test dependencies with: pip install -r requirements-dev.txt"
    exit 1
fi

# Parse command line arguments
MODE="all"
COVERAGE=true
VERBOSE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --unit)
            MODE="unit"
            shift
            ;;
        --integration)
            MODE="integration"
            shift
            ;;
        --no-coverage)
            COVERAGE=false
            shift
            ;;
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -h|--help)
            echo "Usage: ./run_tests.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --unit           Run only unit tests"
            echo "  --integration    Run only integration tests"
            echo "  --no-coverage    Skip coverage report"
            echo "  -v, --verbose    Verbose output"
            echo "  -h, --help       Show this help message"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Run with --help for usage information"
            exit 1
            ;;
    esac
done

# Build pytest command
PYTEST_CMD="pytest"

# Add path based on mode
case $MODE in
    unit)
        echo "Running unit tests only..."
        PYTEST_CMD="$PYTEST_CMD tests/unit/"
        ;;
    integration)
        echo "Running integration tests only..."
        PYTEST_CMD="$PYTEST_CMD tests/integration/"
        ;;
    all)
        echo "Running all tests..."
        PYTEST_CMD="$PYTEST_CMD tests/"
        ;;
esac

# Add coverage if enabled
if [ "$COVERAGE" = true ]; then
    PYTEST_CMD="$PYTEST_CMD --cov=backend --cov-report=term-missing --cov-report=html"
fi

# Add verbose if enabled
if [ "$VERBOSE" = true ]; then
    PYTEST_CMD="$PYTEST_CMD -v"
fi

# Run the tests
echo ""
echo "Command: $PYTEST_CMD"
echo ""

if $PYTEST_CMD; then
    echo ""
    echo -e "${GREEN}✓ All tests passed!${NC}"

    if [ "$COVERAGE" = true ]; then
        echo ""
        echo "Coverage report generated in htmlcov/index.html"
    fi

    exit 0
else
    echo ""
    echo -e "${RED}✗ Tests failed${NC}"
    exit 1
fi
