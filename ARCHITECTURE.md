CCS 2.0 Architecture
====================

This document describes the internal architecture of the CCS 2.0 Python
implementation and how it differs from the CCS 1.0 design used in the
[C++](https://github.com/hellige/ccs-cpp) and
[Java](https://github.com/hellige/ccs) implementations.


Overview
--------

CCS resolves configuration by matching rules against a context. The pipeline
from CCS source text to property lookup is:

```
Source text
  -> Parser (parser.py)
  -> AST (ast.py)
  -> Flatten selectors (ast.py: flatten())
  -> Convert to DNF (dnf.py: to_dnf())
  -> Build rule tree (rule_tree.py)
  -> Build DAG (dag.py: build_dag())
  -> Query via Context (search_state.py)
```

In CCS 1.0, the pipeline was simpler: `Parser -> AST -> DAG -> Query`. The
2.0 design introduces explicit intermediate representations (flattened
selectors, DNF formulae, rule tree) that make the semantics clearer and
enable new features.


Module guide
------------

| Module | Role |
|--------|------|
| `parser.py` | Hand-written lexer and recursive-descent parser |
| `ast.py` | AST node types (`Expr`, `Step`, `Nested`, `PropDef`, `Import`, `Constraint`) and `flatten()` |
| `formula.py` | `Clause` (conjunction of literals) and `Formula` (disjunction of clauses), plus `normalize()` |
| `dnf.py` | Converts AST selectors to DNF formulae via `to_dnf()`, `merge()`, `expand()` |
| `rule_tree.py` | `RuleTreeNode`: intermediate tree associating formulae with properties and constraints |
| `dag.py` | `Dag`, `AndNode`, `OrNode`, `LiteralMatcher`, `Key`, `Specificity`, and `build_dag()` |
| `search_state.py` | `Context`: immutable query context with `augment()` and property lookup |
| `property.py` | `Property`: value with origin and override level |
| `stringval.py` | String values with `${VAR}` environment variable interpolation |
| `error.py` | `MissingPropertyError`, `EmptyPropertyError`, `AmbiguousPropertyError` |


Key concepts
------------

### Selectors and DNF

A CCS selector like `(a, b) (c, d)` means "(a OR b) AND (c OR d)". CCS 2.0
converts all selectors to **Disjunctive Normal Form (DNF)**, a sum-of-products
representation:

```
(a, b) (c, d)  ->  a c, a d, b c, b d
```

This is done by the `to_dnf()` function after `flatten()` has simplified
nested expressions of the same operator.

**Expansion limit:** DNF conversion can be exponential. The `expand()` function
enforces a configurable limit (default 100 clauses) and raises `ValueError` if
exceeded. Users can work around this by stratifying complex rules.

**Multi-value key optimization:** When a disjunction contains multiple values
for the same key (e.g., `(env.dev, env.staging, env.prod)`), the `flatten()`
function collapses these into a single set-valued literal rather than expanding
them into separate clauses. This is safe because they all have the same
specificity and the hash-table lookup in matching handles sets naturally.

### Formulae and normalization

A `Formula` is a set of `Clause`s (disjunction of conjunctions). A `Clause` is
a set of `Key` literals (conjunction).

Formulae are **normalized** by removing subsumed clauses: if clause `s` is a
subset of clause `c`, then `c` is redundant (it can never be the best match
when `s` also matches). This is the `normalize()` function.

Formulae also track **shared sub-clauses**: clauses that appear as subsets of
two or more top-level clauses. These are detected during DNF expansion and
exploited during DAG building to maximize node sharing.

### The DAG

The DAG is the core runtime data structure. It's built from the rule tree by
`build_dag()` in two phases:

1. **Add all unique literals** (individual `Key`s) as `AndNode`s attached to
   `LiteralMatcher`s in the `Dag`.

2. **Build clause and formula nodes** from smallest to largest, using a greedy
   **set-cover algorithm** to maximize sharing of intermediate nodes.

The set-cover algorithm (in `build()`) works as follows: for a given expression
(clause or formula), find all previously-built sub-expressions that are subsets,
rank them by coverage, and greedily select the best covers. Remaining uncovered
elements get direct edges. This minimizes fan-out and edge count.

### Three node types

**`AndNode` (conjunction):** Has a fixed `specificity` computed at DAG build
time and a `tally_count` equal to the number of incoming edges. Activated
exactly once, when all parents have been activated (tally reaches zero).

**`OrNode` (formula/disjunction):** Also uses tally counting, but differently.
Activated whenever the propagated specificity exceeds the previous best.
The tally is used for **poisoning** (see below), not for activation gating.

**Root `OrNode` (`dag.prop_node`):** Holds properties and constraints that apply
unconditionally (empty selector).

### Specificity

Specificity determines which rule wins when multiple rules match. It's a
4-tuple compared lexicographically:

```python
Specificity(override, positive, negative, wildcard)
```

- `override`: override level (0 for normal, 1 for `@override`)
- `positive`: count of positive literal matches
- `negative`: count of negative literal matches (reserved for future use)
- `wildcard`: count of wildcard matches

Higher specificity wins. At equal specificity, multiple values are an error
(`AmbiguousPropertyError`).

For `AndNode`s, specificity is the sum of the specificities of literals in the
clause. For `OrNode`s, specificity is propagated from whichever activating
clause had the highest specificity.

### Matching algorithm

When `Context.augment(key, value)` is called:

1. Look up `key` in `dag.children` to find the `LiteralMatcher`.
2. Activate the wildcard node (if any) and all matching positive-value nodes.
3. For each activated node, decrement its tally count. If tally reaches zero
   (for `AndNode`s) or the new specificity exceeds the previous best (for
   `OrNode`s), the node **activates**:
   - Accumulate its properties into the context.
   - Enqueue its constraints for processing.
   - Recursively activate children.
4. Process any enqueued constraints (which may trigger further activations).

### Poisoning

When a constraint `key = value` is applied, nodes that match `key` with a
*different* value are **poisoned**. A poisoned node can never activate, even if
its tally later reaches zero. This implements a form of closed-world assumption:
once you've said `env = prod`, rules matching `env.dev` are excluded.

Poisoning is tracked via a persistent set in the `Context`, ensuring that
forked contexts don't interfere with each other.

### Persistent data structures

Contexts are immutable. `augment()` returns a new `Context` with updated state.
This is implemented using persistent (immutable, structural-sharing) data
structures from the `pyrsistent` library:

- `tallies`: persistent map from node to tally count
- `or_specificities`: persistent map from `OrNode` to best activation specificity
- `props`: persistent map from property name to accumulator
- `poisoned`: persistent set of poisoned nodes


How CCS 2.0 differs from 1.0
-----------------------------

### Explicit DNF conversion

CCS 1.0 builds the DAG directly from the AST using `AndTally` and `OrTally`
structures to track complex selectors. CCS 2.0 first converts selectors to
normalized DNF, making the semantics of complex boolean selectors explicit and
deterministic.

### Set-cover DAG building

CCS 1.0 builds the DAG incrementally as rules are parsed. CCS 2.0 collects all
rules first, then builds the DAG in a single pass using a set-cover algorithm
that optimizes for sharing.

### Immutable contexts

CCS 1.0's `SearchState` mutates internal state. CCS 2.0's `Context` is
immutable, using persistent data structures. This makes context forking (one
parent context, multiple specialized children) safe and efficient.

### No descendant selector

CCS 1.0 supports the `>` (descendant) selector, inherited from the original
CSS-inspired design. CCS 2.0 drops this operator. The parser still recognizes
`>` but it is commented out in the grammar. Removing `>` is what enables DNF
conversion and several planned features (notably negative matches).

### Expansion limits

CCS 2.0 enforces limits on DNF expansion to prevent combinatorial explosion
from complex selectors.

<!-- TODO: document additional semantic differences between 1.0 and 2.0 -->


The CCS.ipynb notebook
----------------------

The Jupyter notebook `CCS.ipynb` in the repository root is the primary design
document for CCS 2.0. It contains:

- Detailed explanations of the DAG building algorithm with worked examples
- Visualizations of DAG structures (via GraphViz)
- Performance measurements on real CCS files
- A canonical dump format for normalized property output (useful for diffing)
- Design notes and open questions

It serves as both interactive documentation and a development scratchpad.
