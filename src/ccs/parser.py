"""CCS parser"""

import re

from ccs import ast
from ccs import dag
from ccs import stringval


class ParseError(Exception):
    def __init__(self, location, message):
        super().__init__(f"{location}: {message}")
        self.location = location


class Location:
    def __init__(self, line, column):
        self.line = line
        self.column = column

    def __str__(self):
        return f"<{self.line}:{self.column}>"


class Token:
    EOS = "end-of-input"
    LPAREN = "'('"
    RPAREN = "')'"
    LBRACE = "'{'"
    RBRACE = "'}'"
    SEMI = "';'"
    COLON = "':'"
    COMMA = "','"
    DOT = "'.'"
    GT = "'>'"  # TODO delete!
    EQ = "'='"
    CONSTRAIN = "'@constrain'"
    CONTEXT = "'@context'"
    IMPORT = "'@import'"
    OVERRIDE = "'@override'"
    INT = "integer"
    DOUBLE = "double"
    IDENT = "identifier"
    NUMID = "numeric/identifier"
    STRING = "string literal"

    def __init__(self, typ, location, initial_val=""):
        self.type = typ
        self.location = location
        self.value = initial_val
        self.string_value = None  # TODO only for STRING interp, delete!

    def __str__(self):
        return self.type

    def append(self, s):
        self.value += s  # TODO anything better than string concat here?

    # TODO needed?
    # def int_value(self):
    #     return int(self.value)

    # def double_value(self):
    #     return float(self.value)


class Buf:
    EOF = ""

    def __init__(self, stream):
        self.stream = stream
        self.line = 1
        self.column = 0
        self.peek_char = self._read_next()

    def _read_next(self):
        c = self.stream.read(1)
        # even though our EOF is already '', seems clearer to be explicit about
        # this here...
        return self.EOF if c == "" else c

    def get(self):
        c = self.peek_char
        self.peek_char = self._read_next()
        # this way of tracking location gives funny results when get() returns
        # a newline, but we don't actually care about that anyway...
        self.column += 1
        if c == "\n":
            self.line += 1
            self.column = 0
        return c

    def peek(self):
        return self.peek_char

    def location(self):
        return Location(self.line, self.column)

    def peek_location(self):
        return Location(self.line, self.column + 1)


