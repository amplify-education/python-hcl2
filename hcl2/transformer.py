import re
from lark import Transformer, Discard


HEREDOC_PATTERN = re.compile(r'<<([a-zA-Z0-9]+)\n((.|\n)*?)\n\s*\1', re.S)


class DictTransformer(Transformer):
    def numeric_lit(self, args):
        return float(str(args[0]))

    def true_lit(self, args):
        return True

    def false_lit(self, args):
        return False

    def null_lit(self, args):
        return None

    def identifier(self, args):
        return str(args[0])

    def variable_expr(self, args):
        return str(args[0])

    def string_lit(self, args):
        # remove double quotes from start and end of the token
        return "".join([str(arg) for arg in args])

    def expr_term(self, args):
        # if the expression starts with a paren then unwrap it
        if args[0] == "(":
            return args[1]
        # otherwise return the value itself
        return args[0]

    def index_expr_term(self, args):
        return "%s[%s]" % (str(args[0]), str(args[1]))

    def get_attr_expr_term(self, args):
        return "%s.%s" % (str(args[0]), str(args[1]))

    def attr_splat_expr_term(self, args):
        return "%s.*.%s" % (args[0], args[1])

    def tuple(self, args):
        args = [self.to_string_dollar(arg) for arg in args if arg != "\n" and not isinstance(arg, Discard)]
        return args

    def object_elem(self, args):
        key = self.strip_quotes(args[0])
        value = self.to_string_dollar(args[1])

        return {
            key: value
        }

    def object(self, args):
        args = [arg for arg in args if arg != "\n" and not isinstance(arg, Discard)]
        result = {}
        for arg in args:
            result.update(arg)
        return result

    def function_call(self, args):
        args = [arg for arg in args if arg != "\n" and not isinstance(arg, Discard)]
        args_str = ''
        if len(args) > 1:
            args_str = ",".join([str(arg) for arg in args[1]])
        return "%s(%s)" % (str(args[0]), args_str)

    def arguments(self, args):
        return args

    def new_line_and_or_comma(self, args):
        return Discard()

    def new_line(self, args):
        return Discard()

    def block(self, args):
        args = [arg for arg in args if arg != "\n" and not isinstance(arg, Discard)]
        result = {}
        current_level = result
        for arg in args[0:-2]:
            current_level[self.strip_quotes(arg)] = {}
            current_level = current_level[self.strip_quotes(arg)]

        current_level[self.strip_quotes(args[-2])] = args[-1]

        return result

    def one_line_block(self, args):
        args = [arg for arg in args if arg != "\n" and not isinstance(arg, Discard)]
        result = {}
        current_level = result
        for arg in args[0:-2]:
            current_level[self.strip_quotes(arg)] = {}
            current_level = current_level[self.strip_quotes(arg)]

        current_level[self.strip_quotes(args[-2])] = args[-1]

        return result

    def attribute(self, args):
        key = str(args[0])
        if key.startswith('"') and key.endswith('"'):
            key = key[1:-1]
        value = self.to_string_dollar(args[1])

        return {
            key: value
        }

    def interpolation(self, args):
        return "${%s}" % str(args[0])

    def conditional(self, args):
        return "%s ? %s : %s" % (args[0], args[1], args[2])

    def binary_op(self, args):
        return " ".join([str(arg) for arg in args])

    def unary_op(self, args):
        return "".join([str(arg) for arg in args])

    def body(self, args):
        args = [arg for arg in args if arg != "\n" and not isinstance(arg, Discard)]
        result = {}
        for arg in args:
            for k, v in arg.items():
                key = str(k)
                if key not in result:
                    result[key] = v
                else:
                    if isinstance(result[key], list):
                        if isinstance(v, list):
                            result[key].extend(v)
                        else:
                            result[key].append(v)
                    else:
                        result[key] = [result[key], v]
        return result

    def start(self, args):
        args = [arg for arg in args if arg != "\n" and not isinstance(arg, Discard)]
        return args[0]

    def binary_operator(self, args):
        return str(args[0])

    def heredoc_template(self, args):
        match = HEREDOC_PATTERN.match(str(args[0]))
        if not match:
            raise RuntimeError("Invalid Heredoc token: %s" % args[0])
        return '"%s"' % match.group(2)

    def to_string_dollar(self, value):
        if isinstance(value, str):
            if value.startswith('"') and value.endswith('"'):
                return str(value)[1:-1]
            else:
                return '${%s}' % value
        return value

    def strip_quotes(self, value):
        if isinstance(value, str):
            if value.startswith('"') and value.endswith('"'):
                return str(value)[1:-1]
        return value

    def new_line_or_comment(self, args):
        return Discard()
