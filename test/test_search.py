from io import StringIO

from ccs.dag import build_dag
from ccs.dnf import to_dnf
from ccs.parser import Parser
from ccs.rule_tree import RuleTreeNode
from ccs.search_state import Context


def get_value(ctx: Context, prop: str) -> str:
    return next(iter(ctx.props[prop].values)).value


def test_with_root_node():
    expr = """
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
    """

    root = RuleTreeNode()
    n = Parser().parse(StringIO(expr), "-")
    n.add_to(root)

    dag = build_dag(root)
    ctx = Context(dag)

    assert get_value(ctx, "baz") == "outerbaz"

    in_a = ctx.augment("a")
    assert get_value(in_a, "baz") == "quux"

    assert get_value(ctx, "x") == "outerx"

    in_c = ctx.augment("c")
    assert get_value(in_c, "x") == "outerx"

    in_cd = in_c.augment("d")
    assert get_value(in_cd, "x") == "y"

    assert get_value(in_cd, "noothers") == "val"

    assert get_value(ctx, "c") == "success"
