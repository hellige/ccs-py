# CCS Python - Claude Session Context

This file captures context for Claude Code sessions working on this project.


## Project overview

CCS is a context-based configuration language created by Matt Hellige. There
are four implementations:

- **ccs** (Java): Original implementation. Mature. GitHub: hellige/ccs
- **ccs-cpp** (C++): Most mature, 15+ years daily production use on hundreds
  of servers. GitHub: hellige/ccs-cpp
- **ccs-py** (Python): This repo. Reference implementation for CCS 2.0
  semantics. Not intended to replace C++ in production; the plan is to
  eventually port 2.0 semantics back to C++.
- **ccs2-rs** (Rust): By a colleague (Asaaj). Incomplete but follows 2.0
  design. GitHub: Asaaj/ccs2-rs

All repos are public on GitHub but have never been promoted or documented well.


## Key files in this repo

| File | What's there |
|------|-------------|
| `CCS.ipynb` | **Primary design document.** Detailed algorithm descriptions, worked examples, visualizations, performance measurements, TODOs. Read this first for any design questions. |
| `src/ccs/parser.py` | Hand-written lexer + recursive-descent parser. ~560 lines. |
| `src/ccs/ast.py` | AST types and `flatten()` for selector simplification. |
| `src/ccs/formula.py` | `Clause`/`Formula` IR and `normalize()` (subsumption removal). |
| `src/ccs/dnf.py` | `to_dnf()`, `expand()`, `merge()` - DNF conversion with expansion limits. |
| `src/ccs/rule_tree.py` | `RuleTreeNode` - intermediate representation between AST and DAG. |
| `src/ccs/dag.py` | Core DAG: `build_dag()`, set-cover algorithm, `AndNode`/`OrNode`, `Key`, `Specificity`. |
| `src/ccs/search_state.py` | `Context` - immutable query context with matching algorithm. |
| `src/ccs/property.py` | `Property` - value + origin + override level. |
| `src/ccs/stringval.py` | String interpolation (`${VAR}` from environment). |
| `src/ccs/error.py` | Error types. |
| `test/test_search.py` | Integration tests - most useful for understanding end-to-end behavior. |
| `test/test_parser.py` | 80+ parse cases. |


## Key files in sibling repos

| File | What's there |
|------|-------------|
| `../ccs-cpp/tests.txt` | 24 acceptance test cases in a simple text format. Should be ported to Python. |
| `../ccs-cpp/misc/grammar.txt` | CCS 1.0 grammar specification. |
| `../ccs-cpp/README.md` | Best existing syntax reference. |
| `../ccs-cpp/vlans.ccs` | Real-world production CCS file (~100 lines). |
| `../ccs/src/test/java/net/immute/ccs/FunctionalTest.java` | Java functional tests covering all 1.0 features. |
| `../ccs/src/test/resources/*.ccs` | Test CCS files used by Java tests. |


## Architecture (quick reference)

Pipeline: `Source -> Parser -> AST -> flatten() -> to_dnf() -> RuleTree -> build_dag() -> Context`

The DAG is built in two phases using a greedy set-cover algorithm. Three node
types: `AndNode` (conjunction, fixed specificity, tally-gated activation),
`OrNode` (disjunction, propagated specificity, re-activatable), and literal
nodes (AndNodes attached to LiteralMatchers).

Contexts are immutable using pyrsistent persistent data structures.

See ARCHITECTURE.md for full details.


## Design status

**Solid:**
- DNF conversion with multi-value optimization
- Two-phase set-cover DAG building
- Three node types for specificity propagation
- Persistent data structures for context forking
- Poisoning for closed-world assumption

**In progress / needs work:**
- Negative matches: designed but not implemented, syntax TBD
  (candidates: `!env.prod`, `env.!prod`)
- Specificity semantics: may be rethought
- Override mechanism: considering generalization beyond binary override/normal
- Typed property values: not implemented (everything is raw strings)
- CLI tool: stub only
- Canonical dump: works in notebook but not in library

**Modernization needed:**
- Python code targets 3.6, should be updated for 3.10+
- setup.py -> pyproject.toml
- Inconsistent type annotations
- Many classes could be dataclasses
- Pattern matching could replace isinstance chains

See ROADMAP.md for full details.


## Running tests

```bash
cd /home/mhellige/src/hmm/ccs-py
.venv/bin/pytest test/
```


## Session log

### 2026-02-20: Initial exploration and documentation

- Explored all three CCS repos plus the Rust implementation (Asaaj/ccs2-rs).
- Read through all Python source files, test files, C++ tests and grammar.
- Analyzed CCS.ipynb notebook (primary design document).
- Created README.md, ARCHITECTURE.md, ROADMAP.md, and this file.
- Key learning: Python version is reference impl for 2.0 semantics, will
  eventually port back to C++. Several semantic differences from 1.0 exist
  beyond just the implementation changes (to be documented later).
- Owner's priorities: tidy up, modernize Python, complete missing features.
- Reviewed real production usage: 67 CCS files in heimdall/config, 35+ imports
  from main.ccs, constraints across env/stack/instance/node/cpuType/exchange
  and more. Heavy use of @override, @constrain, @context, @import.
- Identified four design concerns (added to ROADMAP.md): poisoning mechanism
  complexity, multi-value key optimization composability with negatives,
  specificity needing formal specification, SetAccumulator possible correctness
  issue.
- Owner confirmed: negative matches are designed (syntax TBD), specificity and
  override generalization are still in design phase. Owner will teach the
  semantic differences from 1.0 in a future session.
- Owner is not concerned about external adoption; CCS is already in heavy
  production use by their team.
- Next session: likely modernization work or diving into 2.0 semantic details.
