class Property:
    def __init__(self, value, origin, override_level, property_number=0):
        self.value = value
        self.origin = origin
        self.override_level = override_level
        self.property_number = property_number

    def __repr__(self):
        return f"'{self.value}'"
