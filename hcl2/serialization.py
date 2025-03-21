from abc import ABC, abstractmethod
from collections import defaultdict
from email.policy import default
from json import JSONEncoder
from typing import List, Any, Union, Tuple, Optional

ArgsType = List["LarkElement"]


def is_dollar_string(value: str) -> bool:
    return value.startswith("${") and value.endswith("}")


def to_dollar_string(value: str) -> str:
    if not is_dollar_string(value):
        return f"${{{value}}}"
    return value


def unwrap_dollar_string(value: str) -> str:
    if is_dollar_string(value):
        return value[2:-1]
    return value


def wrap_into_parentheses(value: str) -> str:
    if is_dollar_string(value):
        value = unwrap_dollar_string(value)
        return to_dollar_string(f"({value})")

    return f"({value})"


class LarkEncoder(JSONEncoder):
    def default(self, obj: Any):
        if isinstance(obj, LarkRule):
            return obj.serialize()
        else:
            return super().default(obj)


class LarkElement(ABC):
    @abstractmethod
    def serialize(self) -> Any:
        raise NotImplementedError()


class LarkToken(LarkElement):
    def __init__(self, name: str, value: Union[str, int]):
        self._name = name
        self._value = value

    @property
    def name(self) -> str:
        return self._name

    @property
    def value(self):
        return self._value

    def serialize(self) -> Any:
        return self._value

    def __str__(self) -> str:
        return str(self._value)

    def __repr__(self) -> str:
        return f"<LarkToken instance: {self._name} {self._value}>"


EQ_Token = LarkToken


class TokenSequence:
    def __init__(self, tokens: List[LarkToken]):
        self.tokens = tokens

    def joined(self):
        return "".join(str(token) for token in self.tokens)


class LarkRule(ABC):
    _classes = []

    @staticmethod
    @abstractmethod
    def rule_name() -> str:
        raise NotImplementedError()

    @classmethod
    def process(cls, children):
        return cls(children)

    @abstractmethod
    def serialize(self) -> Any:
        raise NotImplementedError()

    def __init__(self, children):
        self._children: List[LarkElement] = children

    def __init_subclass__(cls, **kwargs):
        cls._classes.append(cls)

    def __repr__(self):
        return f"<LarkRule: {self.__class__.__name__} ({';'.join(str(child) for child in self._children)})>"


class StartRule(LarkRule):

    _children: Tuple["BodyRule"]

    @staticmethod
    def rule_name() -> str:
        return "start"

    def serialize(self) -> Any:
        return self._children[0].serialize()


class BodyRule(LarkRule):

    _children: List[
        Union[
            "NewLineOrCommentRule",
            "AttributeRule",
            "BlockRule",
        ]
    ]

    @staticmethod
    def rule_name() -> str:
        return "body"

    def serialize(self) -> Any:
        blocks: List[BlockRule] = []
        attributes: List[AttributeRule] = []
        comments = []

        for child in self._children:
            if isinstance(child, BlockRule):
                blocks.append(child)
            if isinstance(child, AttributeRule):
                attributes.append(child)
            if isinstance(child, NewLineOrCommentRule):
                child_comments = child.actual_comments()
                if child_comments:
                    comments.extend(child_comments)

        result = {}

        for attribute in attributes:
            result.update(
                {attribute.identifier.serialize(): attribute.expression.serialize()}
            )

        # result.update({
        #     attribute.identifier.serialize(): attribute.expression.serialize()
        #     for attribute in attributes
        # })

        result.update(
            {block.labels[0].serialize(): block.serialize() for block in blocks}
        )

        result["__comments__"] = comments

        return result


class BlockRule(LarkRule):
    @staticmethod
    def rule_name() -> str:
        return "block"

    def __init__(self, children):
        super().__init__(children)
        *self._labels, self._body = children

    @property
    def labels(self) -> List["IdentifierRule"]:
        return list(filter(lambda label: label is not None, self._labels))

    @property
    def body(self) -> BodyRule:
        return self._body

    def serialize(self) -> BodyRule:
        result = self._body.serialize()
        labels = self._labels
        for label in reversed(labels[1:]):
            result = {label.serialize(): result}
        return result


class IdentifierRule(LarkRule):

    _children: List[LarkToken]

    @staticmethod
    def rule_name() -> str:
        return "identifier"

    def serialize(self) -> Any:
        return TokenSequence(self._children).joined()


class IntLitRule(LarkRule):

    _children: List[LarkToken]

    @staticmethod
    def rule_name() -> str:
        return "int_lit"

    def serialize(self) -> Any:
        return str(TokenSequence(self._children).joined())


class FloatLitRule(LarkRule):

    _children: List[LarkToken]

    @staticmethod
    def rule_name() -> str:
        return "float_lit"

    def serialize(self) -> Any:
        return str(TokenSequence(self._children).joined())


