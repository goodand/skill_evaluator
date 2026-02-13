"""L2-L6 evaluator 단위 테스트."""

import pytest
from pathlib import Path

from models import MetricResult, LayerResult
from helpers import make_skill

from evaluators.l2_activation import (
    check_trigger_count,
    check_trigger_specificity,
    check_trigger_overlap,
    evaluate as evaluate_l2,
)
from evaluators.l3_retrieval import (
    check_reference_count,
    check_reference_type_coverage,
    check_progressive_disclosure,
    check_reference_freshness,
    evaluate as evaluate_l3,
)
from evaluators.l4_workflow import (
    check_workflow_structure,
    check_plan_adherence,
    evaluate as evaluate_l4,
)
from evaluators.l5_execution import (
    check_script_count,
    check_shebang,
    check_cli_interface,
    check_docstrings,
    check_bridge_availability,
    check_function_quality,
    check_code_complexity,
    evaluate as evaluate_l5,
)
from evaluators.l6_validation import (
    check_verification_infra,
    check_error_handling,
    check_faithfulness,
    evaluate as evaluate_l6,
)


# ══════════════════════════════════════════════
# L2: 활성화 신뢰성
# ══════════════════════════════════════════════

class TestL2TriggerCount:

    def test_no_triggers(self, tmp_path):
        skill = make_skill(tmp_path, name="no-trig", description="Simple tool")
        result = check_trigger_count(skill)
        assert result.score == 0
        assert result.passed is False

    def test_optimal_range(self, tmp_path):
        skill = make_skill(
            tmp_path, name="opt-trig",
            triggers=["kw1", "kw2", "kw3", "kw4", "kw5", "kw6", "kw7", "kw8"],
        )
        result = check_trigger_count(skill)
        assert result.score == 15  # 8-15 optimal
        assert result.passed is True

    def test_few_triggers(self, tmp_path):
        skill = make_skill(tmp_path, name="few-trig", triggers=["one"])
        result = check_trigger_count(skill)
        assert result.score == 5  # <= 2

    def test_moderate_triggers(self, tmp_path):
        skill = make_skill(tmp_path, name="mod-trig", triggers=["a", "b", "c", "d"])
        result = check_trigger_count(skill)
        assert result.score == 10  # 3-7


class TestL2TriggerSpecificity:

    def test_all_specific(self, tmp_path):
        skill = make_skill(
            tmp_path, name="spec",
            triggers=["phantom dependency", "circular import", "bisect"],
        )
        result = check_trigger_specificity(skill)
        assert result.score == 15  # 100% specific

    def test_all_generic(self, tmp_path):
        skill = make_skill(
            tmp_path, name="gen",
            triggers=["분석", "도와줘", "확인"],
        )
        result = check_trigger_specificity(skill)
        assert result.score == 3  # 0% specific

    def test_no_keywords(self, tmp_path):
        skill = make_skill(tmp_path, name="none", description="No triggers")
        result = check_trigger_specificity(skill)
        assert result.score == 0
        assert result.passed is False


class TestL2TriggerOverlap:

    def test_no_overlap(self, tmp_path):
        s1 = make_skill(tmp_path, name="s1", triggers=["alpha", "beta"])
        s2 = make_skill(tmp_path, name="s2", triggers=["gamma", "delta"])
        result = check_trigger_overlap(s1, [s1, s2])
        assert result.score == 10

    def test_with_overlap(self, tmp_path):
        s1 = make_skill(tmp_path, name="s1", triggers=["alpha", "beta", "shared"])
        s2 = make_skill(tmp_path, name="s2", triggers=["gamma", "shared"])
        result = check_trigger_overlap(s1, [s1, s2])
        assert result.score < 10  # overlap detected

    def test_no_keywords(self, tmp_path):
        s1 = make_skill(tmp_path, name="s1", description="No triggers")
        result = check_trigger_overlap(s1, [s1])
        assert result.score == 0
        assert result.passed is False


