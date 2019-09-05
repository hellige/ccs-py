class Origin:
    def __init__(self, filename, line_number):
        self.filename = filename
        self.line_number = line_number

    def __str__(self):
        return f"{self.filename}: {self.line_number}"


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
    # selector is a "selector branch" type
    def __init__(self, selector = None):
        self.selector = selector
        self.rules = []

    def set_selector(self, selector):
        self.selector = selector

    def append(self, rule):
        self.rules.append(rule)

    def add_to(self, build_context):
        if self.selector:
            build_context = self.selector.traverse(build_context)
        for rule in self.rules:
            rule.add_to(build_context)

    def resolve_imports(self, *args):
        for rule in self.rules:
            if not rule.resolve_imports(*args):
                return False
        return True

    def __str__(self):
        return f"{self.selector} : {{ {'; '.join(map(str, self.rules))} }}"


# "selector branch" types


class Conjunction:
    def __init__(self, leaf):
        self.leaf = leaf

    def __str__(self):
        return f"(AND {self.leaf})"

    def traverse(self, build_context):
        return build_context.conjunction(build_context.traverse(self.leaf))


class Disjunction:
    def __init__(self, leaf):
        self.leaf = leaf

    def __str__(self):
        return f"(OR {self.leaf})"

    def traverse(self, build_context):
        return build_context.disjunction(build_context.traverse(self.leaf))

# "selector leaf" types


class Step:
    def __init__(self, key):
        self.key = key

    def __str__(self):
        return f"(STEP {self.key})"

    def traverse(self, dag):
        return dag.find_or_create_node(self.key)

    def conjunction(self, right):
        return Wrap(Conjunction(self), right)

    def disjunction(self, right):
        return Wrap(Disjunction(self), right)


class Wrap:
    def __init__(self, branch, leaf):
        self.branches = [branch]
        self.leaf = leaf

    def __str__(self):
        return f"(WRAP [{' '.join(map(str, self.branches))}] {self.leaf})"

    def traverse(self, dag):
        tmp = dag.build_context()
        for branch in self.branches:
            tmp = branch.traverse(tmp)
        return tmp.traverse(self.leaf)

    def _push(self, branch, leaf):
        self.branches.append(branch)
        self.leaf = leaf
        return self

    def conjunction(self, right):
        return self._push(Conjunction(self.leaf), right)

    def disjunction(self, right):
        return self._push(Disjunction(self.leaf), right)
