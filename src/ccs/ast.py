"""CCS abstract syntax tree."""

from abc import ABC, abstractmethod
from collections import defaultdict
from enum import Enum
from typing import Dict, List, Optional, Set

from ccs.dag import Key


class Origin:
    """The original source location from which a rule/property was parsed."""

    def __init__(self, filename: str, line_number: int) -> None:
        self.filename = filename
        self.line_number = line_number

    def __repr__(self) -> str:
        return f"{self.filename}:{self.line_number}"


class Op(Enum):
    AND = "AND"
    OR = "OR"


class Selector(ABC):
    """Base class for AST nodes representing selector expressions."""


class Expr(Selector):
    """A conjunction or disjunction selector expression."""

    def __init__(self, op: Op, children: List[Selector]) -> None:
        self.op = op
        self.children = children

    def __str__(self) -> str:
        return f"({self.op.name} {' '.join(map(str, self.children))})"


def conj(terms: List[Selector]) -> Expr:
    "Construct a conjunction expression."
    return Expr(Op.AND, terms)


def disj(terms: List[Selector]) -> Expr:
    "Construct a disjunction expression."
    return Expr(Op.OR, terms)


class Step(Selector):
    """A single-step primitive selector expression."""

    def __init__(self, key: Key) -> None:
        self.key = key

    def __str__(self) -> str:
        return f"{self.key}"


class AstNode(ABC):
    """Base class for AST nodes for rules."""

    @abstractmethod
    def add_to(self, build_context) -> None:
        ...

    def resolve_imports(self, import_resolver, parser, in_progress) -> bool:
        return True


class Import(AstNode):
    """AST node for @import."""

    def __init__(self, location: str) -> None:
        self.location = location
        self.ast: Optional[AstNode] = None

    def __str__(self) -> str:
        return f"@import '{self.location}'"

    def add_to(self, build_context):
        assert self.ast
        self.ast.add_to(build_context)

    def resolve_imports(self, import_resolver, parser, in_progress) -> bool:
        if self.location in in_progress:
            # TODO logger
            print(f"Circular import detected involving '{self.location}'")
        else:
            in_progress.append(self.location)
            try:
                self.ast = parser.parse_ccs_stream(
                    import_resolver.resolve(self.location),
                    self.location,
                    import_resolver,
                    in_progress,
                )
                if self.ast:
                    return True
            finally:
                in_progress.pop()
        return False


class PropDef:
    """AST node for a property setting."""

    def __init__(self, name: str, value: str, origin: Origin, override: bool) -> None:
        self.name = name
        self.value = value
        self.origin = origin
        self.override = override

    def __str__(self) -> str:
        return f"def {self.name}"

    def add_to(self, build_context):
        build_context.add_property(self.name, self.value, self.origin, self.override)


class Constraint:
    """AST node for @constrain."""

    def __init__(self, key: Key) -> None:
        self.key = key

    def __str__(self) -> str:
        return f"@constrain {self.key}"

    def add_to(self, build_context):
        build_context.add_constraint(self.key)


class Nested:
    """AST node for a nested ruleset (single or multiple rules)."""

    def __init__(self, selector: Optional[Selector] = None) -> None:
        self.selector = selector
        self.rules: List[AstNode] = []

    def set_selector(self, selector: Selector) -> None:
        self.selector = selector

    def append(self, rule: AstNode) -> None:
        self.rules.append(rule)

    def add_to(self, build_context) -> None:
        if self.selector:
            build_context = build_context.traverse(self.selector)
        for rule in self.rules:
            rule.add_to(build_context)

    def resolve_imports(self, *args) -> bool:
        for rule in self.rules:
            if not rule.resolve_imports(*args):
                return False
        return True

    def __str__(self) -> str:
        return f"{self.selector} {{ {'; '.join(map(str, self.rules))} }}"


def flatten(expr: Selector) -> Selector:
    """Flatten a selector expression.

    A selector is flattened when we've inlined trivially nested expressions. In other
    words, a flat selector consists of strictly alternating levels of AND and OR."""

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
    if len(new_children) == 1:
        return new_children[0]
    return Expr(expr.op, new_children)
