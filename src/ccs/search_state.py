from collections import deque
from collections.abc import Callable
from typing import Any, TypeVar, Optional, TextIO, Protocol

from pyrsistent import m, s, dq
import pyrsistent

from ccs.ast import ImportResolver
from ccs.dag import AndNode, Key, Specificity, build_dag
from ccs.error import EmptyPropertyError, AmbiguousPropertyError, MissingPropertyError
from ccs.parser import Parser
from ccs.property import Property
from ccs.rule_tree import RuleTreeNode

T = TypeVar("T")


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


class PropertyTracer(Protocol):
    def __call__(self, format_str: str, *args: Any) -> None: ...


class Context:
    @classmethod
    def from_ccs_stream(
        cls,
        stream: TextIO,
        filename: str,
        import_resolver: Optional[ImportResolver] = None,
        *,
        trace_properties: Optional[PropertyTracer] = None,
    ) -> "Context":
        parser = Parser()
        if import_resolver is not None:
            rules = parser.parse_ccs_stream(stream, filename, import_resolver, [])
        else:
            rules = parser.parse(stream, filename)

        root = RuleTreeNode()
        rules.add_to(root)
        dag = build_dag(root)
        return Context(dag, trace_properties=trace_properties)

    def __init__(
        self,
        dag,
        prop_accumulator=MaxAccumulator,
        tallies=m(),
        or_specificities=m(),
        props=m(),
        poisoned=None,
        *,
        debug_location=None,
        trace_properties: Optional[PropertyTracer] = None,
    ):
        self.dag = dag
        self.tallies = tallies
        self.or_specificities = or_specificities
        self.prop_accumulator = prop_accumulator
        self.props = props
        self.poisoned = poisoned
        self.debug_location = debug_location if debug_location is not None else dq()
        self.trace_properties = trace_properties

        if len(props) == 0:
            for field, new_value in self._augment(deque(), activate_root=True).items():
                setattr(self, field, new_value)

    def augment(self, key, value=None):
        key = Key(key, {value})
        changes = self._augment(deque([key]))
        return Context(
            self.dag,
            self.prop_accumulator,
            **changes,
            debug_location=self.debug_location.append(key),
            trace_properties=self.trace_properties,
        )

    def _augment(self, keys, *, activate_root=False) -> dict:
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
            if propagated_specificity is None:
                return prev_spec
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
                props = _update_props(
                    props, n.props, self.prop_accumulator, activation_specificity
                )
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

        if activate_root:
            keys = deque(self.dag.prop_node.constraints) + keys
            activate(self.dag.prop_node)

        while keys:
            key = keys.popleft()
            assert len(key.values) < 2
            match_step(key.name, next(iter(key.values), None))

        return {
            "tallies": tallies,
            "or_specificities": or_specificities,
            "props": props,
            "poisoned": poisoned,
        }

    def get_single_property(self, prop: str) -> Property:
        contenders = self.props.get(prop, None)
        if contenders is None:
            raise MissingPropertyError(f"Invalid property: {prop}")

        properties = list(contenders.values)
        if len(properties) == 0:
            raise EmptyPropertyError(f"Property {prop} has no values")
        if len(properties) > 1:
            raise AmbiguousPropertyError(
                f"Property {prop} has too many values: {properties}"
            )

        match = properties[0]
        if self.trace_properties is not None:
            if len(self.debug_location) == 0:
                location_str = "<root>"
            else:
                location_str = " > ".join([str(key) for key in self.debug_location])
            self.trace_properties(
                "Found property: %s = %s\n\tin context: [%s]",
                prop,
                match.value,
                location_str,
            )
        return match

    def get_single_value(
        self, prop: str, *, cast: Optional[Callable[[Any], T]] = None
    ) -> T:
        value = self.get_single_property(prop).value
        if cast is not None:
            return cast(value)
        else:
            return value

    def try_get_single_value(
        self, prop: str, default: T, *, cast: Optional[Callable[[Any], T]] = None
    ) -> T:
        try:
            return self.get_single_value(prop, cast=cast)
        except MissingPropertyError:
            return default


def _update_props(props, new_props, prop_accumulator, activation_specificity):
    for name, prop_val in new_props:
        prop_vals = props.get(name, prop_accumulator())
        prop_specificity = (
            Specificity(prop_val.override_level, 0, 0, 0) + activation_specificity
        )
        props = props.set(name, prop_vals.accum(prop_val, prop_specificity))
    return props
