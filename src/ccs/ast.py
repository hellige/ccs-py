"""CCS abstract syntax tree."""

from enum import Enum
from typing import List, Optional

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


class Selector:
    """Base class for AST nodes representing selector expressions."""

    def __init__(self, is_literal: bool) -> None:
        self.is_literal = is_literal


class Expr(Selector):
    """A conjunction or disjunction selector expression."""

    def __init__(self, op: Op, children: List["Expr"]) -> None:
        super().__init__(False)
        self.op = op
        self.children = children

    def __str__(self) -> str:
        return f"({self.op.name} {' '.join(map(str, self.children))})"


def conj(terms: List[Expr]) -> Expr:
    "Constructs a conjunction expression."
    return Expr(Op.AND, terms)


def disj(terms: List[Expr]) -> Expr:
    "Constructs a disjunction expression."
    return Expr(Op.OR, terms)


class Step(Selector):
    """A single-step primitive selector expression."""

    def __init__(self, key: Key) -> None:
        super().__init__(True)
        self.key = key

    def __str__(self) -> str:
        return f"{self.key}"


class AstNode:
    """Base class for AST nodes for rules."""

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
