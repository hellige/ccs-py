from itertools import chain

from ccspy.to_dnf import flatten, expand, to_dnf
from ccspy.formula import Clause, Formula
from ccspy.property import Property


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
        stats['nodes'] += 1
        stats['props'] += len(self.props)
        stats['constraints'] += len(self.constraints)
        stats['edges'] += len(self.children)
        for node in self.children:
            node._accumulate_stats(stats)

    def stats(self):
        # TODO also perhaps max formula size? avg formula size? etc?
        stats = {'nodes': 0, 'props': 0, 'constraints': 0, 'edges': 0}
        self._accumulate_stats(stats)
        return stats

    def label(self):
        return str(self.formula)

    def color(self):
        return 'lightblue' if len(self.props) or len(self.constraints) else 'transparent'
