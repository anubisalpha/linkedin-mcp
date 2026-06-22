import asyncio

from .server import main as _async_main


def main() -> None:
    asyncio.run(_async_main())


if __name__ == "__main__":
    main()
