import pytest
from io import StringIO
from pathlib import Path

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
    """Parse selector string into a list of (key, value) augment steps.

    Each space-separated token is one augment call. A dot separates
    key from value: 'a.b' is augment("a", "b"), 'a' is augment("a").

    Examples:
        'a.b'     -> [('a', 'b')]
        'a.b c.d' -> [('a', 'b'), ('c', 'd')]
        'a'       -> [('a', None)]
    """
    if not selector_str:
        return []
    steps = []
    for token in selector_str.split():
        parts = token.split(".", 1)
        name = parts[0]
        value = parts[1] if len(parts) > 1 else None
        steps.append((name, value))
    return steps


def apply_selector(ctx, selector_str):
    """Apply parsed selector steps to a Context, return augmented Context."""
    for name, value in parse_selector(selector_str):
        ctx = ctx.augment(name, value)
    return ctx


TESTS_PATH = Path(__file__).parent / "acceptance_tests.txt"
cases = parse_tests(TESTS_PATH) if TESTS_PATH.exists() else []


@pytest.mark.parametrize("name, ccs, assertions", cases, ids=[c[0] for c in cases])
def test_acceptance(name, ccs, assertions):
    ctx = Context.from_ccs_stream(StringIO(ccs), name)
    for selector, prop, expected in assertions:
        augmented = apply_selector(ctx, selector)
        assert augmented.get_single_value(prop) == expected