class Lexer:
    def __init__(self, stream):
        self.stream = Buf(stream)
        self.next = self.next_token()

    def peek(self):
        return self.next

    def consume(self):
        tmp = self.next
        self.next = self.next_token()
        return tmp

    def next_token(self):
        c = self.stream.get()

        while c.isspace() or self.comment(c):
            c = self.stream.get()

        where = self.stream.location()

        def const(typ):
            return lambda c, loc: Token(typ, loc)

        recognizers = {
            Buf.EOF: const(Token.EOS),
            "(": const(Token.LPAREN),
            ")": const(Token.RPAREN),
            "{": const(Token.LBRACE),
            "}": const(Token.RBRACE),
            ";": const(Token.SEMI),
            ":": const(Token.COLON),
            ",": const(Token.COMMA),
            ".": const(Token.DOT),
            ">": const(Token.GT),
            "=": const(Token.EQ),
            "@": self.command,
            "'": self.string,
            '"': self.string,
        }

        if c in recognizers:
            return recognizers[c](c, where)

        if self.numid_init_char(c):
            return self.numid(c, where)

        if self.ident_init_char(c):
            return self.ident(c, where)

        raise ParseError(where, f"Unexpected character: '{c}' (0x{hex(ord(c))})")

    def command(self, c, where):
        tok = self.ident(c, where)
        if tok.value == "@constrain":
            tok.type = Token.CONSTRAIN
        elif tok.value == "@context":
            tok.type = Token.CONTEXT
        elif tok.value == "@import":
            tok.type = Token.IMPORT
        elif tok.value == "@override":
            tok.type = Token.OVERRIDE
        else:
            raise ParseError(where, f"Unrecognized @-command: {tok.value}")
        return tok

    def comment(self, c):
        if c != "/":
            return False
        if self.stream.peek() == "/":
            self.stream.get()
            tmp = self.stream.get()
            while tmp != "\n" and tmp != Buf.EOF:
                tmp = self.stream.get()
            return True
        elif self.stream.peek() == "*":
            self.stream.get()
            self.multiline_comment()
            return True
        return False

    def multiline_comment(self):
        while True:
            c = self.stream.get()
            if c == Buf.EOF:
                raise ParseError(
                    self.stream.location(), "Unterminated multi-line comment"
                )
            if c == "*" and self.stream.peek() == "/":
                self.stream.get()
                return
            if c == "/" and self.stream.peek() == "*":
                self.stream.get()
                self.multiline_comment()

    def ident_init_char(self, c):
        if c == "$":
            return True
        if c == "_":
            return True
        if "A" <= c and c <= "Z":
            return True
        if "a" <= c and c <= "z":
            return True
        return False

    def ident_char(self, c):
        if self.ident_init_char(c):
            return True
        if "0" <= c and c <= "9":
            return True
        return False

    def numid_init_char(self, c):
        if "0" <= c and c <= "9":
            return True
        if c == "-" or c == "+":
            return True
        return False

    def numid_char(self, c):
        if self.numid_init_char(c):
            return True
        if self.ident_char(c):
            return True
        if c == ".":
            return True
        return False

    def interpolant_char(self, c):
        if c == "_":
            return True
        if "0" <= c and c <= "9":
            return True
        if "A" <= c and c <= "Z":
            return True
        if "a" <= c and c <= "z":
            return True
        return False

    # TODO all implementations, this is terrible. interpolation should be
    # handled at the parser level, not at the scanner level. it leads to a lot
    # of ugliness...
    def string(self, first, where):
        result = stringval.StringVal()
        current = ""  # TODO ok to just use strings and +=???
        while self.stream.peek() != first:
            peek = self.stream.peek()
            if peek == Buf.EOF:
                raise ParseError(
                    self.stream.peek_location(), "Unterminated string literal"
                )
            elif peek == "$":
                self.stream.get()
                if self.stream.peek() != "{":
                    raise ParseError(self.stream.peek_location(), "Expected '{'")
                self.stream.get()
                if len(current) > 0:
                    result.add_literal(current)
                current = ""
                interpolant = ""
                while self.stream.peek() != "}":
                    if not self.interpolant_char(self.stream.peek()):
                        raise ParseError(
                            self.stream.peek_location(),
                            "Character not allowed in string interpolant: "
                            f"{self.stream.peek()} "
                            f"(0x{hex(ord(self.stream.peek()))})",
                        )
                    interpolant += self.stream.get()
                self.stream.get()
                result.add_interpolant(interpolant)
            elif peek == "\\":
                self.stream.get()
                escape = self.stream.get()
                escapes = "$'\"\\tnr"
                if escape in escapes:
                    current += escape
                elif escape == "\n":
                    pass  # escaped newline: ignore
                else:
                    raise ParseError(
                        self.stream.location(),
                        f"Unrecognized escape sequence: '\\{escape}' "
                        f"(0x{hex(ord(escape))})",
                    )
            else:
                current += self.stream.get()
        self.stream.get()
        if len(current) > 0:
            result.add_literal(current)
        tok = Token(Token.STRING, where)
        tok.string_value = result
        return tok

    INT_RE = re.compile("[-+]?[0-9]+")
    DOUBLE_RE = re.compile("[-+]?[0-9]+\\.?[0-9]*([eE][-+]?[0-9]+)?")

    def numid(self, first, where):
        if first == "0" and self.stream.peek() == "x":
            self.stream.get()
            return self.hex_literal(where)

        token = Token(Token.NUMID, where, first)

        while self.numid_char(self.stream.peek()):
            token.append(self.stream.get())

        if self.INT_RE.fullmatch(token.value):
            token.type = Token.INT
        elif self.DOUBLE_RE.fullmatch(token.value):
            token.type = Token.DOUBLE

        return token  # it's a generic NUMID

    def hex_char(self, c):
        if "0" <= c and c <= "9":
            return ord(c) - ord("0")
        if "a" <= c and c <= "f":
            return 10 + ord(c) - ord("a")
        if "A" <= c and c <= "F":
            return 10 + ord(c) - ord("A")
        return -1

    def hex_literal(self, where):
        token = Token(Token.INT, where)
        n = self.hex_char(self.stream.peek())
        token.intValue = 0
        while n != -1:
            token.intValue = token.intValue * 16 + n
            token.append(self.stream.get())
            n = self.hex_char(self.stream.peek())
        token.doubleValue = token.intValue
        return token

    def ident(self, first, where):
        token = Token(Token.IDENT, where, first)
        while self.ident_char(self.stream.peek()):
            token.append(self.stream.get())
        return token


