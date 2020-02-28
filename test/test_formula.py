from ccs.formula import Clause, Formula, normalize


def test_normalize():
    form = Formula(
        [
            Clause(["a", "b"]),
            Clause(["b"]),
            Clause(["a"]),
            Clause(["c", "d"]),
            Clause(["a", "c", "d"]),
            Clause(["c", "d"]),
        ]
    )
    assert str(form) == "a, b, a b, c d, a c d"
    assert str(normalize(form)) == "a, b, c d"
