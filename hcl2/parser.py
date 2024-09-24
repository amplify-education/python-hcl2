"""A parser for HCL2 implemented using the Lark parser"""
from pathlib import Path

from lark import Lark, Token
from lark.reconstruct import Reconstructor

from .indenter import TerraformIndenter

PARSER_FILE = Path(__file__).absolute().resolve().parent / ".lark_cache.bin"


hcl2 = Lark.open(
    "hcl2.lark",
    parser="lalr",
    # cache=str(PARSER_FILE),  # Disable/Delete file to effect changes to the grammar
    rel_to=__file__,
    propagate_positions=True,
    maybe_placeholders=False,  # Needed for reconstruction
    postlex=TerraformIndenter(),
)

SPACE_AFTER = set(',+-*/~@<>="|:')
SPACE_BEFORE = (SPACE_AFTER - set(",:")) | set("'")


def _special_symbol(sym):
    return Token("SPECIAL", sym.name)


def _postprocess_reconstruct(items):
    stack = ["\n"]
    actions = []
    last_was_whitespace = True
    for item in items:
        if isinstance(item, Token) and item.type == "SPECIAL":
            actions.append(item.value)
        else:
            if actions:
                assert actions[0] == "_NL", actions

                for a in actions[1:]:
                    if a == "_NL":
                        yield "\n"
                    elif a == "_INDENT":
                        stack.append(stack[-1] + " " * 2)
                    elif a == "_DEDENT":
                        stack.pop()
                    else:
                        assert False, a
                actions.clear()
                yield stack[-1]
                last_was_whitespace = True
            if not last_was_whitespace:
                if item[0] in SPACE_BEFORE:
                    yield " "
            yield item
            last_was_whitespace = item[-1].isspace()
            if not last_was_whitespace:
                if item[-1] in SPACE_AFTER:
                    yield " "
                    last_was_whitespace = True
    yield "\n"


class HCLReconstructor:
    def __init__(self, parser):
        self._recons = Reconstructor(
            parser,
            {
                "_NL": _special_symbol,
                "_DEDENT": _special_symbol,
                "_INDENT": _special_symbol,
            },
        )

    def reconstruct(self, tree):
        return self._recons.reconstruct(tree, _postprocess_reconstruct)


hcl2_reconstructor = HCLReconstructor(hcl2)
