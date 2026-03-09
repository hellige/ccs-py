"""The 'ccs dump' command."""

from __future__ import annotations

from pathlib import Path

import click
import pyrsistent

from ccs.cli import cli
from ccs.cli._util import apply_context_specs, load_context
from ccs.dump import dump_dag


@cli.command()
@click.argument("file", type=click.Path(exists=True, dir_okay=False))
@click.argument("properties", nargs=-1)
@click.option(
    "-c", "--context", "contexts", multiple=True,
    help="Context constraint: KEY or KEY.VALUE (repeatable).",
)
def dump(file, properties, contexts):
    """Canonical dump of rules from a CCS file.

    Loads FILE, applies context constraints, and prints a canonical
    representation of all matching rules. If PROPERTIES are specified,
    only rules setting those properties are shown.
    """
    file_path = Path(file).resolve()
    ctx = load_context(file_path)
    # Enable closed-world assumption so dump reflects context.
    ctx.poisoned = pyrsistent.s()
    ctx = apply_context_specs(ctx, contexts)

    dump_dag(ctx, properties or None)
