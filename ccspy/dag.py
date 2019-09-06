from functools import total_ordering

@total_ordering
class Key:
    def __init__(self, name, value=None):
        self.name = name
        self.value = value
        self.specificity = None # TODO

    # TODO java code notices if key/val are actually not idents and quotes them
    def __str__(self):
        if self.value:
            return f"{self.name}.{self.value}"
        return self.name

    def __eq__(self, other):
        if not other: return False
        return self.name == other.name and self.value == other.value

    def __lt__(self, other):
        return (self.name, self.value) < (other.name, other.value)

    def __hash__(self):
        return hash((self.name, self.value))
