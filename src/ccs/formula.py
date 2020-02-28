"""CCS selector intermediate representation: clauses and formulae."""

from ccs.dag import Key, Specificity
from typing import Iterable, Set


class Clause:
    """A conjunction of literal matchers."""

    def __init__(self, lits: Iterable[Key]) -> None:
        self.literals = frozenset(lits)

    def first(self) -> Key:
        return next(iter(self.literals))

    def issubset(self, other: "Clause") -> bool:
        return self.literals.issubset(other.literals)

    def is_strict_subset(self, other: "Clause") -> bool:
        return self.literals < other.literals

    def elements(self) -> Iterable[Key]:
        return self.literals

    def union(self, other: "Clause") -> "Clause":
        return Clause(self.literals.union(other.literals))

    def specificity(self) -> Specificity:
        return sum((l.specificity for l in self.literals), Specificity(0, 0, 0, 0))

    def __str__(self) -> str:
        return " ".join(map(str, sorted(self.literals)))

    def _repr_pretty_(self, p, cycle) -> None:
        p.text(str(self) if not cycle else "...")

    def __len__(self) -> int:
        return len(self.literals)

    # note: we rely on this ordering when building the dag
    def __lt__(self, other: "Clause") -> bool:
        if len(self.literals) == len(other.literals):
            return sorted(self.literals) < sorted(other.literals)
        return len(self.literals) < len(other.literals)

    def __eq__(self, other) -> bool:
        return self.literals == other.literals

    def __hash__(self) -> int:
        return hash(self.literals)

    def __repr__(self) -> str:
        return "<{}>".format("".join(map(str, self.literals)))


class Formula:
    """A disjunction of clauses."""

    def __init__(
        self, clauses: Iterable[Clause], shared: Iterable[Clause] = []
    ) -> None:
        self.clauses = frozenset(clauses)
        self.shared = frozenset(shared)

    def first(self) -> Clause:
        return next(iter(self.clauses))

    def issubset(self, other: "Formula") -> bool:
        return self.clauses.issubset(other.clauses)

    def elements(self) -> Iterable[Clause]:
        return self.clauses

    def __len__(self) -> int:
        return len(self.clauses)

    def __str__(self) -> str:
        return ", ".join(map(str, sorted(self.clauses)))

    def _repr_pretty_(self, p, cycle) -> None:
        p.text(str(self) if not cycle else "...")

    # note: we rely on this ordering when building the dag
    def __lt__(self, other: "Formula") -> bool:
        if len(self.clauses) == len(other.clauses):
            return sorted(self.clauses) < sorted(other.clauses)
        return len(self.clauses) < len(other.clauses)

    def __eq__(self, other) -> bool:
        return self.clauses == other.clauses

    def __hash__(self) -> int:
        return hash(self.clauses)

    def __repr__(self) -> str:
        return "({})".format("".join(map(str, self.clauses)))


def subsumes(c: Clause, d: Clause) -> bool:
    """A clause c "subsumes" a clause d when d is a subset of c."""
    return c.issubset(d)


def normalize(formula: Formula) -> Formula:
    """Normalize a formula.

    For any formula, we define a normal form which exists, is unique, and is equivalent
    to the original formula under the usual interpretation of boolean logic.

    Clauses are always normal, since all literals are positive. Formulae are normalized
    by removing any clause subsumed by any other. A clause c is subsumed by a clause s
    if s <= c. This is the obvious O(mn) algorithm. Our formulae are usually of size 1,
    so this is just fine."""

    minimized: Set[Clause] = set()
    for c in formula.clauses:
        minimized = {s for s in minimized if not subsumes(c, s)}
        if not any(subsumes(s, c) for s in minimized):
            minimized.add(c)
    # note *strict* subset check here...
    shared = {
        s for s in formula.shared if any(s.is_strict_subset(c) for c in minimized)
    }
    return Formula(minimized, shared)
