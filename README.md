[![Build Status](https://github.com/hellige/ccs-py/actions/workflows/ci.yml/badge.svg)](https://github.com/hellige/ccs-py/actions?workflow=CI)

CCS for Python
==============

This is the Python implementation of [CCS](http://github.com/hellige/ccs), a
context-based configuration language. This version implements the CCS 2.0
semantics, which refine and extend the original design.

CCS is also available for [C++](http://github.com/hellige/ccs-cpp) (the most
mature implementation, with 15+ years of production use),
[Java](http://github.com/hellige/ccs), and
[Rust](https://github.com/Asaaj/ccs2-rs).

There's a presentation about the language [here](http://hellige.github.io/ccs),
but it's a little sketchy without someone talking along with it.


What is CCS?
------------

CCS is a language for config files, and libraries to read those files and
configure applications.

Most configuration systems are simple key-value stores: you look up
`database.host` and get back a string. This works fine until your application
runs in multiple environments, regions, and deployment stacks, at which point
you end up with either many near-duplicate config files or a mess of
templating logic.

CCS takes a different approach. Configuration is a set of **rules** with
**selectors** that match against a **context**. When your application starts, it
builds a context describing "who am I?" (production, US-East, stack CL, etc.)
and queries the rules for property values. The most specific matching rule wins,
and ambiguous matches are errors, not silent overrides.

```ccs
// Base config
database.host = "localhost"
database.port = 5432

// Production overrides
env.prod {
    database.host = "prod-db.internal"
    database.timeout = 30
}

// Production + US region: more specific, wins over env.prod alone
env.prod region.us {
    database.host = "us-prod-db.internal"
}

// Override: always wins regardless of specificity
env.prod stack.CL : @override database.host = "cl-specific-db.internal"
```


Quick start
-----------

```python
from io import StringIO
from ccs.search_state import Context

ccs_rules = """
greeting = "hello"
env.prod {
    greeting = "hello (production)"
    debug = false
}
env.dev {
    greeting = "hello (dev)"
    debug = true
}
"""

# Load rules
ctx = Context.from_ccs_stream(StringIO(ccs_rules), "example.ccs")

# Query in base context
print(ctx.get_single_value("greeting"))  # "hello"

# Query in production context
prod = ctx.augment("env", "prod")
print(prod.get_single_value("greeting"))  # "hello (production)"
print(prod.get_single_value("debug"))     # "false"

# Contexts are immutable; augment returns a new context
dev = ctx.augment("env", "dev")
print(dev.get_single_value("debug"))      # "true"
```


Syntax reference
----------------

### Property definitions

```ccs
name = 123              // 64-bit integer
name = 0xFF             // hex integer
name = 3.14             // double
name = true             // boolean
name = "hello"          // string (double-quoted)
name = 'hello'          // string (single-quoted)
```

### String interpolation and escapes

```ccs
url = 'http://${DB_HOST}:${DB_PORT}/mydb'   // environment variable interpolation
escaped = "literal: \${NOT_INTERPOLATED}"    // escape with backslash
multiline = 'line one \
line two'                                    // escaped newline is ignored
```

Recognized escape sequences: `\t \n \r \' \" \\ \$`.
The non-delimiting quote character need not be escaped: `'say "hi"'` and
`"it's fine"` both work.

### Selectors

Selectors determine when rules apply, based on the current context.

```ccs
// Conjunction (AND): both must be present in context
env.prod region.us { ... }

// Disjunction (OR): either one suffices
env.dev, env.staging { ... }

// Parenthesized grouping
(env.dev, env.staging) (region.us, region.eu) { ... }

// Wildcard: matches any value for a constraint name
env { ... }

// Multi-value: matches when constraint has both values
second.class1.class2 { ... }
```

Operator precedence, highest to lowest:
- Juxtaposition (conjunction/AND)
- `,` (disjunction/OR)

### Rule forms

```ccs
// Block form
selector { rules }

// Inline form
selector : property = value
selector : @import "file.ccs"
selector : @constrain key.value
```

### @-directives

```ccs
@context (env.prod region.us)     // set context for entire file (must be first)
@import "other.ccs"               // import another ruleset
@constrain key.value              // add constraint to current context
@override property = value        // override: wins over any non-override rule
```

### Simultaneous constraints

```ccs
// Sequential: two separate constraint steps
a.b c.d { ... }

// Simultaneous: single step with both constraints (rarely needed)
a.b/c.d { ... }
```

These differ when the same constraints are applied in separate API calls vs.
a single builder call.

### Comments

```ccs
// Single-line comment
/* Multi-line comment */
/* Nested /* comments */ are supported */
```


API reference
-------------

### Loading rules

```python
from ccs.search_state import Context

# From a stream
ctx = Context.from_ccs_stream(stream, filename)

# With import resolution
ctx = Context.from_ccs_stream(stream, filename, import_resolver)
```

### Querying properties

```python
# Get a single value (raises if missing or ambiguous)
value = ctx.get_single_value("property_name")

# Get with type casting
count = ctx.get_single_value("count", cast=int)
ratio = ctx.get_single_value("ratio", cast=float)

# Get with default for missing properties
value = ctx.try_get_single_value("property_name", "default_value")

# Get the full Property object (includes origin info)
prop = ctx.get_single_property("property_name")
```

### Building context

```python
# Contexts are immutable. augment() returns a new context.
prod_ctx = ctx.augment("env", "prod")
us_prod_ctx = prod_ctx.augment("region", "us")

# Wildcard constraint (no value)
any_env_ctx = ctx.augment("env")
```

### Error handling

```python
from ccs.error import MissingPropertyError, AmbiguousPropertyError

try:
    value = ctx.get_single_value("prop")
except MissingPropertyError:
    # Property not defined in current context
    ...
except AmbiguousPropertyError:
    # Multiple values at the same specificity
    ...
```


Related implementations
-----------------------

| Implementation | Repository | Status |
|---------------|-----------|--------|
| C++ (v1) | [hellige/ccs-cpp](https://github.com/hellige/ccs-cpp) | Mature, 15+ years production use |
| Java (v1) | [hellige/ccs](https://github.com/hellige/ccs) | Mature, production use |
| Python (v2) | [hellige/ccs-py](https://github.com/hellige/ccs-py) | Work in progress |
| Rust (v2) | [Asaaj/ccs2-rs](https://github.com/Asaaj/ccs2-rs) | Work in progress |


License
-------

MIT
