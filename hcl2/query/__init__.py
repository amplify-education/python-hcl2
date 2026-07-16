"""Query facades for navigating HCL2 LarkElement trees."""

from hcl2.query._base import NodeView, register_view, view_for
from hcl2.query.attributes import AttributeView
from hcl2.query.blocks import BlockView
from hcl2.query.body import BodyView, DocumentView
from hcl2.query.builtins import BUILTIN_NAMES, apply_builtin
from hcl2.query.containers import ObjectView, TupleView
from hcl2.query.expressions import ConditionalView
from hcl2.query.for_exprs import ForObjectView, ForTupleView
from hcl2.query.functions import FunctionCallView
from hcl2.query.pipeline import (
    BuiltinStage,
    PathStage,
    SelectStage,
    classify_stage,
    execute_pipeline,
    split_pipeline,
)
from hcl2.query.predicate import evaluate_predicate, parse_predicate

__all__ = [
    "NodeView",
    "view_for",
    "register_view",
    "DocumentView",
    "BodyView",
    "BlockView",
    "AttributeView",
    "TupleView",
    "ObjectView",
    "ForTupleView",
    "ForObjectView",
    "FunctionCallView",
    "ConditionalView",
    "split_pipeline",
    "classify_stage",
    "execute_pipeline",
    "PathStage",
    "BuiltinStage",
    "SelectStage",
    "apply_builtin",
    "BUILTIN_NAMES",
    "parse_predicate",
    "evaluate_predicate",
]