class TestL2Evaluate:

    def test_returns_layer_result(self, tmp_path):
        skill = make_skill(tmp_path, name="l2-eval", triggers=["debug", "analyze"])
        result = evaluate_l2(skill, all_skills=[skill])
        assert isinstance(result, LayerResult)
        assert result.layer == "L2"
        assert len(result.metrics) == 3


# ══════════════════════════════════════════════
# L3: 검색 품질
# ══════════════════════════════════════════════

class TestL3ReferenceCount:

    def test_no_references(self, tmp_path):
        skill = make_skill(tmp_path, name="no-ref")
        result = check_reference_count(skill)
        assert result.score == 0
        assert result.passed is False

    def test_one_reference(self, tmp_path):
        skill = make_skill(tmp_path, name="one-ref", create_references=True)
        result = check_reference_count(skill)
        assert result.score == 10

    def test_many_references(self, tmp_path):
        skill = make_skill(
            tmp_path, name="many-ref",
            reference_contents={"a.md": "# A", "b.md": "# B", "c.md": "# C"},
        )
        result = check_reference_count(skill)
        assert result.score == 20  # 3+ = 만점


class TestL3ReferenceTypeCoverage:

    def test_no_references(self, tmp_path):
        skill = make_skill(tmp_path, name="no-ref-type")
        result = check_reference_type_coverage(skill)
        assert result.score == 0

    def test_api_and_example(self, tmp_path):
        skill = make_skill(
            tmp_path, name="typed-ref",
            reference_contents={"api_guide.md": "# API", "example_data.json": "{}"},
        )
        result = check_reference_type_coverage(skill)
        assert result.score == 10  # 2 types * 5


class TestL3ProgressiveDisclosure:

    def test_concise_skill_md(self, tmp_path):
        skill = make_skill(tmp_path, name="concise")
        result = check_progressive_disclosure(skill)
        assert result.score == 10  # < 200 lines

    def test_long_skill_md(self, tmp_path):
        long_body = "\n".join([f"Line {i}" for i in range(600)])
        skill = make_skill(tmp_path, name="long-md", skill_md_body=long_body)
        result = check_progressive_disclosure(skill)
        assert result.score == 2  # 500+ lines


class TestL3Evaluate:

    def test_returns_layer_result(self, tmp_path):
        skill = make_skill(
            tmp_path, name="l3-eval",
            create_references=True,
        )
        result = evaluate_l3(skill)
        assert isinstance(result, LayerResult)
        assert result.layer == "L3"
        assert len(result.metrics) == 5


# ══════════════════════════════════════════════
# L4: 워크플로우 충실도
# ══════════════════════════════════════════════

class TestL4WorkflowStructure:

    def test_no_workflow(self, tmp_path):
        skill = make_skill(tmp_path, name="no-wf")
        result = check_workflow_structure(skill)
        assert result.score == 0
        assert result.passed is False

    def test_with_phases(self, tmp_path):
        body = "# Title\n\n## Workflow\nPhase 1: Init\nPhase 2: Analyze\nPhase 3: Report\n"
        skill = make_skill(tmp_path, name="phased", skill_md_body=body)
        result = check_workflow_structure(skill)
        assert result.score >= 35  # 20(감지) + 15(3+단계)
        assert result.passed is True

    def test_with_pipeline_and_conditional(self, tmp_path):
        body = "# Title\n\nPipeline:\nStep 1 ──► Step 2\nskip if not needed\n"
        skill = make_skill(tmp_path, name="pipeline-wf", skill_md_body=body)
        result = check_workflow_structure(skill)
        assert result.passed is True


