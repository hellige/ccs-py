from collections import defaultdict
from itertools import chain
from typing import Dict, FrozenSet, Iterable, Sequence, Set

from ccs.ast import Expr, Op, Selector, Step
from ccs.dag import Key
from ccs.formula import Clause, Formula, normalize
from ccs.property import Property


class RuleTreeNode:
    def __init__(self, expand_limit=100, formula=Formula([Clause([])])):
        self.expand_limit = expand_limit
        self.formula = formula
        self.children = []
        self.props = []
        self.constraints = []

    def __iter__(self):
        yield self
        for v in chain(*map(iter, self.children)):
            yield v

    def traverse(self, selector):
        dnf = to_dnf(flatten(selector), self.expand_limit)
        formula = expand(self.expand_limit, self.formula, dnf)
        self.children.append(RuleTreeNode(self.expand_limit, formula))
        return self.children[-1]

    def add_property(self, name, value, origin, override):
        self.props.append((name, Property(value, origin, 1 if override else 0)))

    def add_constraint(self, key):
        self.constraints.append(key)

    def _accumulate_stats(self, stats):
        stats["nodes"] += 1
        stats["props"] += len(self.props)
        stats["constraints"] += len(self.constraints)
        stats["edges"] += len(self.children)
        for node in self.children:
            node._accumulate_stats(stats)

    def stats(self):
        # TODO also perhaps max formula size? avg formula size? etc?
        stats = {"nodes": 0, "props": 0, "constraints": 0, "edges": 0}
        self._accumulate_stats(stats)
        return stats

    def label(self):
        return str(self.formula)

    def color(self):
        return (
            "lightblue" if len(self.props) or len(self.constraints) else "transparent"
        )


def to_dnf(expr: Selector, limit: int = 100) -> Formula:
    if isinstance(expr, Step):
        return Formula([Clause([expr.key])])

    assert isinstance(expr, Expr)
    if expr.op == Op.OR:
        res = merge(map(lambda e: to_dnf(e, limit), expr.children))
        return res
    assert expr.op == Op.AND
    return expand(limit, *map(lambda e: to_dnf(e, limit), expr.children))


def flatten(expr: Selector) -> Selector:
    if isinstance(expr, Step):
        return expr

    assert isinstance(expr, Expr)

    lit_children: Dict[str, Set[str]] = defaultdict(set)
    new_children = []

    def add_child(e: Selector) -> None:
        assert isinstance(expr, Expr)  # mypy should know this, but doesn't...
        if isinstance(e, Step) and expr.op == Op.OR:
            # in this case, we can group matching literals by key to avoid unnecessary dnf expansion.
            # it's not totally clear whether it's better to do this here or in to_dnf() (or possibly even in
            # normalize()??, so this is a bit of an arbitrary choice...
            # TODO negative matches will need to be handled here, probably adding as separate clusters,
            # depending on specificity rules?
            # TODO wildcard matches also need to be handled specially here, either as a flag on the key or
            # a special entry in values...
            # TODO if this is done prior to normalize(), that function needs to be changed to understand
            # set-valued pos/neg literals... and might need to be changed for negative literals either way?
            lit_children[e.key.name].update(e.key.values)
        else:
            new_children.append(e)

    for e in map(flatten, expr.children):
        if isinstance(e, Expr) and e.op == expr.op:
            for c in e.children:
                add_child(c)
        else:
            add_child(e)

    for name in lit_children:
        new_children.append(Step(Key(name, lit_children[name])))
    return Expr(expr.op, new_children)


def merge(forms: Iterable[Formula]) -> Formula:
    empty: FrozenSet[Clause] = frozenset()  # mypy appeasement...
    clauses = empty.union(*(f.elements() for f in forms))
    shared = empty.union(*(f.shared for f in forms))
    return normalize(Formula(clauses, shared))


def expand(limit: int, *forms: Formula) -> Formula:
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
