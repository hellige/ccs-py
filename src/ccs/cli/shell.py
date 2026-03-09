"""The 'ccs shell' interactive REPL command."""

from __future__ import annotations

from pathlib import Path

import click
import pyrsistent

from ccs.cli import cli
from ccs.cli._util import apply_context_specs, load_context, parse_context_steps
from ccs.dump import dump_dag
from ccs.error import AmbiguousPropertyError, MissingPropertyError
from ccs.search_state import suggest_context

try:
    from prompt_toolkit import PromptSession
    from prompt_toolkit.completion import Completer, Completion
    HAS_PROMPT_TOOLKIT = True
except ImportError:
    HAS_PROMPT_TOOLKIT = False


COMMANDS = ["add", "pop", "drop", "context", "reset", "save", "load",
            "get", "props", "dump", "suggest", "help", "quit", "exit"]


def _context_path(ctx):
    """Format the current context path for display."""
    if len(ctx.debug_location) == 0:
        return ""
    parts = [str(key) for key in ctx.debug_location]
    return " > ".join(parts)


def _make_prompt(ctx):
    path = _context_path(ctx)
    if path:
        return f"ccs [{path}]> "
    return "ccs> "


class ShellState:
    """Mutable state for the REPL session."""

    def __init__(self, root_ctx):
        self.root_ctx = root_ctx
        self.ctx = root_ctx
        self.history = []  # stack for pop
        self.saved = {}    # name -> (ctx, history)


class CcsCompleter(Completer):
    """Tab completer for the CCS shell."""

    def __init__(self, state: ShellState):
        self.state = state

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        words = text.split()

        if len(words) == 0 or (len(words) == 1 and not text.endswith(" ")):
            # completing the command name
            prefix = words[0] if words else ""
            for cmd in COMMANDS:
                if cmd.startswith(prefix):
                    yield Completion(cmd, start_position=-len(prefix))
            return

        cmd = words[0]
        # completing the argument
        if text.endswith(" "):
            arg_prefix = ""
        else:
            arg_prefix = words[-1]

        if cmd in ("get", "dump"):
            # handle -a flag for get
            if cmd == "get" and arg_prefix == "-":
                yield Completion("-a", start_position=-1)
                return
            for prop_name in sorted(self.state.ctx.props.keys()):
                if prop_name.startswith(arg_prefix):
                    yield Completion(prop_name, start_position=-len(arg_prefix))

        elif cmd == "add":
            dot = arg_prefix.find(".")
            if dot == -1:
                # completing key name
                for key_name in sorted(self.state.ctx.dag.children.keys()):
                    if key_name.startswith(arg_prefix):
                        yield Completion(key_name, start_position=-len(arg_prefix))
            else:
                # completing key.value
                key_name = arg_prefix[:dot]
                val_prefix = arg_prefix[dot + 1:]
                if key_name in self.state.ctx.dag.children:
                    matcher = self.state.ctx.dag.children[key_name]
                    for value in sorted(matcher.positive_values.keys()):
                        if value.startswith(val_prefix):
                            yield Completion(
                                f"{key_name}.{value}",
                                start_position=-len(arg_prefix),
                            )

        elif cmd == "load":
            for name in sorted(self.state.saved.keys()):
                if name.startswith(arg_prefix):
                    yield Completion(name, start_position=-len(arg_prefix))

        elif cmd == "drop":
            seen_keys = set()
            for key in self.state.ctx.debug_location:
                seen_keys.add(key.name)
            for key_name in sorted(seen_keys):
                if key_name.startswith(arg_prefix):
                    yield Completion(key_name, start_position=-len(arg_prefix))


def _cmd_add(state, arg):
    if not arg:
        click.echo("Usage: add KEY[.VALUE] ...", err=True)
        return
    try:
        keys = parse_context_steps(arg)
    except click.ClickException as e:
        click.echo(str(e), err=True)
        return
    if not keys:
        return
    state.history.append(state.ctx)
    for key in keys:
        value = next(iter(key.values), None)
        state.ctx = state.ctx.augment(key.name, value)


def _cmd_pop(state, arg):
    if not state.history:
        click.echo("Nothing to pop.", err=True)
        return
    state.ctx = state.history.pop()


def _cmd_drop(state, arg):
    if not arg:
        click.echo("Usage: drop KEY", err=True)
        return
    # Rebuild context by replaying all augments except the one matching this key
    specs = []
    found = False
    for key in state.ctx.debug_location:
        if key.name == arg and not found:
            found = True
            continue
        value = next(iter(key.values), None)
        specs.append((key.name, value))
    if not found:
        click.echo(f"Key '{arg}' not in current context.", err=True)
        return
    ctx = state.root_ctx
    for key_name, value in specs:
        ctx = ctx.augment(key_name, value)
    state.ctx = ctx
    state.history.clear()


def _cmd_context(state, arg):
    path = _context_path(state.ctx)
    if path:
        click.echo(f"[{path}]")
    else:
        click.echo("<root>")


def _cmd_reset(state, arg):
    state.ctx = state.root_ctx
    state.history.clear()


def _cmd_save(state, arg):
    if not arg:
        click.echo("Usage: save NAME", err=True)
        return
    state.saved[arg] = (state.ctx, list(state.history))
    click.echo(f"Saved context as '{arg}'.")


