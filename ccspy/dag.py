class Key:
    def __init__(self, name, value):
        self.name = name
        self.value = value
        self.specificity = None # TODO

    # TODO java code notices if key/val are actually not idents and quotes them
    def __str__(self):
        return f"{self.name}.{self.value}"

    def __eq__(self, other):
        if not other: return False
        return self.name == other.name and self.value == other.value

    def __hash__(self):
        return hash((self.name, self.value))
