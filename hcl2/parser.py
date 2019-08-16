import os
from os.path import exists, dirname

from lark import Lark
from lark.grammar import Rule
from lark.lexer import TerminalDef

from hcl2.transformer import DictTransformer

PARSER_FILE = os.path.join(dirname(__file__), 'lark_parser.py')

if not exists(PARSER_FILE):
    with open(dirname(__file__) + '/hcl2.lark', 'r') as lark_file, open(PARSER_FILE, 'w') as parser_file:
        lark_inst = Lark(lark_file.read(), parser="lalr", lexer="contextual")

        print('from sre_constants import MAXREPEAT', file=parser_file)
        print('from lark.grammar import Rule', file=parser_file)
        print('from lark.lexer import TerminalDef', file=parser_file)
        print('from lark import Lark', file=parser_file)

        data, m = lark_inst.memo_serialize([TerminalDef, Rule])
        print('DATA = (', file=parser_file)
        print(data, file=parser_file)
        print(')', file=parser_file)
        print('MEMO = (', file=parser_file)
        print(m, file=parser_file)
        print(')', file=parser_file)

        print('Shift = 0', file=parser_file)
        print('Reduce = 1', file=parser_file)
        print("def Lark_StandAlone(transformer=None, postlex=None):", file=parser_file)
        print("  namespace = {'Rule': Rule, 'TerminalDef': TerminalDef}", file=parser_file)
        print("  return Lark.deserialize(DATA, namespace, MEMO, transformer=transformer, postlex=postlex)",
              file=parser_file)

from hcl2.lark_parser import Lark_StandAlone

hcl2 = Lark_StandAlone(transformer=DictTransformer())


def load(text):
    return hcl2.parse(text)
