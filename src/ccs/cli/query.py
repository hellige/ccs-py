"""The 'ccs query' command."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from ccs.cli import cli
from ccs.cli._util import apply_context_specs, load_context
from ccs.error import AmbiguousPropertyError, MissingPropertyError


@cli.command()
@click.argument("file", type=click.Path(exists=True, dir_okay=False))
@click.argument("properties", nargs=-1, required=True)
@click.option(
    "-c", "--context", "contexts", multiple=True,
    help="Context constraint: KEY or KEY.VALUE (repeatable).",
)
@click.option(
    "-a", "--all", "show_all", is_flag=True, default=False,
    help="Show all matching values with specificities (uses SetAccumulator).",
)
@click.option(
    "-t", "--trace", is_flag=True, default=False,
    help="Enable property tracing (prints origin and context path to stderr).",
)
def query(file, properties, contexts, show_all, trace):
    """Query properties from a CCS file.

    Loads FILE, applies context constraints, and prints the requested PROPERTIES.
    """
    file_path = Path(file).resolve()
    ctx = load_context(file_path, show_all=show_all, trace=trace)
    ctx = apply_context_specs(ctx, contexts)

    errors = False
    for prop in properties:
        if show_all:
            accum = ctx.props.get(prop, None)
            if accum is None:
                click.echo(f"{prop}: <not set>", err=True)
                errors = True
            else:
                for p, specificity in accum.values:
                    click.echo(f"{prop} = {p.value}  (specificity: {specificity}, origin: {p.origin})")
        else:
            try:
                value = ctx.get_single_value(prop)
                click.echo(f"{prop} = {value}")
            except MissingPropertyError:
                click.echo(f"{prop}: <not set>", err=True)
                errors = True
            except AmbiguousPropertyError as e:
                click.echo(f"{prop}: {e}", err=True)
                errors = True

    if errors:
        sys.exit(1)
