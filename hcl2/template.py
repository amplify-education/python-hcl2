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


def _scan_expression(text: str, start: int) -> int:
    """Return the index just past the `}` closing the span opened at *start*.

    Braces nest, and a string literal inside may contain braces of its own or
    an escaped quote, so neither can be found by counting alone.
    """
    depth = 0
    index = start
    length = len(text)
    while index < length:
        char = text[index]
        if char == '"':
            index += 1
            while index < length:
                if text[index] == "\\":
                    index += 2
                    continue
                if text[index] == '"':
                    break
                index += 1
            index += 1
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index + 1
        index += 1
    # Unbalanced: the caller gets the rest as one span rather than an error,
    # because a serializer is the wrong place to reject what the parser took.
    return length


def split_template(text: str) -> Iterator[Tuple[str, str]]:
    """Yield `(kind, chunk)` pairs covering *text* exactly once.

    `kind` is `LITERAL` for text the reader treats as characters, including
    the `$${` and `%%{` escapes themselves, and `INTERPOLATION` for a `${...}`
    or `%{...}` span, whose content is expression source.
    """
    index = 0
    literal_start = 0
    length = len(text)

    while index < length:
        char = text[index]
        if char in _OPENERS:
            escape = _ESCAPES[char]
            if text.startswith(escape, index):
                # An escape is literal text, and consuming it here is what
                # stops the `${` inside it from opening a span.
                index += len(escape)
                continue
            if text.startswith(_OPENERS[char], index):
                if literal_start != index:
                    yield LITERAL, text[literal_start:index]
                end = _scan_expression(text, index + 1)
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
