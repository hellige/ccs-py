import os


class Literal:
    def __init__(self, s):
        self.is_interpolant = False
        self.s = s

    def interpolate(self):
        return self.s


class Interpolant:
    def __init__(self, i):
        self.is_interpolant = True
        self.i = i

    def interpolate(self):
        return os.environ.get(self.i, "")


class StringVal:
    def __init__(self):
        self.elements = []

    def add_literal(self, s):
        self.elements.append(Literal(s))

    def add_interpolant(self, i):
        self.elements.append(Interpolant(i))

    def interpolation(self):
        if len(self.elements) > 1: return True
        if self.elements[0].is_interpolant: return True
        return False

    def str(self):
        return ''.join(e.interpolate() for e in self.elements)

    def __str__(self):
        return self.str()
