"""Shared CLI utilities."""

from __future__ import annotations

import io
import sys
from pathlib import Path
from typing import TextIO

import click

from ccs.dag import Key
from ccs.parser import Lexer, Token, ParseError
from ccs.search_state import Context, SetAccumulator


class FileImportResolver:
    """Resolves @import paths relative to the directory containing the importing file."""

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir

    def resolve(self, location: str) -> TextIO:
        return open(self.base_dir / location)


def parse_context_steps(text: str) -> list[Key]:
    """Parse context specs using real CCS lexing rules.

    Accepts one or more steps like: env.prod node.foo 'weird key'."weird val"
    Returns a list of Key objects.

    Raises click.ClickException on parse errors.
    """
    lex = Lexer(io.StringIO(text))
    keys = []
    try:
        while lex.peek().type is not Token.EOS:
            tok = lex.consume()
            if tok.type == Token.IDENT:
                name = tok.value
            elif tok.type == Token.STRING:
                name = tok.string_value.str()
            else:
                raise click.ClickException(
                    f"Expected identifier or string, got {tok.type}"
                )
            values = set()
            if lex.peek().type is Token.DOT:
                lex.consume()
                vtok = lex.consume()
                if vtok.type == Token.IDENT:
                    values.add(vtok.value)
                elif vtok.type == Token.STRING:
                    values.add(vtok.string_value.str())
                else:
                    raise click.ClickException(
                        f"Expected identifier or string after '.', got {vtok.type}"
                    )
            keys.append(Key(name, values))
    except ParseError as e:
        raise click.ClickException(str(e))
    return keys


def load_context(
    file_path: Path,
    *,
    show_all: bool = False,
    trace: bool = False,
) -> Context:
    """Load a CCS file and return a root Context.

    Raises click.ClickException on failure.
    """
    resolver = FileImportResolver(file_path.parent)

    tracer = None
    if trace:
        def tracer(fmt, *args):
            print(fmt % args, file=sys.stderr)

    kwargs = {}
    if show_all:
        kwargs["prop_accumulator"] = SetAccumulator
    if tracer:
        kwargs["trace_properties"] = tracer

    try:
        with open(file_path) as f:
            return Context.from_ccs_stream(f, str(file_path), resolver, **kwargs)
    except Exception as e:
        raise click.ClickException(f"Failed to load {file_path}: {e}") from e


def apply_context_specs(ctx: Context, specs: tuple[str, ...]) -> Context:
    """Apply a sequence of context specs (from -c flags) to a Context."""
    for spec in specs:
        for key in parse_context_steps(spec):
            value = next(iter(key.values), None)
            ctx = ctx.augment(key.name, value)
    return ctx
