from collections import deque
from pyrsistent import m, s
import pyrsistent

from ccs.dag import AndNode, Key, Specificity


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
    def __init__(self, dag, prop_accumulator=MaxAccumulator,
            tallies=m(), or_specificities=m(), props=m(), poisoned=None):
        self.dag = dag
        self.tallies = tallies
        self.or_specificities = or_specificities
        self.prop_accumulator = prop_accumulator
        self.props = props  # TODO add all root-level props from dag!
        self.poisoned = poisoned

    def augment(self, key, value=None):
        keys = deque([Key(key, {value})])
        tallies = self.tallies
        or_specificities = self.or_specificities
        poisoned = self.poisoned
        props = self.props

        def accum_tally(n):
            nonlocal tallies
            count = tallies.get(n, n.tally_count)
            if count > 0:
                count -= 1
                tallies = tallies.set(n, count)
                if count == 0:
                    return True
            return False

        def activate_and(n, propagated_specificity):
            if accum_tally(n):
                return n.specificity
            return None

        def activate_or(n, propagated_specificity):
            nonlocal or_specificities
            prev_spec = or_specificities.get(n, Specificity(0, 0, 0, 0))
            if propagated_specificity > prev_spec:
                or_specificities = or_specificities.set(n, propagated_specificity)
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

        def poison(n):
            nonlocal poisoned
            fully_poisoned = False
            if isinstance(n, AndNode):
                # a bit of care is required here, since we build tally-one
                # conjunction nodes for literals, even when they represent
                # disjunctions of multiple values.
                # TODO this is starting to feel a bit too cute and tricky,
                # might be time to build those in a more obvious way and use
                # a more explicit technique to ensure uniqueness of literal
                # values in context.
                # but anyway, because of that, and because we always activate
                # prior to poisoning, we can avoid incorrectly poisoning a
                # literal node just by checking to see whether it's already
                # been fully activated. that's the only scenario in which this
                # can happen, so it's sufficient to detect it.
                if tallies.get(n) != 0 and n not in poisoned:
                    fully_poisoned = True
            else:
                fully_poisoned = accum_tally(n)
            if fully_poisoned:
                poisoned = poisoned.add(n)
                for n in n.children:
                    poison(n)

        def match_step(key, value):
            if key in self.dag.children:
                matcher = self.dag.children[key]
                if matcher.wildcard:
                    activate(matcher.wildcard)
                if value and value in matcher.positive_values:
                    for node in matcher.positive_values[value]:
                        activate(node)
                # TODO negative matches here too
                if poisoned is not None:
                    for v2, nodes in matcher.positive_values.items():
                        # TODO here, there's a question... if value is None, do
                        # we insist that no value ever be asserted for key and
                        # poison everything? or do we remain agnostic, with the
                        # idea that key.value is still a monotonic refinement of
                        # just key? for now we assume the former.
                        if value != v2:
                            for node in nodes:
                                poison(node)
                        # TODO and of course dually negative matches too

        while keys:
            key = keys.popleft()
            assert(len(key.values) < 2)
            match_step(key.name, next(iter(key.values), None))

        return Context(self.dag, self.prop_accumulator, tallies, or_specificities, props, poisoned)
