"""CCS rule tree representation."""

from itertools import chain
from typing import List

from ccs.ast import Selector, flatten
from ccs.dag import Key
from ccs.dnf import expand, to_dnf
from ccs.formula import Clause, Formula
from ccs.property import Property


class RuleTreeNode:
    def __init__(self, expand_limit=100, formula=Formula([Clause([])])) -> None:
        self.expand_limit = expand_limit
        self.formula = formula
        self.children: List[RuleTreeNode] = []
        self.props: List[object] = []  # TODO this type is clearly temporary
        self.constraints: List[Key] = []

    def __iter__(self):
        yield self
        for v in chain(*map(iter, self.children)):
            yield v

    def traverse(self, selector: Selector) -> "RuleTreeNode":
        dnf = to_dnf(flatten(selector), self.expand_limit)
        formula = expand(self.expand_limit, self.formula, dnf)
        self.children.append(RuleTreeNode(self.expand_limit, formula))
        return self.children[-1]

    def add_property(self, name, value, origin, override) -> None:
        self.props.append((name, Property(value, origin, 1 if override else 0)))

    def add_constraint(self, key: Key) -> None:
        self.constraints.append(key)

    def _accumulate_stats(self, stats) -> None:
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

    def label(self) -> str:
        return str(self.formula)

    def color(self) -> str:
        return (
            "lightblue" if len(self.props) or len(self.constraints) else "transparent"
        )
