from collections import namedtuple
from functools import total_ordering


class Specificity(namedtuple('Specificity',
        ['override', 'positive', 'negative', 'wildcard'])):
    __slots__ = ()

    def __add__(self, other):
        return Specificity(
            self.override + other.override, self.positive + other.positive,
            self.negative + other.negative, self.wildcard + other.wildcard)


POS_LIT_SPEC = Specificity(0, 1, 0, 0)
WILDCARD_SPEC = Specificity(0, 0, 0, 1)


@total_ordering
class Key:
    def __init__(self, name, values=set()):
        self.name = name
        self.values = frozenset(values)
        self.specificity = POS_LIT_SPEC if len(values) else WILDCARD_SPEC

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
