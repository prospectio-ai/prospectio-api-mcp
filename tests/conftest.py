"""Root conftest - loads .env before any test imports."""
from dotenv import load_dotenv

load_dotenv()

# Register external mock fixtures so they are available in all tests
pytest_plugins = ["tests.fixtures.external"]
