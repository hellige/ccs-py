CCS 2.0 Roadmap
===============

This document tracks the high-level plan for the CCS 2.0 Python
implementation. It covers what's done, what's missing, and what's still being
designed.


What works today
----------------

The core pipeline is functional end-to-end:

- **Parsing:** Full CCS syntax including selectors, property definitions,
  `@import`, `@constrain`, `@context`, `@override`, string interpolation,
  comments (including nested), hex literals, and all value types.

- **Selector processing:** Flattening, DNF conversion with expansion limits,
  multi-value key optimization, shared sub-clause detection, and formula
  normalization.

- **DAG building:** Two-phase set-cover algorithm, `AndNode`/`OrNode`
  construction, `LiteralMatcher` dispatch, statistics collection.

- **Matching:** Context augmentation, tally-based activation, specificity
  propagation, poisoning, `@override` support, `@constrain` processing.

- **Property resolution:** `MaxAccumulator` (best-specificity-wins),
  `SetAccumulator` (collect all), ambiguity detection, property tracing.

- **Import resolution:** File inclusion with circular import detection.

- **Tests:** Parser tests (80+ cases), AST flattening tests, DNF conversion
  tests, formula normalization tests, integration tests for search/matching.


Implementation gaps
-------------------

These are features that exist in CCS 1.0 or are partially implemented in the
2.0 codebase but need completion:

### Negative literal support

The `LiteralMatcher` has a `negative_values` field and several TODO comments
for negative match handling in `search_state.py`, but the actual matching logic
is not implemented. This blocks negative matches (see below).

### Typed property values

The C++ and Java implementations have typed values (int, double, bool, string)
with coercion rules (`getInt()`, `getDouble()`, `getBool()`, `getString()`).
The Python version stores everything as the raw parsed string and relies on the
caller's `cast` parameter. This works but is less ergonomic and doesn't match
the behavior of the other implementations (e.g., `true`/`false` as boolean
values, hex integers as ints).

### CLI tool

`ccs/cli/__init__.py` just prints "Not yet implemented". The C++ version has
no CLI either, but a tool for loading, validating, and dumping CCS files would
be useful.

### Canonical dump

The notebook contains a working canonical dump implementation for diffing
configurations, but it's described as "terrible and wants a cleanup" and is not
yet part of the library proper.

### Origin tracking

Property origins (filename + line number) are parsed and stored but not
consistently propagated through all error messages and debug output.

### Logging

Several places use `print()` for error reporting (e.g., circular import
detection, parse errors). These should use a proper logging mechanism.


Known concerns
--------------

These are design areas that need careful attention before building further.

### Poisoning is implemented but not enabled

