from ccspy.dag import Specificity


class Clause:
    def __init__(self, lits):
        self.literals = frozenset(lits)

    def first(self):
        return next(iter(self.literals))

    def issubset(self, other):
        return self.literals.issubset(other.literals)

    def elements(self):
        return self.literals

    def union(self, other):
        return Clause(self.literals.union(other.literals))

    def specificity(self):
        return sum((l.specificity for l in self.literals),
            Specificity(0, 0, 0, 0))

    def __str__(self):
        return " ".join(map(str, sorted(self.literals)))

    def _repr_pretty_(self, p, cycle):
        p.text(str(self) if not cycle else '...')

    def __len__(self):
        return len(self.literals)

    def __lt__(self, other):
        if len(self.literals) == len(other.literals):
            return sorted(self.literals) < sorted(other.literals)
        return len(self.literals) < len(other.literals)

    def __eq__(self, other):
        return self.literals == other.literals

    def __hash__(self):
        return hash(self.literals)

    def __repr__(self):
        return '<{}>'.format(''.join(map(str, self.literals)))


class Formula:
    def __init__(self, clauses):
        self.clauses = frozenset(clauses)
        self.shared = frozenset()

    def first(self):
        return next(iter(self.clauses))

    def issubset(self, other):
        return self.clauses.issubset(other.clauses)

    def elements(self):
        return self.clauses

    def __len__(self):
        return len(self.clauses)

    def __str__(self):
        return ", ".join(map(str, sorted(self.clauses)))

    def _repr_pretty_(self, p, cycle):
        p.text(str(self) if not cycle else '...')

    def __lt__(self, other):
        if len(self.clauses) == len(other.clauses):
            return sorted(self.clauses) < sorted(other.clauses)
        return len(self.clauses) < len(other.clauses)

    def __eq__(self, other):
        return self.clauses == other.clauses

    def __hash__(self):
        return hash(self.clauses)

    def __repr__(self):
        return '({})'.format(''.join(self.clauses))
