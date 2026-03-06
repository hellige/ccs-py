import pytest
from io import StringIO
from collections import deque
from pathlib import Path

from ccs.dag import Key
from ccs.search_state import Context


def parse_tests(path):
    """Parse tests.txt into [(name, ccs, [(selector, prop, value)])]."""
    text = Path(path).read_text()
    cases = []
    for block in text.split("==="):
        block = block.strip()
        if not block:
            continue
        parts = block.split("---")
        assert len(parts) == 3, f"Expected 3 sections, got {len(parts)} in: {block[:60]}"
        name = parts[0].strip()
        ccs = parts[1].strip()
        assertions = []
        for line in parts[2].strip().splitlines():
            line = line.strip()
            if not line:
                continue
            if ":" in line:
                selector_part, rest = line.split(":", 1)
                prop_part, value_part = rest.split("=", 1)
                assertions.append(
                    (selector_part.strip(), prop_part.strip(), value_part.strip())
                )
            else:
                prop_part, value_part = line.split("=", 1)
                assertions.append(("", prop_part.strip(), value_part.strip()))
        cases.append((name, ccs, assertions))
    return cases


def parse_selector(selector_str):
    """Parse selector string into list of steps.

    Each step is a list of (key, value) pairs to apply simultaneously.

    Examples:
        'a.b'       -> [[('a', 'b')]]
        'a.b.c'     -> [[('a', 'b'), ('a', 'c')]]
        'a.b c.d'   -> [[('a', 'b')], [('c', 'd')]]
        'a.b.c/d.e' -> [[('a', 'b'), ('a', 'c'), ('d', 'e')]]
        'a'         -> [[('a', None)]]
    """
    if not selector_str:
        return []
    steps = []
    for step_str in selector_str.split():
        step_keys = []
        for segment in step_str.split("/"):
            parts = segment.split(".")
            name = parts[0]
            values = parts[1:]
            if values:
                for v in values:
                    step_keys.append((name, v))
            else:
                step_keys.append((name, None))
        steps.append(step_keys)
    return steps


def apply_selector(ctx, selector_str):
    """Apply parsed selector steps to a Context, return augmented Context."""
    for step_keys in parse_selector(selector_str):
        if len(step_keys) == 1:
            name, value = step_keys[0]
            ctx = ctx.augment(name, value)
        else:
            keys = deque(Key(name, {value}) for name, value in step_keys)
            changes = ctx._augment(keys)
            ctx = Context(
                ctx.dag,
                ctx.prop_accumulator,
                **changes,
                trace_properties=ctx.trace_properties,
            )
    return ctx


TESTS_PATH = Path(__file__).parent / "acceptance_tests.txt"
cases = parse_tests(TESTS_PATH) if TESTS_PATH.exists() else []


@pytest.mark.parametrize("name, ccs, assertions", cases, ids=[c[0] for c in cases])
def test_acceptance(name, ccs, assertions):
    ctx = Context.from_ccs_stream(StringIO(ccs), name)
    for selector, prop, expected in assertions:
        augmented = apply_selector(ctx, selector)
        assert augmented.get_single_value(prop) == expected
