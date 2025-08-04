"""Make cosmoserver runnable as a module with python -m cosmoserver.cli"""

from .cli import cli_main

if __name__ == "__main__":
    cli_main()
