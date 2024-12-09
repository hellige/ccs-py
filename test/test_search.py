from io import StringIO


from ccs.dag import build_dag
from ccs.error import AmbiguousPropertyError, MissingPropertyError
from ccs.parser import Parser
from ccs.rule_tree import RuleTreeNode
from ccs.search_state import Context


def expect_exception(work, expected):
    try:
        work()
    except expected:
        pass
    else:
        raise AssertionError(f"Expected exception {expected} did not happen")


def load_context(expr: str) -> Context:
    return Context.from_ccs_stream(StringIO(expr), "-")


def test_get_single_value():
    ctx = load_context(
        """
        a = 1
        a = 2

        c = 4.3
        d = "cannotcast"
        """
    )

    expect_exception(lambda: ctx.get_single_value("a"), AmbiguousPropertyError)
    expect_exception(lambda: ctx.get_single_value("b"), MissingPropertyError)

    assert 4.3 == ctx.get_single_value("c", cast=float)

    expect_exception(lambda: ctx.get_single_value("d", cast=float), ValueError)


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
