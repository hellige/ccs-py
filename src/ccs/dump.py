"""Canonical dump of a CCS DAG.

Produces a canonical textual representation of all properties reachable
from a Context, sorted by property name and formula.
"""

from __future__ import annotations

import sys

import pyrsistent

from ccs.dag import AndNode, Key
from ccs.formula import Clause, Formula


def top_sort(dag):
    """Topological sort of DAG nodes, building formula representations.

    Returns (nodes, node_forms) where nodes is in topological order and
    node_forms maps each node to its Clause or Formula.
    """
    visited = set()
    result = []

    def visit(n):
        if n in visited:
            return
        for m in n.children:
            visit(m)
        visited.add(n)
        result.append(n)

    node_forms = {}

    def visit_literal_node(node, name, value=None):
        # at this point, we know all the nodes are going to be
        # AndNodes, but we also know that in actual fact they correspond
        # to disjunctions of literals, so we do something a bit special
        # to build the clause:
        assert isinstance(node, AndNode)

        # TODO this won't really work right for disjunctions of a wildcard
        # plus actual values (as in '(a, a.x, a.y) : foo = bar'), but i'm
        # pretty sure that's already broken other places as well. anyway,
        # add a test and fix it everywhere!
        if node in node_forms:
            values = node_forms[node].first().values
        else:
            values = set()
        to_add = {value} if value else set()
        node_forms[node] = Clause([Key(name, values | to_add)])
        visit(node)

    for lit, matcher in dag.children.items():
        if matcher.wildcard:
            visit_literal_node(matcher.wildcard, lit)
        for v, nodes in matcher.positive_values.items():
            for node in nodes:
                visit_literal_node(node, lit, v)
        # TODO handle negative values here

    return reversed(result), node_forms


# TODO this is terrible and wants a cleanup!
def combine(f1, f2):
    """Merge two Clause/Formula objects."""
    if isinstance(f1, Clause) and isinstance(f2, Clause):
        return f1.union(f2)
    if isinstance(f1, Formula) and isinstance(f2, Formula):
        return Formula(f1.clauses.union(f2.clauses))
    if isinstance(f1, Clause) and isinstance(f2, Formula):
        return Formula(f2.clauses | {f1})
    assert False, f"what are you trying to do? {type(f1)} {type(f2)}"


def dump_dag(ctx, prop_names=None, *, out=sys.stdout):
    """Print canonical dump of properties visible from a Context.

    If prop_names is given (a string or iterable of strings), only rules
    setting those properties are shown.

    Each line shows the formula (selector) under which a property is set,
    along with its value, override status, and origin.
    """
    if isinstance(prop_names, str):
        prop_names = {prop_names}
    elif prop_names is not None:
        prop_names = set(prop_names)

    dag = ctx.dag
    poisoned = ctx.poisoned or pyrsistent.s()
    nodes, node_forms = top_sort(dag)

    def _include(prop):
        return prop_names is None or prop[0] in prop_names

    results = []

    # Root-level (unconditional) properties from prop_node
    for prop in dag.prop_node.props:
        if _include(prop):
            results.append((None, prop))

    for node in nodes:
        # TODO is this the correct place to bail out here? or only when
        # we add the props to result? think hard about this!
        if node in poisoned:
            continue
        form = node_forms.get(node)
        if form is None:
            continue
        for prop in node.props:
            if not _include(prop):
                continue
            # TODO this is terrible, find a better way to do it. in general,
            # wouldn't it be easier to just store the normalized formula
            # in each node?? how much memory could that possibly really waste?
            prop_form = Formula([form]) if isinstance(form, Clause) else form
            results.append((prop_form, prop))  # TODO include origin!
        # TODO also handle constraints!
        for child in node.children:
            if child in node_forms:
                child_form = node_forms[child]
            else:
                child_form = Clause([]) if isinstance(child, AndNode) else Formula([])
            node_forms[child] = combine(form, child_form)

    def sort_key(result):
        return (result[1][0], str(result[0]) if result[0] else "")

    for result in sorted(results, key=sort_key):
        name = result[1][0]
        prop = result[1][1]
        ovd = "@override " if prop.override_level > 0 else ""
        if result[0] is None:
            print(f"{ovd}{name} = '{prop.value}' // {prop.origin}", file=out)
        else:
            print(f"{result[0]} : {ovd}{name} = '{prop.value}' // {prop.origin}", file=out)
