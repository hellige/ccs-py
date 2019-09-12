class Property:
    def __init__(self, value, origin, override_level):
        self.value = value
        self.origin = origin
        self.override_level = override_level

    def __repr__(self):
        return f"'{self.value}'"
