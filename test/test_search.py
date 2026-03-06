import re
from io import StringIO
import pytest

from ccs.error import AmbiguousPropertyError, MissingPropertyError
from ccs.search_state import Context, StrictMaxAccumulator


def expect_exception(work, expected):
    try:
        work()
    except expected:
        pass
    else:
        raise AssertionError(f"Expected exception {expected} did not happen")


def load_context(expr: str, *args, **kwargs) -> Context:
    return Context.from_ccs_stream(StringIO(expr), "-", *args, **kwargs)


def test_get_single_value():
    ctx = load_context(
        """
        a = 1
        a = 2

        c = 4.3
        d = "cannotcast"
        """
    )

    # source-order tie-breaking: last writer wins
    assert ctx.get_single_value("a") == "2"

    with pytest.raises(MissingPropertyError):
        ctx.get_single_value("b")

    assert 4.3 == ctx.get_single_value("c", cast=float)

    with pytest.raises(ValueError):
        ctx.get_single_value("d", cast=float)


def test_with_root_node():
    ctx = load_context(
        """
        a, f b e, c {
          c d {
            x = y
          }
          e f {
            foobar = abc
          }
        }
        a, c, b e f : baz = quux

        x = outerx
        baz = outerbaz
        foobar = outerfoobar
        noothers = val
        
        multi {
            x = failure
            level {
                x = success
            }
        }

        z.underconstraint {
            c = success
        }
        @constrain z.underconstraint
        c = failure
        
        """
    )

    assert ctx.get_single_value("baz") == "outerbaz"

    in_a = ctx.augment("a")
    assert in_a.get_single_value("baz") == "quux"

    assert ctx.get_single_value("x") == "outerx"

    in_c = ctx.augment("c")
    assert in_c.get_single_value("x") == "outerx"

    in_cd = in_c.augment("d")
    assert in_cd.get_single_value("x") == "y"

    assert in_cd.get_single_value("noothers") == "val"

    assert ctx.get_single_value("c") == "success"

    lvl1 = ctx.augment("multi")
    lvl2 = lvl1.augment("level")
    assert lvl2.get_single_value("x")


def test_strict_max_accumulator():
    ctx = load_context(
        """
        a = 1
        a = 2
        """,
        prop_accumulator=StrictMaxAccumulator,
    )

    with pytest.raises(AmbiguousPropertyError):
        ctx.get_single_value("a")


def test_import():
    files = {
        "main.ccs": '@import "helpers.ccs"\nbaz.bar: frob = "nitz"',
        "helpers.ccs": 'foo.bar: x = "imported"',
    }

    class Resolver:
        def resolve(self, location):
            return StringIO(files[location])

    ctx = Context.from_ccs_stream(
        StringIO(files["main.ccs"]), "main.ccs", Resolver()
    )
    assert ctx.augment("foo", "bar").get_single_value("x") == "imported"
    assert ctx.augment("baz", "bar").get_single_value("frob") == "nitz"


def test_import_source_order():
    """Imported properties participate in source-order tie-breaking."""
    files = {
        "main.ccs": 'a: test = "first"\n@import "other.ccs"',
        "other.ccs": 'a: test = "second"',
    }

    class Resolver:
        def resolve(self, location):
            return StringIO(files[location])

    ctx = Context.from_ccs_stream(
        StringIO(files["main.ccs"]), "main.ccs", Resolver()
    )
    # imported file comes after "first", so "second" wins
    assert ctx.augment("a").get_single_value("test") == "second"


def test_import_source_order_sandwich():
    """Property after import wins over imported property."""
    files = {
        "main.ccs": 'a: test = "first"\n@import "other.ccs"\na: test = "third"',
        "other.ccs": 'a: test = "second"',
    }

    class Resolver:
        def resolve(self, location):
            return StringIO(files[location])

    ctx = Context.from_ccs_stream(
        StringIO(files["main.ccs"]), "main.ccs", Resolver()
    )
    # "third" comes last in source order
    assert ctx.augment("a").get_single_value("test") == "third"


def test_context():
    ctx = load_context(
        """
        @context (a)
        test = 'in_a'
        b: test = 'in_ab'
        """
    )

    # @context (a) wraps everything under a, so root has no properties
    with pytest.raises(MissingPropertyError):
        ctx.get_single_value("test")

    # augmenting with a activates the context
    in_a = ctx.augment("a")
    assert in_a.get_single_value("test") == "in_a"

    # further augmentation works within the context
    in_ab = in_a.augment("b")
    assert in_ab.get_single_value("test") == "in_ab"


def test_context_independence():
    """Augmenting one branch does not affect sibling branches."""
    ctx = load_context(
        """
        a { x = 'in_a' }
        b { x = 'in_b' }
        """
    )

    branch_a = ctx.augment("a")
    branch_b = ctx.augment("b")
    assert branch_a.get_single_value("x") == "in_a"
    assert branch_b.get_single_value("x") == "in_b"

    # augmenting branch_a further doesn't affect branch_b
    branch_a.augment("b")
    assert branch_b.get_single_value("x") == "in_b"

    # original context is also unchanged
    with pytest.raises(MissingPropertyError):
        ctx.get_single_value("x")


def test_trace_properties():
    logged = []

    def debug_trace(fmt, *args):
        logged.append(fmt % args)

    ctx = load_context(
        """
        a {
            b {
                c = "42"
            }
        }
        c = 101
        """,
        trace_properties=debug_trace,
    )

    assert ctx.get_single_value("c", cast=int) == 101
    assert re.match(r".*c = 101.*\n.*\[<root>\]", logged[-1], re.MULTILINE)

    in_a = ctx.augment("a")
    assert in_a.get_single_value("c", cast=int) == 101
    assert re.match(r".*c = 101.*\n.*\[a\]", logged[-1], re.MULTILINE)

    in_b = ctx.augment("b")
    assert in_b.get_single_value("c", cast=int) == 101
    assert re.match(r".*c = 101.*\n.*\[b\]", logged[-1], re.MULTILINE)

    in_ab = in_a.augment("b")
    assert in_ab.get_single_value("c", cast=int) == 42
    assert re.match(r".*c = 42.*\n.*\[a > b\]", logged[-1], re.MULTILINE)