class TestL4PlanAdherence:

    def test_no_markers(self, tmp_path):
        skill = make_skill(tmp_path, name="no-plan")
        result = check_plan_adherence(skill)
        assert result.score == 0
        assert result.passed is False

    def test_with_checklist(self, tmp_path):
        body = "# Title\n\n- [x] Done\n- [ ] Pending\n- [x] Also done\n"
        skill = make_skill(tmp_path, name="checklist", skill_md_body=body)
        result = check_plan_adherence(skill)
        assert result.score >= 8  # 체크리스트 감지

    def test_with_when_to_use(self, tmp_path):
        body = "# Title\n\n## When to Use\nUse this when...\n\n## Don't Use\nDon't use when...\n"
        skill = make_skill(tmp_path, name="when-use", skill_md_body=body)
        result = check_plan_adherence(skill)
        assert result.score >= 5  # when_to_use + dont_use


class TestL4Evaluate:

    def test_returns_layer_result(self, tmp_path):
        body = "# Title\n\nPhase 1: Init\nPhase 2: Work\n- [x] Done\n"
        skill = make_skill(tmp_path, name="l4-eval", skill_md_body=body)
        result = evaluate_l4(skill)
        assert isinstance(result, LayerResult)
        assert result.layer == "L4"
        assert len(result.metrics) == 2


# ══════════════════════════════════════════════
# L5: 실행 정밀도
# ══════════════════════════════════════════════

class TestL5ScriptCount:

    def test_no_scripts(self, tmp_path):
        skill = make_skill(tmp_path, name="no-scripts")
        result = check_script_count(skill)
        assert result.score == 0
        assert result.passed is False

    def test_some_scripts(self, tmp_path):
        skill = make_skill(
            tmp_path, name="some-scripts",
            script_contents={"a.py": "# a", "b.py": "# b"},
        )
        result = check_script_count(skill)
        assert result.score == 6  # 2 * 3 = 6, cap 10
        assert result.passed is True

    def test_many_scripts(self, tmp_path):
        contents = {f"s{i}.py": f"# s{i}" for i in range(5)}
        skill = make_skill(tmp_path, name="many-scripts", script_contents=contents)
        result = check_script_count(skill)
        assert result.score == 10  # 5 * 3 = 15 -> cap 10


class TestL5Shebang:

    def test_with_shebang(self, tmp_path):
        skill = make_skill(
            tmp_path, name="shebang-ok",
            script_contents={"main.py": "#!/usr/bin/env python3\n# code"},
        )
        result = check_shebang(skill)
        assert result.score == 10

    def test_without_shebang(self, tmp_path):
        skill = make_skill(
            tmp_path, name="no-shebang",
            script_contents={"main.py": "# no shebang\nprint('hi')"},
        )
        result = check_shebang(skill)
        assert result.score == 0

    def test_no_scripts_dir(self, tmp_path):
        skill = make_skill(tmp_path, name="no-scripts-dir")
        result = check_shebang(skill)
        assert result.score == 0
        assert result.passed is False


class TestL5CliInterface:

    def test_with_argparse(self, tmp_path):
        skill = make_skill(
            tmp_path, name="cli-ok",
            script_contents={
                "main.py": (
                    "import argparse\n"
                    "parser = argparse.ArgumentParser()\n"
                    "parser.add_argument('--input')\n"
                ),
            },
        )
        result = check_cli_interface(skill)
        assert result.score == 10  # 7(argparse) + 3(add_argument)

    def test_no_cli(self, tmp_path):
        skill = make_skill(
            tmp_path, name="no-cli",
            script_contents={"main.py": "print('hello')"},
        )
        result = check_cli_interface(skill)
        assert result.score == 0


class TestL5Docstrings:

    def test_with_docstring(self, tmp_path):
        skill = make_skill(
            tmp_path, name="docstring-ok",
            script_contents={"main.py": '"""Module docstring."""\nprint("hi")'},
        )
        result = check_docstrings(skill)
        assert result.score == 10  # 100% coverage

    def test_without_docstring(self, tmp_path):
        skill = make_skill(
            tmp_path, name="no-docstring",
            script_contents={"main.py": "# No docstring\nprint('hi')"},
        )
        result = check_docstrings(skill)
        assert result.score == 0


