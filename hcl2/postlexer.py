"""Postlexer that transforms the token stream between the Lark lexer and parser.

Each transformation is implemented as a private method that accepts and yields
tokens.  The public ``process`` method chains them together, making it easy to
add new passes without touching existing logic.
"""

from typing import FrozenSet, Iterator, Optional, Tuple

from lark import Token

# Type alias for a token stream consumed and produced by each pass.
TokenStream = Iterator[Token]

# Operator token types that may legally follow a line-continuation newline.
# MINUS is excluded — it is also the unary negation operator, and merging a
# newline into MINUS would incorrectly consume statement-separating newlines
# before negative literals (e.g. "a = 1\nb = -2").
OPERATOR_TYPES: FrozenSet[str] = frozenset(
    {
        "DOUBLE_EQ",
        "NEQ",
        "LT",
        "GT",
        "LEQ",
        "GEQ",
        "ASTERISK",
        "SLASH",
        "PERCENT",
        "DOUBLE_AMP",
        "DOUBLE_PIPE",
        "PLUS",
        "QMARK",
    }
)


class PostLexer:
    """Transform the token stream before it reaches the LALR parser."""

    def process(self, stream: TokenStream) -> TokenStream:
        """Chain all postlexer passes over the token stream."""
        yield from self._merge_newlines_into_operators(stream)

    def _merge_newlines_into_operators(self, stream: TokenStream) -> TokenStream:
        """Merge NL_OR_COMMENT tokens into immediately following operator tokens.

        LALR parsers cannot distinguish a statement-ending newline from a
        line-continuation newline before a binary operator.  This pass resolves
        the ambiguity by merging NL_OR_COMMENT into the operator token's value
        when the next token is a binary operator or QMARK.  The transformer
        later extracts the newline prefix and creates a NewLineOrCommentRule
        node, preserving round-trip fidelity.
        """
        pending_nl: Optional[Token] = None
        for token in stream:
            if token.type == "NL_OR_COMMENT":
                if pending_nl is not None:
                    yield pending_nl
                pending_nl = token
            else:
                if pending_nl is not None:
                    if token.type in OPERATOR_TYPES:
                        token = token.update(value=str(pending_nl) + str(token))
                    else:
                        yield pending_nl
                    pending_nl = None
                yield token
        if pending_nl is not None:
            yield pending_nl

    @property
    def always_accept(self) -> Tuple[()]:
        """Terminal names the parser must accept even when not expected by LALR.

        Lark requires this property on postlexer objects.  An empty tuple
        means no extra terminals are injected.
        """
        return ()
