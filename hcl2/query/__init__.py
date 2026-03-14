"""Query facades for navigating HCL2 LarkElement trees."""

from hcl2.query._base import NodeView, view_for, register_view
from hcl2.query.body import DocumentView, BodyView
from hcl2.query.blocks import BlockView
from hcl2.query.attributes import AttributeView
from hcl2.query.containers import TupleView, ObjectView
from hcl2.query.for_exprs import ForTupleView, ForObjectView
from hcl2.query.functions import FunctionCallView
from hcl2.query.expressions import ConditionalView
from hcl2.query.pipeline import (
    split_pipeline,
    classify_stage,
    execute_pipeline,
    PathStage,
    BuiltinStage,
    SelectStage,
)
from hcl2.query.builtins import apply_builtin, BUILTIN_NAMES
from hcl2.query.predicate import parse_predicate, evaluate_predicate

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