class TestL5BridgeAvailability:

    def test_no_bridge(self, tmp_path):
        skill = make_skill(
            tmp_path, name="no-bridge",
            script_contents={"main.py": "# code"},
        )
        result = check_bridge_availability(skill)
        assert result.score == 0
        assert result.passed is True  # bridge는 선택사항

    def test_with_bridge_script(self, tmp_path):
        skill = make_skill(
            tmp_path, name="bridge-script",
            script_contents={"bridge_other.py": "# bridge code"},
        )
        result = check_bridge_availability(skill)
        assert result.score == 10

    def test_with_bridges_dir(self, tmp_path):
        skill = make_skill(tmp_path, name="bridge-dir", create_scripts=True)
        # bridges/ 디렉토리 직접 생성
        (tmp_path / "bridge-dir" / "bridges").mkdir()
        # re-parse to pick up bridges dir
        from discovery import parse_skill_md
        skill = parse_skill_md(tmp_path / "bridge-dir")
        result = check_bridge_availability(skill)
        assert result.score == 10


class TestL5FunctionQuality:

    def test_good_functions(self, tmp_path):
        skill = make_skill(
            tmp_path, name="good-funcs",
            script_contents={
                "main.py": (
                    '"""Module."""\n'
                    "def analyze(data: list) -> dict:\n"
                    '    """Analyze the data."""\n'
                    "    return {}\n\n"
                    "def process(items: list) -> None:\n"
                    '    """Process items."""\n'
                    "    pass\n"
                ),
            },
        )
        result = check_function_quality(skill)
        assert result.score >= 10  # good docstring + type hint coverage

    def test_no_functions(self, tmp_path):
        skill = make_skill(
            tmp_path, name="no-funcs",
            script_contents={"main.py": "x = 1\ny = 2\n"},
        )
        result = check_function_quality(skill)
        assert result.score == 5  # 함수 없음 기본 점수


class TestL5CodeComplexity:

    def test_no_scripts(self, tmp_path):
        skill = make_skill(tmp_path, name="no-scripts-cc")
        result = check_code_complexity(skill)
        assert result.score == 0
        assert result.passed is False

    def test_simple_functions(self, tmp_path):
        """단순 함수 = 낮은 CC = 만점."""
        skill = make_skill(
            tmp_path, name="simple-cc",
            script_contents={
                "main.py": (
                    "def add(a, b):\n"
                    "    return a + b\n\n"
                    "def greet(name):\n"
                    "    print(f'Hello {name}')\n"
                ),
            },
        )
        result = check_code_complexity(skill)
        assert result.score == 15  # avg CC = 1.0
        assert result.passed is True
        assert "평균 CC=1.0" in result.details

    def test_complex_function(self, tmp_path):
        """분기가 많은 함수 = 높은 CC."""
        skill = make_skill(
            tmp_path, name="complex-cc",
            script_contents={
                "main.py": (
                    "def process(data):\n"
                    "    if not data:\n"
                    "        return None\n"
                    "    for item in data:\n"
                    "        if item > 0:\n"
                    "            if item > 100:\n"
                    "                print('big')\n"
                    "            elif item > 50:\n"
                    "                print('medium')\n"
                    "            else:\n"
                    "                print('small')\n"
                    "        elif item == 0:\n"
                    "            continue\n"
                    "        else:\n"
                    "            try:\n"
                    "                abs(item)\n"
                    "            except ValueError:\n"
                    "                pass\n"
                ),
            },
        )
        result = check_code_complexity(skill)
        assert result.score < 15  # high CC
        assert "최대 CC=" in result.details

    def test_no_functions(self, tmp_path):
        """함수 없는 스크립트 = 기본 점수."""
        skill = make_skill(
            tmp_path, name="no-funcs-cc",
            script_contents={"main.py": "x = 1\ny = 2\nprint(x + y)\n"},
        )
        result = check_code_complexity(skill)
        assert result.score == 5  # 분석 가능한 함수 없음

    def test_syntax_error_handled(self, tmp_path):
        """구문 오류 파일은 건너뜀."""
        skill = make_skill(
            tmp_path, name="syntax-err",
            script_contents={
                "bad.py": "def broken(\n",
                "good.py": "def ok():\n    pass\n",
            },
        )
        result = check_code_complexity(skill)
        assert result.score == 15  # only good.py analyzed, CC=1


