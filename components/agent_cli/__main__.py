"""Allow: python -m agent_cli ..."""
from .main import main
import asyncio

if __name__ == "__main__":
    asyncio.run(main())
