import io

from ccs.ast import flatten
from ccs.parser import Parser


def parse_expr(string: str):
    return Parser().parse_selector(io.StringIO(string))


def test_flatten_and():
    sel = "(a b) (c d)"
    assert str(parse_expr(sel)) == "(AND (AND a b) (AND c d))"
    assert str(flatten(parse_expr(sel))) == "(AND a b c d)"


def test_flatten_or():
    sel = "(a, b), (c, d)"
    assert str(parse_expr(sel)) == "(OR (OR a b) (OR c d))"
    assert str(flatten(parse_expr(sel))) == "(OR a b c d)"


def test_flatten_mixed():
    sel = "(a, b, c) (c d) (d, (e, f g))"
    assert str(parse_expr(sel)) == "(AND (OR a b c) (AND c d) (OR d (OR e (AND f g))))"
    assert str(flatten(parse_expr(sel))) == "(AND (OR a b c) c d (OR (AND f g) d e))"


def test_flatten_consolidated_leaf_conjunctions():
    sel = "(a.x, a.y, a.z) b"
    assert str(parse_expr(sel)) == "(AND (OR a.x a.y a.z) b)"
    # TODO what's happening here? create an example where this matters...
    assert str(flatten(parse_expr(sel))) == "(AND (OR (a.x, a.y, a.z)) b)"