class ParserImpl:
    def __init__(self, filename, stream):
        self.filename = filename
        self.lex = Lexer(stream)
        self.cur = None
        self.last = None
        self.advance()

    def parse_ruleset(self):
        rules = ast.Nested()
        if self.advance_if(Token.CONTEXT):
            rules.set_selector(self.parse_context())
        while self.cur.type != Token.EOS:
            self.parse_rule(rules)
        return rules

    def advance(self):
        self.last = self.cur
        self.cur = self.lex.consume()

    def advance_if(self, typ):
        if self.cur.type is typ:
            self.advance()
            return True
        return False

    def expect(self, typ):
        if not self.advance_if(typ):
            raise ParseError(
                self.cur.location, f"Expected {typ}, found {self.cur.type}"
            )

    def parse_context(self):
        self.expect(Token.LPAREN)
        result = self.parse_selector()
        self.expect(Token.RPAREN)
        self.advance_if(Token.SEMI)
        return result

    def parse_rule(self, rules):
        # the only ambiguity is between ident as start of a property setting
        # and ident as start of a selector, i.e.:
        #   foo = bar
        #   foo : bar = 'baz'
        # we can use the presence of '=' to disambiguate. parse_primrule() performs
        # this lookahead without consuming the additional token.
        if self.parse_primrule(rules):
            self.advance_if(Token.SEMI)
            return

        nested = ast.Nested(self.parse_selector())

        if self.advance_if(Token.COLON):
            if not self.parse_primrule(nested):
                raise ParseError(
                    self.cur.location,
                    "Expected @import, @constrain, or property setting",
                )
            self.advance_if(Token.SEMI)
        elif self.advance_if(Token.LBRACE):
            while not self.advance_if(Token.RBRACE):
                self.parse_rule(nested)
        else:
            raise ParseError(
                self.cur.location, "Expected ':' or '{' following selector"
            )

        rules.append(nested)

    def parse_primrule(self, rules):
        if self.cur.type is Token.IMPORT:
            self.advance()
            self.expect(Token.STRING)
            if self.last.string_value.interpolation():
                raise ParseError(
                    self.last.location, "Interpolation not allowed in import statements"
                )
            rules.append(ast.Import(self.last.string_value.str()))
            return True
        elif self.cur.type is Token.CONSTRAIN:
            self.advance()
            rules.append(ast.Constraint(self.parse_single_step()))
            return True
        elif self.cur.type is Token.OVERRIDE:
            self.advance()
            rules.append(self.parse_property(True))
            return True
        elif self.cur.type in [Token.IDENT, Token.STRING]:
            if self.lex.peek().type is Token.EQ:
                rules.append(self.parse_property(False))
                return True
        return False

    def parse_property(self, override):
        name = self.parse_ident("property name")
        self.expect(Token.EQ)

        # we set the origin from the location of the equals sign. it's a bit
        # arbitrary, but it seems as good as anything.
        origin = ast.Origin(self.filename, self.last.location.line)

        # TODO this is very different from the java code but it sure
        # would be nice to keep this simpler... if this doesn't work out,
        # refer to the java/c++ code for the typed Value stuff
        if self.cur.type not in [
            Token.INT,
            Token.DOUBLE,
            Token.STRING,
            Token.NUMID,
            Token.IDENT,
        ]:
            raise ParseError(
                self.cur.location,
                f"{self.cur.type} cannot occur here. Expected property value "
                + "(number, identifier, string, or boolean)",
            )
        propval = (
            self.cur.value if self.cur.value else self.cur.string_value.str()
        )  # TODO not complete...

        self.advance()
        return ast.PropDef(name, propval, origin, override)

    def parse_selector(self):
        return self.parse_sum()
        # leaf = self.parse_sum()
        # if self.advance_if(Token.GT):
        #     raise ParseError(self.cur.location, "No longer supported") # TODO
        # return ast.Conjunction(leaf)

    def parse_sum(self):
        terms = [self.parse_product()]
        while self.advance_if(Token.COMMA):
            terms.append(self.parse_product())
        if len(terms) == 1:
            return terms[0]
        return ast.disj(terms)

    def could_start_step(self, token):
        return token.type in [Token.IDENT, Token.STRING, Token.LPAREN]

    def parse_product(self):
        terms = [self.parse_term()]
        # term starts with ident or '(', which is enough to disambiguate...
        while self.could_start_step(self.cur):
            terms.append(self.parse_term())
        if len(terms) == 1:
            return terms[0]
        return ast.conj(terms)

    def parse_term(self):
        return self.parse_step()

    #     left = self.parse_step()
    #     while self.cur.type is Token.GT:
    #         # here we have to distinguish another step from a trailing '>'. again,
    #         # peeking for ident or '(' does the trick.
    #         if not self.could_start_step(self.lex.peek()):
    #              return left
    #         self.advance()
    #         left = left.descendant(self.parse_step())
    #     return left

    def parse_step(self):
        if self.advance_if(Token.LPAREN):
            result = self.parse_sum()
            self.expect(Token.RPAREN)
            return result
        return ast.Step(self.parse_single_step())

    def parse_single_step(self):
        name = self.parse_ident("selector name")
        values = set()
        if self.advance_if(Token.DOT):
            values.add(self.parse_ident("selector value"))
        return dag.Key(name, values)

    def parse_ident(self, what):
        if self.advance_if(Token.IDENT):
            return self.last.value
        if self.advance_if(Token.STRING):
            if self.last.string_value.interpolation():
                raise ParseError(
                    self.last.location, f"Interpolation not allowed in {what}"
                )
            return self.last.string_value.str()
        raise ParseError(
            self.cur.location, f"{self.cur.type} cannot occur here. Expected {what}"
        )


class Parser:
    def load_ccs_stream(self, stream, filename, dag, import_resolver):
        rule = self.parse_ccs_stream(stream, filename, import_resolver, [])
        if not rule:
            return

        # everything parsed, no errors. now it's safe to modify the dag...
        rule.add_to(dag.build_context())

    def parse_ccs_stream(self, stream, filename, import_resolver, in_progress):
        try:
            rule = ParserImpl(filename, stream).parse_ruleset()
            if not rule.resolve_imports(import_resolver, self, in_progress):
                return None
            return rule
        except ParseError as e:
            # TODO logger...
            print(f"Errors parsing '{filename}': {e}")
            return None

    def parse(self, stream, filename):
        return ParserImpl(filename, stream).parse_ruleset()

    def parse_selector(self, stream, filename="<none>"):
        return ParserImpl(filename, stream).parse_selector()
