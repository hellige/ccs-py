import os
from typing import Optional


class Literal:
    def __init__(self, s):
        self.is_interpolant = False
        self.s = s

    def interpolate(self):
        return self.s


class Interpolant:
    def __init__(self, i, env: dict[str, str]):
        self.is_interpolant = True
        self.i = i
        self.env = env

    def interpolate(self):
        return self.env.get(self.i, "")


class StringVal:
    def __init__(self, env: Optional[dict[str, str]] = None):
        self.elements = []
        self.env = env

    def add_literal(self, s):
        self.elements.append(Literal(s))

    def add_interpolant(self, i):
        env = self.env if self.env is not None else os.environ
        self.elements.append(Interpolant(i, env))

    def interpolation(self):
        if len(self.elements) > 1:
            return True
        if self.elements[0].is_interpolant:
            return True
        return False

    def str(self):
        return "".join(e.interpolate() for e in self.elements)

    def __str__(self):
        return self.str()
