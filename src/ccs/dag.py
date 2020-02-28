from collections import defaultdict, namedtuple
from functools import total_ordering
import heapq


class Specificity(
    namedtuple("Specificity", ["override", "positive", "negative", "wildcard"])
):
    __slots__ = ()

    def __add__(self, other):
        return Specificity(
            self.override + other.override,
            self.positive + other.positive,
            self.negative + other.negative,
            self.wildcard + other.wildcard,
        )


POS_LIT_SPEC = Specificity(0, 1, 0, 0)
WILDCARD_SPEC = Specificity(0, 0, 0, 1)


# TODO this class really no longer makes sense in this module, it's not
# even directly present in the dag any longer...
@total_ordering
class Key:
    def __init__(self, name, values=set()):
        self.name = name
        self.values = frozenset(values)
        self.specificity = POS_LIT_SPEC if len(values) else WILDCARD_SPEC

    # TODO java code notices if key/val are actually not idents and quotes them
    def __str__(self):
        if len(self.values) > 1:
            val_strs = (f"{self.name}.{val}" for val in sorted(self.values))
            return f"({', '.join(val_strs)})"
        elif len(self.values) == 1:
            return f"{self.name}.{next(iter(self.values))}"
        return self.name

    def __eq__(self, other):
        if not other:
            return False
        return self.name == other.name and self.values == other.values

    def __lt__(self, other):
        return (self.name, sorted(self.values)) < (other.name, sorted(other.values))

    def __hash__(self):
        return hash((self.name, self.values))


class LiteralMatcher:
    def __init__(self):
        self.wildcard = None
        self.positive_values = defaultdict(list)
        self.negative_values = []  # TODO support this

    def add_values(self, values, node):
        # because we find the set of unique literals prior to creating these matchers, we
        # don't currently need to worry about the added node representing being redundant.
        # each node will definitely represent a unique set of values for this name. in the
        # event that the node doesn't end up with any local property settings, building a
        # separate node for every combination is overkill. it might be nice to detect this
        # case and elide the subset node, replacing it with individual nodes for each member.
        # on the other hand, whether this is an improvement depends on whether or not those
        # individual nodes will actually end up existing either way, or alternatively on the
        # number of different sets those values appear in. this isn't a tradeoff with an
        # easy obvious answer.

        if len(values) == 0:
            assert not self.wildcard
            self.wildcard = node

        for value in values:
            self.positive_values[value].append(node)
        # TODO handle negatives


class Node:
    def __init__(self):
        self.children = []
        self.props = []
        self.constraints = []
        self.tally_count = 0  # used for poisoning in case of OrNode

    def add_link(self):
        self.tally_count += 1

    def accumulate_subclass_stats(self, stats):
        pass

    def accumulate_stats(self, stats, visited):
        if self in visited:
            return
        visited.add(self)
        stats.nodes += 1
        stats.props += len(self.props)
        stats.edges += len(self.children)
        stats.fanout_max = max(stats.fanout_max, len(self.children))
        stats.fanout_total += len(self.children)
        self.accumulate_subclass_stats(stats)
        if len(self.children):
            stats.nodes_with_fanout += 1
        for node in self.children:
            node.accumulate_stats(stats, visited)


class AndNode(Node):
    def __init__(self, specificity):
        super().__init__()
        self.specificity = specificity

    def accumulate_subclass_stats(self, stats):
        # only include tally stats for and nodes, since the tallies
        # for or nodes are only used for poisoning...
        stats.tally_max = max(stats.tally_max, self.tally_count)
        stats.tally_total += self.tally_count


class OrNode(Node):
    def accumulate_subclass_stats(self, stats):
        pass


class DagStats:
    def __init__(self):
        self.literals = 0
        self.nodes = 0
        self.props = 0
        self.edges = 0
        self.tally_max = 0
        self.fanout_max = 0
        self.tally_total = 0
        self.fanout_total = 0
        self.nodes_with_fanout = 0

    def __repr__(self):
        return str(self.__dict__)

    def dump(self):
        for name in self.__dict__:
            print(f"{name}: {getattr(self, name)}")
        print(f"tally_avg: {self.tally_total/self.nodes}")
        print(f"fanout_avg: {self.fanout_total/self.nodes_with_fanout}")


class Dag:
    def __init__(self):
        self.children = defaultdict(LiteralMatcher)

    def stats(self):
        stats = DagStats()
        visited = set()
        for _, matcher in self.children.items():
            stats.literals += 1
            if matcher.wildcard:
                matcher.wildcard.accumulate_stats(stats, visited)
            for nodes in matcher.positive_values.values():
                for node in nodes:
                    node.accumulate_stats(stats, visited)
            # TODO handle negatives as well
        return stats


@total_ordering
class Rank:
    def __init__(self, elem):
        self.weight = len(elem)
        self.elem = elem

    def __eq__(self, other):
        return self.weight == other.weight and self.elem == other.elem

    def __lt__(self, other):
        if self.weight == other.weight:
            return self.elem > other.elem
        return self.weight > other.weight


def build(expr, constructor, base_nodes, these_nodes):
    # TODO need a special case for the empty formula
    if len(expr) == 1:
        return base_nodes[expr.first()]

    if expr in these_nodes:
        return these_nodes[expr]
    if len(expr) == 2:
        node = constructor()
        for l in expr.elements():
            base_nodes[l].children.append(node)
            node.add_link()
        return node

    ranks = defaultdict(list)
    sizes = []
    for c in these_nodes:
        if c.issubset(expr):
            assert len(c) < len(expr), "exact equality handled above"
            rank = Rank(c)
            sizes.append(rank)
            for l in c.elements():
                ranks[l].append(rank)
    heapq.heapify(sizes)
    covered = set()
    node = constructor()

    while len(sizes) and sizes[0].weight != 0:
        best = heapq.heappop(sizes).elem
        these_nodes[best].children.append(node)
        node.add_link()
        for l in best.elements():
            if l not in covered:
                covered.add(l)
                for rank in ranks[l]:
                    rank.weight -= 1
        # TODO this repeated linear heapify is no good, we need a heap that allows us to
        # shuffle elements up and down as needed
        heapq.heapify(sizes)

    for l in expr.elements() - covered:
        base_nodes[l].children.append(node)
        node.add_link()

    return node


def add_literal(dag, lit):
    # all literals are built with a tally count of one, even if they're set-valued!
    node = AndNode(lit.specificity)
    node.add_link()
    dag.children[lit.name].add_values(lit.values, node)
    return node


# TODO handle rule_tree_node with empty formula by adding props as root-level props to dag!
def build_dag(rule_tree_nodes):
    dag = Dag()
    lit_nodes = {}
    # obviously there are better ways of gathering the unique literals and unique clauses,
    # if performance needs to be improved...
    sorted_formulae = sorted(rule_tree_nodes, key=lambda n: n.formula)
    all_clauses = [
        c for f in sorted_formulae for c in f.formula.clauses | f.formula.shared
    ]
    for lit in {l for c in all_clauses for l in c.elements()}:
        lit_nodes[lit] = add_literal(dag, lit)
    clause_nodes = {}
    for clause in sorted(all_clauses):
        clause_nodes[clause] = build(
            clause, lambda: AndNode(clause.specificity()), lit_nodes, clause_nodes
        )
    form_nodes = {}
    for rule in sorted_formulae:
        node = build(rule.formula, lambda: OrNode(), clause_nodes, form_nodes)
        node.props += rule.props
        node.constraints += rule.constraints
        form_nodes[rule.formula] = node
    return dag
