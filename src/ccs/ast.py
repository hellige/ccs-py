from enum import Enum


# TODO seems like a decent tutorial place to start:
#   https://realpython.com/python-type-checking/

class Origin:
    def __init__(self, filename, line_number):
        self.filename = filename
        self.line_number = line_number

    def __repr__(self):
        return f"{self.filename}:{self.line_number}"


class Import:
    def __init__(self, location):
        self.location = location
        self.ast = None

    def __str__(self):
        return f"@import '{self.location}'"

    def add_to(self, build_context):
        assert self.ast
        self.ast.add_to(build_context)

    def resolve_imports(self, import_resolver, parser, in_progress):
        if self.location in in_progress:
            # TODO logger
            print(f"Circular import detected involving '{self.location}'")
        else:
            in_progress.append(self.location)
            try:
                self.ast = parser.parse_ccs_stream(
                    import_resolver.resolve(self.location),
                    self.location, import_resolver, in_progress)
                if self.ast:
                    return True
            finally:
                in_progress.pop()
        return False


class PropDef:
    def __init__(self, name, value, origin, override):
        self.name = name
        self.value = value
        self.origin = origin
        self.override = override

    def __str__(self):
        return f"def {self.name}"

    def add_to(self, build_context):
        build_context.add_property(self.name, self.value, self.origin,
            self.override)

    def resolve_imports(self, *args):
        return True


class Constraint:
    def __init__(self, key):
        self.key = key

    def __str__(self):
        return f"@constrain {self.key}"

    def add_to(self, build_context):
        build_context.add_constraint(self.key)

    def resolve_imports(self, *args):
        return True


class Nested:
    # selector is an expr type, and/or or a literal
    def __init__(self, selector=None):
        self.selector = selector
        self.rules = []

    def set_selector(self, selector):
        self.selector = selector

    def append(self, rule):
        self.rules.append(rule)

    def add_to(self, build_context):
        if self.selector:
            build_context = build_context.traverse(self.selector)
        for rule in self.rules:
            rule.add_to(build_context)

    def resolve_imports(self, *args):
        for rule in self.rules:
            if not rule.resolve_imports(*args):
                return False
        return True

    def __str__(self):
        return f"{self.selector} {{ {'; '.join(map(str, self.rules))} }}"


class Op(Enum):
    AND = 'AND'
    OR = 'OR'


class Expr:
    def __init__(self, op, children):
        self.is_literal = False
        self.op = op
        self.children = children

    def __str__(self):
        return f"({self.op.name} {' '.join(map(str, self.children))})"


def conj(terms):
    return Expr(Op.AND, terms)


def disj(terms):
    return Expr(Op.OR, terms)


class Step:
    def __init__(self, key):
        self.is_literal = True
        self.key = key

    def __str__(self):
        return f"{self.key}"
