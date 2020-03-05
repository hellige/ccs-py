import io

from ccs.ast import flatten
from ccs.dnf import to_dnf
from ccs.parser import Parser


def dnfify(string: str):
    expr = Parser().parse_selector(io.StringIO(string))
    return to_dnf(flatten(expr))


def test_dnf():
    assert str(dnfify("a b, c d")) == "a b, c d"


def test_cnf():
    assert str(dnfify("(a, b) (c, d)")) == "a c, a d, b c, b d"


def test_nested_and():
    assert str(dnfify("(a b) (c d)")) == "a b c d"


def test_sharing():
    assert str(dnfify("(a f (b, e)) (c d)")) == "a b c d f, a c d e f"


def test_flatten_single_key_leaf_disjunctions():
    sel = "(a.x, a.y, a.z) b"
    assert str(dnfify(sel)) == "(a.x, a.y, a.z) b"
