from functools import total_ordering

@total_ordering
class Key:
    def __init__(self, name, values=set()):
        self.name = name
        self.values = frozenset(values)
        self.specificity = None # TODO

    # TODO java code notices if key/val are actually not idents and quotes them
    def __str__(self):
        if len(self.values) > 1:
            return f"{self.name}.{{{', '.join(sorted(self.values))}}}"
        elif len(self.values) == 1:
            return f"{self.name}.{next(iter(self.values))}"
        return self.name

    def __eq__(self, other):
        if not other: return False
        return self.name == other.name and self.values == other.values

    def __lt__(self, other):
        return (self.name, self.values) < (other.name, other.values)

    def __hash__(self):
        return hash((self.name, self.values))