def _cmd_load(state, arg):
    if not arg:
        click.echo("Usage: load NAME", err=True)
        return
    if arg not in state.saved:
        click.echo(f"No saved context '{arg}'. Available: {', '.join(sorted(state.saved)) or '(none)'}", err=True)
        return
    state.ctx, state.history = state.saved[arg]
    state.history = list(state.history)  # copy so saves are independent


def _cmd_get(state, arg):
    if not arg:
        click.echo("Usage: get [-a] PROPERTY", err=True)
        return
    parts = arg.split(None, 1)
    show_all = False
    prop = arg
    if parts[0] == "-a":
        show_all = True
        if len(parts) < 2:
            click.echo("Usage: get -a PROPERTY", err=True)
            return
        prop = parts[1]

    if show_all:
        accum = state.ctx.props.get(prop, None)
        if accum is None:
            click.echo(f"{prop}: <not set>", err=True)
        else:
            for p, specificity in accum.values:
                click.echo(f"{prop} = {p.value}  (specificity: {specificity}, origin: {p.origin})")
    else:
        try:
            p = state.ctx.get_single_property(prop)
            click.echo(f"{prop} = {p.value}  (origin: {p.origin})")
        except MissingPropertyError:
            click.echo(f"{prop}: <not set>", err=True)
        except AmbiguousPropertyError as e:
            click.echo(f"{prop}: {e}", err=True)


def _cmd_props(state, arg):
    if not state.ctx.props:
        click.echo("No properties set.")
        return
    for name in sorted(state.ctx.props.keys()):
        try:
            p = state.ctx.get_single_property(name)
            click.echo(f"{name} = {p.value}")
        except AmbiguousPropertyError:
            click.echo(f"{name} = <ambiguous>")


def _cmd_dump(state, arg):
    dump_dag(state.ctx, arg or None)


def _cmd_suggest(state, arg):
    suggestions = suggest_context(state.ctx)
    if not suggestions:
        click.echo("No suggestions — all reachable properties are already set.")
        return
    for key_name, value, new_props in suggestions:
        spec = f"{key_name}.{value}" if value else key_name
        props_str = ", ".join(sorted(new_props))
        click.echo(f"  add {spec}  ->  {props_str}")


def _cmd_help(state, arg):
    click.echo("""Context manipulation:
  add KEY[.VALUE] ...  Augment context (push onto stack)
  pop               Undo last add
  drop KEY          Remove context element, rebuild context
  context           Show current context path
  reset             Return to root context
  save NAME         Save current context as bookmark
  load NAME         Switch to a saved context

Property queries:
  get PROPERTY      Query single property (value + origin)
  get -a PROPERTY   Show all matching values with specificities
  props             List all currently set properties
  dump [PROPERTY]   Canonical dump of all (or one) property
  suggest           List context elements that would add properties

Meta:
  help              Show this help
  quit / exit       Exit shell (also Ctrl-D)""")


DISPATCH = {
    "add": _cmd_add,
    "pop": _cmd_pop,
    "drop": _cmd_drop,
    "context": _cmd_context,
    "reset": _cmd_reset,
    "save": _cmd_save,
    "load": _cmd_load,
    "get": _cmd_get,
    "props": _cmd_props,
    "dump": _cmd_dump,
    "suggest": _cmd_suggest,
    "help": _cmd_help,
}


def _run_repl(state):
    """Run the REPL loop."""
    if HAS_PROMPT_TOOLKIT:
        completer = CcsCompleter(state)
        session = PromptSession(completer=completer)
        def read_input(prompt):
            return session.prompt(prompt)
    else:
        click.echo("(prompt_toolkit not installed — no tab completion. "
                    "Install with: pip install ccs[cli])")
        def read_input(prompt):
            return input(prompt)

    while True:
        try:
            line = read_input(_make_prompt(state.ctx))
        except (EOFError, KeyboardInterrupt):
            click.echo()
            break

        line = line.strip()
        if not line:
            continue

        parts = line.split(None, 1)
        cmd = parts[0]
        arg = parts[1] if len(parts) > 1 else ""

        if cmd in ("quit", "exit"):
            break

        handler = DISPATCH.get(cmd)
        if handler is None:
            click.echo(f"Unknown command: {cmd}. Type 'help' for available commands.", err=True)
            continue

        handler(state, arg)


@cli.command()
@click.argument("file", type=click.Path(exists=True, dir_okay=False))
@click.option(
    "-c", "--context", "contexts", multiple=True,
    help="Initial context constraint: KEY or KEY.VALUE (repeatable).",
)
def shell(file, contexts):
    """Interactive shell for exploring a CCS configuration.

    Loads FILE and enters an interactive REPL where you can incrementally
    build context, query properties, view canonical dumps, and discover
    what context elements would activate additional properties.
    """
    file_path = Path(file).resolve()
    root_ctx = load_context(file_path, show_all=True)
    # Enable closed-world assumption so dump/suggest reflect current context.
    root_ctx.poisoned = pyrsistent.s()

    state = ShellState(root_ctx)
    if contexts:
        state.ctx = apply_context_specs(state.ctx, contexts)
        # Record initial context in history so pop works
        state.history.append(root_ctx)

    _run_repl(state)