The poisoning code in `search_state.py` is fully written (the `poison()`
function, the `if poisoned is not None` guard in `match_step`), but poisoning
is never activated because `poisoned` is initialized to `None` and no code path
sets it to a non-`None` value. The closed-world assumption ("augmenting with
`a.x` means key `a` has ONLY value `x`") is therefore not enforced. Enabling
this is the next step — it requires initializing `poisoned` to an empty set
(e.g., `s()`) and verifying correctness.

The interaction between activation, poisoning, and the tally-count trick for
literal nodes that represent set-valued disjunctions is complex. The comment at
`search_state.py:160` ("this is starting to feel a bit too cute and tricky")
acknowledges this. Negative matches will add another dimension to this same
mechanism. This area needs thorough edge-case testing and possibly a simpler
formulation before building on top of it.

### Multi-value key optimization composability

The `flatten()` function collapses same-key disjunctions (e.g., `(a.x, a.y,
a.z)`) into a single set-valued literal. This is presented as a syntactic
simplification but has semantic consequences: downstream code must understand
set-valued keys. The existing TODOs in `flatten()` about how negatives and
wildcards interact with this clustering suggest it may not compose cleanly with
future features. This interaction needs to be resolved before implementing
negative matches.

### Specificity must be nailed down early

Specificity is load-bearing: every property lookup depends on it, and users'
existing config files implicitly rely on the current rules. The 4-tuple
`(override, positive, negative, wildcard)` works today but is mostly implicit
-- you have to read the code to understand the precedence rules. Before adding
negative matches or override generalization, the specificity semantics should
be precisely specified and documented, because changes after config files are
written would be painful.

### SetAccumulator correctness

The TODO at `search_state.py:19` says "really this should probably be a map
from value to specificity, where only the highest specificity for a given
specific value/origin is retained." If the current implementation keeps all
`(value, specificity)` pairs, it may produce incorrect results when the same
property is set to the same value at different specificities and a different
value at an intermediate specificity. This could lead to spurious ambiguity
errors. Should be investigated and resolved.


New features (2.0 only)
-----------------------

These are features enabled by the 2.0 semantic changes that don't exist in 1.0.

### Negative matches

Negative matches would allow rules like "match when env is NOT prod". This is
a new capability enabled by 2.0's removal of the descendant (`>`) operator and
its explicit DNF semantics. The feature is designed but syntax is not yet
finalized.

Open questions:
- Syntax: `!env.prod`? `env.!prod`? Something else?
- Specificity: how do negative literals interact with specificity counting?
- Interaction with wildcards: what does `!env` mean (no env constraint at all)?
- How do negatives interact with the `flatten()` clustering optimization?

### Specificity rethinking

The current specificity model is a 4-tuple
`(override, positive, negative, wildcard)`. There may be room to rethink these
semantics, though this is still in the design phase.

### Override generalization

CCS 1.0 has a single `@override` level: override rules always beat
non-override rules, and among overrides, normal specificity applies. A possible
generalization would introduce multiple override levels or a different
mechanism. This is only worth pursuing if an elegant and usable design can be
found.


Modernization
-------------

The Python code was largely written in 2019 targeting Python 3.6+. Significant
modernization opportunities exist:

### Build system

- Migrate from `setup.py` to `pyproject.toml` with modern build backend.
- The `PYTHON_REQUIRES` is set to `~=3.6` and classifiers only list 3.6/3.7.
  Should target 3.10+ to use modern features.

### Type annotations

- Some modules have type hints, others don't. Inconsistent use of
  `Optional[X]` vs `X | None`. Modern Python supports `X | None` natively.
- `Self` type (3.11+) would improve return type annotations.
- `rule_tree.py` has `List[object]` with a `# TODO this type is clearly
  temporary` comment.

### Data classes

- `Key`, `Specificity`, `Property`, `Origin`, `DagStats` could all be
  dataclasses (or `NamedTuple` where appropriate).
- `Specificity` is currently a `namedtuple` subclass with a custom `__add__`;
  this is fine but could be cleaner.
- `Key` has manual `__eq__`, `__hash__`, `__lt__` that dataclass could generate.

### Pattern matching

- AST node dispatch (isinstance checks in `flatten()`, `to_dnf()`, `_augment()`)
  could use structural pattern matching (3.10+).

### Other

- Replace `assert` in non-test code with proper error handling.
- `formula.py` uses mutable default argument `shared: Iterable[Clause] = []`
  which is a Python footgun (though it works here because it's only iterated).
- `parser.py` string building uses `+=` with TODO questioning efficiency.


Test coverage
-------------

Current test files:

| File | Covers |
|------|--------|
| `test_parser.py` | 80+ parse success/failure cases, selector printing |
| `test_ast.py` | Flattening: AND, OR, mixed, single-key leaf disjunctions |
| `test_dnf.py` | DNF conversion: basic, CNF expansion, nested AND, sharing, multi-value keys |
| `test_formula.py` | Formula normalization (subsumption removal) |
| `test_search.py` | End-to-end: property lookup, ambiguity, casting, tracing, wildcards, constraints |

### Shared acceptance test suite

A cross-implementation acceptance test suite for CCS 2.0 semantics is a
high-priority goal. The C++ `tests.txt` already has 24 cases in a simple,
implementation-agnostic text format (name, CCS source, assertions). This format
should be adopted and extended to cover all 2.0 semantics, and all
implementations (Python, C++, Rust) should run the same suite. This is
essential for ensuring semantic consistency as 2.0 features are developed in
Python and ported back to C++.

### Gaps

- No tests for `@context`.
- No negative-testing for DNF expansion limit.
- No tests for string interpolation at the search level.