class StringLit(LarkRule):

    _children: List[LarkToken]

    @staticmethod
    def rule_name() -> str:
        return "STRING_LIT"

    def serialize(self) -> Any:
        return TokenSequence(self._children).joined()[1:-1]


class Expression(LarkRule, ABC):
    @staticmethod
    def rule_name() -> str:
        return "expression"


class ExprTerm(Expression):
    @staticmethod
    def rule_name() -> str:
        return "expr_term"

    def __init__(self, children):
        self._parentheses = False
        if (
            isinstance(children[0], LarkToken)
            and children[0].name == "LPAR"
            and isinstance(children[-1], LarkToken)
            and children[-1].name == "RPAR"
        ):
            self._parentheses = True
            children = children[1:-1]
        super().__init__(children)

    @property
    def parentheses(self) -> bool:
        return self._parentheses

    def serialize(self) -> Any:
        result = self._children[0].serialize()
        if self._parentheses:
            result = wrap_into_parentheses(result)
        return result


class ConditionalRule(ExprTerm):

    _children: Tuple[
        Expression,
        Expression,
        Expression,
    ]

    @staticmethod
    def rule_name():
        return "conditional"

    @property
    def condition(self) -> Expression:
        return self._children[0]

    @property
    def if_true(self) -> Expression:
        return self._children[1]

    @property
    def if_false(self) -> Expression:
        return self._children[2]

    def __init__(self, children):
        super().__init__(children)

    def serialize(self) -> Any:
        result = f"{self.condition.serialize()} ? {self.if_true.serialize()} : {self.if_false.serialize()}"
        return to_dollar_string(result)


class BinaryOperatorRule(LarkRule):
    _children: List[LarkToken]

    @staticmethod
    def rule_name() -> str:
        return "binary_operator"

    def serialize(self) -> Any:
        return TokenSequence(self._children).joined()


class BinaryTermRule(LarkRule):
    _children: Tuple[
        BinaryOperatorRule,
        "NewLineOrCommentRule",
        ExprTerm,
    ]

    @staticmethod
    def rule_name() -> str:
        return "binary_term"

    def __init__(self, children):
        print(children)
        self._has_comment = False
        if len(children) == 3 and isinstance(children[1], NewLineOrCommentRule):
            self._has_comment = True

        super().__init__(children)

    @property
    def binary_operator(self) -> BinaryOperatorRule:
        return self._children[0]

    @property
    def expr_term(self) -> ExprTerm:
        return self._children[2] if self._has_comment else self._children[1]

    def serialize(self) -> Any:
        return f"{self.binary_operator.serialize()} {self.expr_term.serialize()}"


class UnaryOpRule(Expression):
    _children: Tuple[LarkToken, ExprTerm]

    @staticmethod
    def rule_name() -> str:
        return "unary_op"

    @property
    def unary_operator(self) -> str:
        return str(self._children[0])

    @property
    def expr_term(self):
        return self._children[1]

    def serialize(self) -> Any:
        return to_dollar_string(f"{self.unary_operator}{self.expr_term.serialize()}")


class BinaryOpRule(Expression):
    _children: Tuple[
        ExprTerm,
        BinaryTermRule,
        "NewLineOrCommentRule",
    ]

    @staticmethod
    def rule_name() -> str:
        return "binary_op"

    @property
    def expr_term(self) -> ExprTerm:
        return self._children[0]

    @property
    def binary_term(self) -> BinaryTermRule:
        return self._children[1]

    @classmethod
    def process(cls, children):
        return super().process(children)

    def serialize(self) -> Any:
        lhs = self.expr_term.serialize()
        operator = self.binary_term.binary_operator.serialize()
        rhs = self.binary_term.expr_term.serialize()
        rhs = unwrap_dollar_string(rhs)
        return to_dollar_string(f"{lhs} {operator} {rhs}")


class AttributeRule(LarkRule):
    _children: Tuple[
        IdentifierRule,
        EQ_Token,
        Expression,
    ]

    @staticmethod
    def rule_name() -> str:
        return "attribute"

    @property
    def identifier(self) -> IdentifierRule:
        return self._children[0]

    @property
    def expression(self) -> Expression:
        return self._children[2]

    @classmethod
    def process(cls, children):
        return super().process(children)

    def serialize(self) -> Any:
        return {self.identifier.serialize(): self.expression.serialize()}


class NewLineOrCommentRule(LarkRule):

    _children: List[LarkToken]

    @staticmethod
    def rule_name() -> str:
        return "new_line_or_comment"

    def serialize(self) -> Any:
        return TokenSequence(self._children).joined()

    def actual_comments(self) -> Optional[List[str]]:
        comment = self.serialize()
        if comment == "\n":
            return None
        comment = comment.strip()

        comments = comment.split("\n")

        result = []
        for comment in comments:
            if comment.startswith("//"):
                comment = comment[2:]

            elif comment.startswith("#"):
                comment = comment[1:]

            if comment != "":
                result.append(comment.strip())

        return result