class TestL5Evaluate:

    def test_returns_layer_result(self, tmp_path):
        skill = make_skill(
            tmp_path, name="l5-eval",
            script_contents={
                "main.py": (
                    '#!/usr/bin/env python3\n"""Module."""\n'
                    "import argparse\nparser = argparse.ArgumentParser()\n"
                    "parser.add_argument('--input')\n"
                ),
            },
        )
        result = evaluate_l5(skill)
        assert isinstance(result, LayerResult)
        assert result.layer == "L5"
        assert len(result.metrics) == 7  # 6 기존 + 1 code_complexity


# ══════════════════════════════════════════════
# L6: 검증 커버리지
# ══════════════════════════════════════════════

class TestL6VerificationInfra:

    def test_no_verification(self, tmp_path):
        skill = make_skill(tmp_path, name="no-verify")
        result = check_verification_infra(skill)
        assert result.score == 0
        assert result.passed is False

    def test_with_tests_dir(self, tmp_path):
        skill = make_skill(tmp_path, name="has-tests", create_tests=True)
        result = check_verification_infra(skill)
        assert result.score >= 20

    def test_with_verify_flag(self, tmp_path):
        skill = make_skill(
            tmp_path, name="verify-flag",
            create_tests=True,
            script_contents={"main.py": "parser.add_argument('--verify')"},
        )
        result = check_verification_infra(skill)
        assert result.score >= 35  # 20(tests) + 15(verify flag)


class TestL6ErrorHandling:

    def test_no_error_handling(self, tmp_path):
        skill = make_skill(
            tmp_path, name="no-err",
            script_contents={"main.py": "print('hi')"},
        )
        result = check_error_handling(skill)
        assert result.score == 0
        assert result.passed is False

    def test_full_error_handling(self, tmp_path):
        skill = make_skill(
            tmp_path, name="full-err",
            script_contents={
                "main.py": (
                    "import sys\n"
                    "try:\n"
                    "    result = process()\n"
                    "except ValueError as e:\n"
                    "    print(e)\n"
                    "    sys.exit(1)\n"
                ),
            },
        )
        result = check_error_handling(skill)
        assert result.score == 30  # try + specific except + sys.exit


class TestL6Faithfulness:

    def test_no_markers(self, tmp_path):
        skill = make_skill(tmp_path, name="no-faith")
        result = check_faithfulness(skill)
        assert result.score == 0

    def test_with_output_format_in_md(self, tmp_path):
        body = "# Title\n\n## Output Format\n```json\n{\"key\": \"value\"}\n```\n"
        skill = make_skill(tmp_path, name="output-md", skill_md_body=body)
        result = check_faithfulness(skill)
        assert result.score >= 5  # SKILL.md 내 출력 형식

    def test_with_output_reference(self, tmp_path):
        skill = make_skill(
            tmp_path, name="output-ref",
            reference_contents={"output_schema.json": '{"type": "object"}'},
        )
        result = check_faithfulness(skill)
        assert result.score >= 10  # output 형식 문서


class TestL6Evaluate:

    def test_returns_layer_result(self, tmp_path):
        skill = make_skill(
            tmp_path, name="l6-eval",
            create_tests=True,
            script_contents={
                "main.py": "import sys\ntry:\n    pass\nexcept ValueError:\n    sys.exit(1)\n",
            },
        )
        result = evaluate_l6(skill)
        assert isinstance(result, LayerResult)
        assert result.layer == "L6"
        assert len(result.metrics) == 3
