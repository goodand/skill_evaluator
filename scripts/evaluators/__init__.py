"""Layer Evaluators 패키지.

각 evaluator는 동일한 인터페이스를 제공:
  - check_* 함수들: SkillMetadata → MetricResult
  - evaluate() 함수: SkillMetadata → LayerResult

사용 예:
    from evaluators.l1_structural import evaluate as evaluate_l1
    result = evaluate_l1(skill)
"""

from evaluators.base import run_layer_evaluation
from evaluators.l1_structural import evaluate as evaluate_l1
from evaluators.l2_activation import evaluate as evaluate_l2
from evaluators.l3_retrieval import evaluate as evaluate_l3
from evaluators.l4_workflow import evaluate as evaluate_l4
from evaluators.l5_execution import evaluate as evaluate_l5
from evaluators.l6_validation import evaluate as evaluate_l6
from evaluators.ecosystem import evaluate_ecosystem

LAYERS = {
    "L1": evaluate_l1,
    "L2": evaluate_l2,
    "L3": evaluate_l3,
    "L4": evaluate_l4,
    "L5": evaluate_l5,
    "L6": evaluate_l6,
}

__all__ = [
    "LAYERS",
    "evaluate_l1", "evaluate_l2", "evaluate_l3",
    "evaluate_l4", "evaluate_l5", "evaluate_l6",
    "evaluate_ecosystem",
    "run_layer_evaluation",
]
