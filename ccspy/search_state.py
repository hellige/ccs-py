from collections import deque
from pyrsistent import m, s
import pyrsistent

from ccspy.dag import AndNode, Key, Specificity

# TODO really this should probably be a map from value to specificity, where only the highest specificity
# for a given specific value/origin is retained
class SetAccumulator:
    def __init__(self, values=s()):
        self.values = values

    def accum(self, prop, specificity):
        return SetAccumulator(self.values.add((prop, specificity)))

    def __repr__(self):
        return repr(pyrsistent.thaw(self.values))


class MaxAccumulator:
    def __init__(self, specificity=Specificity(0, 0, 0, 0), values=s()):
        self.specificity = specificity
        self.values = values

    def accum(self, prop, specificity):
        if specificity > self.specificity:
            return MaxAccumulator(specificity, s(prop))
        if specificity == self.specificity:
            return MaxAccumulator(self.specificity, self.values.add(prop))
        return self

    def __repr__(self):
        return repr(pyrsistent.thaw(self.values))

class Context:
    def __init__(self, dag, prop_accumulator=MaxAccumulator, tallies=m(), props=m()):
        self.dag = dag
        self.tallies = tallies
        self.prop_accumulator = prop_accumulator
        self.props = props  # TODO add all root-level props from dag!

    def augment(self, key, value=None):
        keys = deque([Key(key, {value})])
        tallies = self.tallies
        props = self.props

        def activate_and(n, propagated_specificity):
            nonlocal tallies
            count = tallies.get(n, n.tally_count)
            if count > 0:
                count -= 1
                tallies = tallies.set(n, count)
                if count == 0:
                    return n.specificity
            return None

        def activate_or(n, propagated_specificity):
            nonlocal tallies
            prev_spec = tallies.get(n, Specificity(0, 0, 0, 0))
            if propagated_specificity > prev_spec:
                tallies = tallies.set(n, propagated_specificity)
                return propagated_specificity
            return None

        def activate(n, propagated_specificity=None):
            nonlocal keys
            nonlocal props
            activator = activate_and if isinstance(n, AndNode) else activate_or
            activation_specificity = activator(n, propagated_specificity)
            if activation_specificity:
                for constraint in n.constraints:
                    keys.append(constraint)
                for name, prop_val in n.props:
                    prop_vals = props.get(name, self.prop_accumulator())
                    prop_specificity = Specificity(prop_val.override_level, 0, 0, 0) + activation_specificity
                    props = props.set(name, prop_vals.accum(prop_val, prop_specificity))
                for n in n.children:
                    activate(n, activation_specificity)

        def match_step(key, value):
            if key in self.dag.children:
                matcher = self.dag.children[key]
                if matcher.wildcard:
                    activate(matcher.wildcard)
                if value and value in matcher.positive_values:
                    for node in matcher.positive_values[value]:
                        activate(node)
                # TODO negative matches here too

        while keys:
            key = keys.popleft()
            assert(len(key.values) < 2)
            match_step(key.name, next(iter(key.values), None))

        return Context(self.dag, self.prop_accumulator, tallies, props)