import io
import pytest

from ccs import parser


cases = []


def succ(ccs):
    cases.append((ccs, True))


def fail(ccs):
    cases.append((ccs, False))


# basic phrases
succ("")
succ("@import 'file'")
fail("@context (foo x.bar # baz)")
succ("prop = 'val'")
succ("elem.id {}")
succ("elem.id {prop = 'val'}")
fail("elem.id {prop = @override 'hi'}")
succ("a.class blah elem.id {prop=3}")
succ("a.class blah elem.id {prop=2.3}")
succ('a.class blah elem.id {prop="val"}')
fail('a.class blah elem.id prop="val" }')
succ("a.class blah elem.id {prop=0xAB12}")
succ("a.class blah elem. id {prop=2.3}")
succ('a . class elem.id {prop="val"}')
fail("blah")
fail("@import 'file'; @context (foo)")
fail("@yuno?")
succ("@import 'file' ; @constrain foo")
succ("a.class { @import 'file' }")
fail("a.class { @context (foo) }")
succ("elem.id { prop = 'val'; prop2 = 31337 }")
succ("prop.'val' { p = 1; }")
succ("a b, c d {p=1}")
succ("(a, b) (c, d) {p=1}")
succ("a, b, c {p=1}")
succ("a, (b c) d {p=1}")
succ("a.\"foo\" 'bar' {'test' = 1}")


# comments
succ("// single line comment\n")
succ("// single line comment nonl")
succ("/* multi-line comment */")
succ("prop = /* comment */ 'val'")
succ("prop = /*/ comment */ 'val'")
succ("prop = /**/ 'val'")
succ("prop = /* comment /*nest*/ more */ 'val'")
succ("elem.id /* comment */ {prop = 'val'}")
fail("elem.id /* comment {prop = 'val'}")
succ("// comment\nelem { prop = 'val' prop = 'val' }")


# ugly abutments
fail("foo {p = 1x = 2}")
succ("foo {p = 1x p2 = 2}")
succ("foo {p = 'x'x = 2}")
succ("foo {p = 1 x = 2}")
fail("value=12asdf.foo {}")
succ("value=12asdf.foo nextsel {}")
succ("foo {p = 1 x = 2}")
succ("foo{p=1;x=2}")
fail("foo{@overridep=1}")
succ("foo{@override /*hi*/ p=1}")
succ("@import'asdf'")
fail("@constrainasdf")
succ("@import 'asdf' \n ; \n @constrain asdf \n ; @import 'foo'  ")
succ("@import /*hi*/ 'asdf'")
succ("env.foo/* some comment */{ }")


# in-file constraints
succ("a.b: @constrain a.c")


# interplation tests
succ("a = 'hi'")
fail("a = 'hi")
fail("a = 'hi\\")
fail("a = 'hi\\4 there'")
succ("a = 'h${there}i'")
fail("a = 'h$there}i'")
fail("a = 'h${t-here}i'")


def parse(ccs):
    try:
        parser.Parser().parse(io.StringIO(ccs), "-")
        return True
    except parser.ParseError:
        return False


@pytest.mark.parametrize("ccs, expected", cases)
def test_parse(ccs, expected):
    assert parse(ccs) == expected


def test_parse_selector_and_print():
    ccs = "(a, b, c) (d, e, f)"
    ast = parser.Parser().parse_selector(io.StringIO(ccs))
    assert str(ast) == "(AND (OR a b c) (OR d e f))"
