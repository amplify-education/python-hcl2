"""Splitting template text into the parts that mean different things.

A quoted string or a heredoc body is not one run of literal characters. HCL
reads `${...}` and `%{...}` as expression source, and `$${`/`%%{` as escapes
for a literal `${`/`%{`. Anything that rewrites such text -- resolving escapes,
adding them, or turning one form into another -- has to know which span it is
looking at, or it corrupts the expression inside.

The grammar already separates these for a quoted string, which is why
`StringRule._serialize_part_as_value` can do the right thing by asking each
part for its terminal. A heredoc body arrives as one opaque token, so the same
distinction has to be recovered from the text. That is what this does.

The scan is a single left-to-right pass, because the two questions cannot be
answered separately: a splitter run before escapes are resolved would see the
`${` inside `$${` and open an interpolation that is not there.
"""

from typing import Callable, Iterator, Tuple

LITERAL = "literal"
INTERPOLATION = "interpolation"

_OPENERS = {"$": "${", "%": "%{"}
_ESCAPES = {"$": "$${", "%": "%%{"}


def _skip_string(text: str, index: int) -> int:
    """Return the index just past the string literal opening at *index*.

    A string literal inside an expression is itself a template, so a `${` or
    `%{` in it opens a nested expression whose own literals may hold quotes
    and braces. OpenTofu evaluates `"a ${upper("v${ "{" }w")} b"` to
    `a V{W b`, so taking the next quote as the terminator ended this literal
    at the one that *opens* the innermost one, and the brace after it was
    then counted as structural.

    The escapes stay escapes here: `"a ${upper("v$${x}w")} b"` is `a V${X}W b`,
    so `$${` does not open anything.
    """
    length = len(text)
    index += 1
    while index < length:
        char = text[index]
        if char == "\\":
            index += 2
            continue
        if char in _OPENERS:
            if text.startswith(_ESCAPES[char], index):
                index += len(_ESCAPES[char])
                continue
            if text.startswith(_OPENERS[char], index):
                end = _scan_expression(text, index + 1)
                if end == -1:
                    # Unbalanced, so there is no literal to close either.
                    return length
                index = end
                continue
        if char == '"':
            return index + 1
        index += 1
    return length


def _skip_comment(text: str, index: int) -> int:
    """Return the index just past the comment opening at *index*, or *index*.

    HCL writes them three ways, and all three may hold a brace: `#` and `//`
    run to the end of the line, `/* */` to its terminator. OpenTofu evaluates
    `${1 /* } */ + 2}` to 3, so a scan that counts that brace closes the
    expression in the middle of itself.
    """
    if text.startswith("/*", index):
        end = text.find("*/", index + 2)
        return len(text) if end == -1 else end + 2
    if text.startswith("//", index) or text[index] == "#":
        end = text.find("\n", index)
        return len(text) if end == -1 else end
    return index


def _scan_expression(text: str, start: int) -> int:
    """Return the index just past the `}` closing the span opened at *start*.

    Braces nest, and three things inside an expression may carry one that is
    not structural: a string literal, a comment, and the body of a heredoc
    written inline. The first two are skipped here. A brace in a heredoc body
    is not, which is a known gap rather than an oversight -- recognising one
    means matching its delimiter, and the case has not been seen in the wild.
    """
    depth = 0
    index = start
    length = len(text)
    while index < length:
        char = text[index]
        if char == "\\":
            # A backslash pair is one unit. Without this the scan enters string
            # mode at the quote of a `\\"`, then reads the real closing quote as
            # another escape and runs to the end of the text, swallowing
            # everything after the expression into one span.
            index += 2
            continue
        if char == '"':
            index = _skip_string(text, index)
            continue
        if char == "#" or text.startswith("//", index) or text.startswith("/*", index):
            skipped = _skip_comment(text, index)
            if skipped != index:
                index = skipped
                continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index + 1
        index += 1
    # Unbalanced. Reported as such rather than swallowed: handing the rest
    # back as an expression means nothing escapes it, and the heredoc paths
    # then emit raw newlines and unescaped quotes into what is supposed to be
    # quoted-string source. Treated as literal it is at least well-formed.
    return -1


def split_template(text: str) -> Iterator[Tuple[str, str]]:
    """Yield `(kind, chunk)` pairs covering *text* exactly once.

    `kind` is `LITERAL` for text the reader treats as characters, including
    the `$${` and `%%{` escapes themselves, and `INTERPOLATION` for a `${...}`
    or `%{...}` span, whose content is expression source.
    """
    if "$" not in text and "%" not in text:
        # The overwhelmingly common case, and the one this used to make
        # expensive: a per-character loop where a scan for two characters
        # answers the question. `process_escape_sequences` has the same guard.
        if text:
            yield LITERAL, text
        return

    index = 0
    literal_start = 0
    length = len(text)

    while index < length:
        char = text[index]
        if char == "\\":
            index += 2
            continue
        if char in _OPENERS:
            escape = _ESCAPES[char]
            if text.startswith(escape, index):
                # An escape is literal text, and consuming it here is what
                # stops the `${` inside it from opening a span.
                index += len(escape)
                continue
            if text.startswith(_OPENERS[char], index):
                end = _scan_expression(text, index + 1)
                if end == -1:
                    # Nothing closes it, so the rest is literal text -- and the
                    # leading run has to stay unyielded, or the tail below
                    # repeats it.
                    break
                if literal_start != index:
                    yield LITERAL, text[literal_start:index]
                yield INTERPOLATION, text[index:end]
                index = end
                literal_start = index
                continue
        index += 1

    if literal_start != length:
        yield LITERAL, text[literal_start:length]


def resolve_escaped_markers(text: str) -> str:
    """Resolve `$${` and `%%{` into the single sigil they stand for.

    Only in literal spans: inside `${...}` the same characters are expression
    source, where `$${` does not mean a literal `${`.
    """
    return "".join(
        chunk.replace("$${", "${").replace("%%{", "%{") if kind == LITERAL else chunk
        for kind, chunk in split_template(text)
    )


def map_literal_spans(text: str, transform: Callable[[str], str]) -> str:
    """Apply *transform* to the literal spans of *text*, leaving the rest alone.

    An escape belongs to the string that carries it, not to an expression
    written inside it: escaping or unescaping through an interpolation rewrites
    someone else's source and changes what it means.
    """
    return "".join(transform(chunk) if kind == LITERAL else chunk for kind, chunk in split_template(text))
