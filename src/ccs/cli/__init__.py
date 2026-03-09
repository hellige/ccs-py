"""CCS command-line interface."""

from __future__ import annotations

import sys

try:
    import click
except ImportError:
    click = None


def main():
    if click is None:
        print(
            "The ccs CLI requires click. Install with: pip install ccs[cli]",
            file=sys.stderr,
        )
        return 1
    cli()


if click is not None:
    @click.group()
    @click.version_option(package_name="ccs-py")
    def cli():
        """CCS configuration query tool."""

    # Register subcommands — each module decorates @cli.command() on import.
    import ccs.cli.query  # noqa: F401
    import ccs.cli.shell  # noqa: F401
