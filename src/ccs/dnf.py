"""DNF-conversion.

These functions convert from AST selector types, ideally flattened, to DNF formulae."""

from ccs.ast import Expr, Op, Selector, Step
from ccs.formula import Clause, Formula, normalize

from typing import FrozenSet, Iterable, Sequence


def to_dnf(expr: Selector, limit: int = 100) -> Formula:
    """Convert a selector to a DNF formula."""

    if isinstance(expr, Step):
        return Formula([Clause([expr.key])])

    assert isinstance(expr, Expr)
    if expr.op == Op.OR:
        res = merge(map(lambda e: to_dnf(e, limit), expr.children))
        return res
    assert expr.op == Op.AND
    return expand(limit, *map(lambda e: to_dnf(e, limit), expr.children))


def merge(forms: Iterable[Formula]) -> Formula:
    """Merge a sequence of formulae into one, preserving shared subclauses."""

    empty: FrozenSet[Clause] = frozenset()  # mypy appeasement...
    clauses = empty.union(*(f.elements() for f in forms))
    shared = empty.union(*(f.shared for f in forms))
    return normalize(Formula(clauses, shared))


def expand(limit: int, *forms: Formula) -> Formula:
    """Exponentially expand a conjunction of formulae to DNF.

    We also detect and accumulate subclauses which end up shared due to the duplication
    of clauses during expansion."""

    # first, build the subclause which is guaranteed to be common
    # to all clauses produced in this expansion. keep count of
    # the non-trivial forms and the size of the result as we go...
    nontrivial = 0
    common = Clause([])
    result_size = 1
    for f in forms:
        result_size *= len(f)
        if len(f) == 1:
            common = common.union(f.first())
        else:
            nontrivial += 1

    if result_size > limit:
        raise ValueError(
            "Expanded form would have {} clauses, which is more "
            "than the limit of {}. Consider increasing the limit or stratifying "
            "this rule.".format(result_size, limit)
        )

    # next, perform the expansion...
    def exprec(forms: Sequence[Formula]) -> Formula:
        if len(forms) == 0:
            return Formula([Clause([])])
        first = forms[0]
        rest = exprec(forms[1:])
        cs = (c1.union(c2) for c1 in first.elements() for c2 in rest.elements())
        res = Formula(cs, first.shared | rest.shared)
        return res

    res = exprec(forms)

    # finally, gather shared subclauses and normalize...
    all_shared = set()
    if nontrivial > 0 and len(common) > 1:
        all_shared.add(common)
    if nontrivial > 1:
        for f in forms:
            if len(f) > 1:
                all_shared.update(c for c in f.elements() if len(c) > 1)
    return normalize(Formula(res.elements(), res.shared | all_shared))
