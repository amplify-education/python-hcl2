from lark.indenter import Indenter


class TerraformIndenter(Indenter):
    """A postlexer that "injects" _INDENT/_DEDENT tokens based on indentation, according to Terraform syntax.

    See also: the ``postlex`` option in `Lark`.
    """

    NL_type = "_NL"
    OPEN_PAREN_types = ["LPAR"]
    CLOSE_PAREN_types = ["RPAR"]
    INDENT_type = "_INDENT"
    DEDENT_type = "_DEDENT"
    tab_len = 2
