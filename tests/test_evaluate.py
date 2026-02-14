"""L1 evaluator 단위 테스트 + CLI 통합 테스트.

리팩토링 후: check_* 함수는 evaluators.l1_structural에서 import.
"""

import json
import subprocess
import sys
import pytest
from pathlib import Path

from models import SkillMetadata, TriggerInfo, MetricResult, LayerResult
from evaluators.l1_structural import (
    check_yaml_validity,
    check_directory_structure,
    check_resource_independence,
    evaluate as evaluate_l1,
)
from helpers import SKILLS_ROOT, TROUBLESHOOTING_COT_DIR, make_skill
from discovery import parse_skill_md


# ──────────────────────────────────────────────
# check_yaml_validity
# ──────────────────────────────────────────────

class TestCheckYamlValidity:

    def test_full_metadata(self, tmp_path):
        """name(다름) + description + triggers = 30점 만점."""
        skill = make_skill(
            tmp_path,
            name="my-special-skill",
            dir_name="skill-dir-1",
            description="A useful tool",
            triggers=["debug", "analyze"],
        )
        result = check_yaml_validity(skill)
        assert result.name == "yaml_validity"
        assert result.max_score == 30.0
        assert result.score == 30.0  # 10(name) + 10(desc) + 10(triggers)
        assert result.passed is True

    def test_minimal_no_triggers(self, tmp_path):
        """name(다름) + description, triggers 없음 = 20점."""
        skill = make_skill(
            tmp_path,
            name="plain-skill",
            dir_name="skill-dir-2",
            description="No triggers here",
        )
        result = check_yaml_validity(skill)
        assert result.score == 20.0  # 10(name) + 10(desc) + 0(triggers)
        assert result.passed is True  # 20 >= 20

    def test_name_same_as_dir(self, tmp_path):
        """name이 디렉토리명과 동일하면 5점."""
        skill_dir = tmp_path / "same-name"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: same-name\ndescription: test desc\n---\n",
            encoding="utf-8",
        )
        skill = parse_skill_md(skill_dir)
        result = check_yaml_validity(skill)
        # name == dir name: 5점 + description: 10점 + triggers 0점 = 15점
        assert result.score == 15.0
        assert result.passed is False  # 15 < 20

    def test_no_description(self, tmp_path):
        """description 없으면 10점 감소."""
        skill_dir = tmp_path / "no-desc"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: no-desc\n---\n",
            encoding="utf-8",
        )
        skill = parse_skill_md(skill_dir)
        result = check_yaml_validity(skill)
        # name == dir name: 5점, no description: 0점, no triggers: 0점
        assert result.score == 5.0
        assert result.passed is False

    def test_no_frontmatter(self, tmp_path):
        """frontmatter 없으면 최저 점수."""
        skill_dir = tmp_path / "bare"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("# Just markdown\n", encoding="utf-8")
        skill = parse_skill_md(skill_dir)
        result = check_yaml_validity(skill)
        # name fallback to dir name (== dir name => 5), no desc, no triggers
        assert result.score == 5.0


# ──────────────────────────────────────────────
# check_directory_structure
# ──────────────────────────────────────────────

class TestCheckDirectoryStructure:

    def test_full_structure(self, tmp_path):
        """모든 디렉토리 존재 시 최대 점수 (40점 캡)."""
        skill = make_skill(
            tmp_path,
            name="full-struct",
            create_scripts=True,
            create_references=True,
            create_tests=True,
            create_design_decision=True,
        )
        result = check_directory_structure(skill)
        assert result.name == "directory_structure"
        assert result.max_score == 40.0
        # 10(SKILL.md) + 15(scripts) + 10(refs) + 5(tests) + 3(design) = 43 -> capped at 40
        assert result.score == 40.0
        assert result.passed is True

    def test_minimal_structure(self, tmp_path):
        """SKILL.md만 존재 = 10점."""
        skill = make_skill(tmp_path, name="minimal-struct")
        result = check_directory_structure(skill)
        assert result.score == 10.0  # SKILL.md만
        assert result.passed is False  # 10 < 20

    def test_scripts_only(self, tmp_path):
        """scripts/ 만 있으면 25점."""
        skill = make_skill(tmp_path, name="scripts-only", create_scripts=True)
        result = check_directory_structure(skill)
        assert result.score == 25.0  # 10 + 15
        assert result.passed is True

    def test_without_optional_dirs(self, tmp_path):
        """scripts + references (선택적 디렉토리 없이)."""
        skill = make_skill(
            tmp_path,
            name="no-optional",
            create_scripts=True,
            create_references=True,
        )
        result = check_directory_structure(skill)
        assert result.score == 35.0  # 10 + 15 + 10
        assert result.passed is True

    def test_details_contains_file_counts(self, tmp_path):
        """details 문자열에 파일 개수 포함."""
        skill = make_skill(
            tmp_path,
            name="count-check",
            create_scripts=True,
            script_contents={"a.py": "# a", "b.py": "# b"},
        )
        result = check_directory_structure(skill)
        assert "2 files" in result.details


# ──────────────────────────────────────────────
# check_resource_independence
# ──────────────────────────────────────────────

class TestCheckResourceIndependence:

    def test_no_scripts_dir(self, tmp_path):
        """scripts/ 없으면 부분 점수 15."""
        skill = make_skill(tmp_path, name="no-scripts")
        result = check_resource_independence(skill)
        assert result.name == "resource_independence"
        assert result.score == 15.0
        assert result.max_score == 30.0
        assert result.passed is True

    def test_clean_scripts_with_relative_path(self, tmp_path):
        """하드코딩 경로 없고 Path(__file__) 사용 = 30점."""
        skill = make_skill(
            tmp_path,
            name="clean-skill",
            script_contents={
                "main.py": (
                    "from pathlib import Path\n"
                    "BASE = Path(__file__).parent\n"
                    "data = BASE / 'data.json'\n"
                ),
            },
        )
        result = check_resource_independence(skill)
        assert result.score == 30.0
        assert result.passed is True
        assert "하드코딩 절대경로 없음" in result.details

    def test_hardcoded_path_detected(self, tmp_path):
        """하드코딩 절대경로 있으면 감점."""
        skill = make_skill(
            tmp_path,
            name="hardcoded-skill",
            script_contents={
                "main.py": (
                    "# bad practice\n"
                    'path = "/Users/someone/project/data.json"\n'
                ),
            },
        )
        result = check_resource_independence(skill)
        # 30 - 10(hardcode) - 5(no relative) = 15
        assert result.score == 15.0
        assert result.passed is True  # 15 >= 15
        assert "하드코딩 경로 발견" in result.details

    def test_multiple_hardcoded_files(self, tmp_path):
        """여러 파일에 하드코딩 경로 = 큰 감점."""
        skill = make_skill(
            tmp_path,
            name="multi-hardcode",
            script_contents={
                "file1.py": 'x = "/Users/dev/file"\n',
                "file2.py": 'y = "/home/user/data"\n',
                "file3.py": 'z = "/mnt/shared/stuff"\n',
            },
        )
        result = check_resource_independence(skill)
        # 30 - 10*3 - 5 = -5 -> max(0, -5) = 0
        assert result.score == 0.0
        assert result.passed is False


# ──────────────────────────────────────────────
# evaluate (L1)
# ──────────────────────────────────────────────

class TestEvaluateL1:

    def test_evaluate_l1_returns_layer_result(self, tmp_path):
        """L1 평가 결과의 기본 구조 검증."""
        skill = make_skill(
            tmp_path,
            name="eval-test",
            description="Testing evaluation",
            triggers=["test"],
            create_scripts=True,
            create_references=True,
            script_contents={"main.py": "from pathlib import Path\nBASE = Path(__file__).parent\n"},
        )
        result = evaluate_l1(skill)
        assert isinstance(result, LayerResult)
        assert result.layer == "L1"
        assert result.skill_name == "eval-test"
        assert len(result.metrics) == 3
        assert result.overall_score > 0

        metric_names = [m.name for m in result.metrics]
        assert "yaml_validity" in metric_names
        assert "directory_structure" in metric_names
        assert "resource_independence" in metric_names

    def test_evaluate_l1_perfect_score(self, tmp_path):
        """모든 조건 충족 시 100점."""
        skill = make_skill(
            tmp_path,
            name="perfect-skill",
            dir_name="skill-dir-3",
            description="Perfect test skill for evaluation",
            triggers=["keyword1", "keyword2"],
            create_scripts=True,
            create_references=True,
            create_tests=True,
            create_design_decision=True,
            script_contents={"main.py": "from pathlib import Path\nBASE = Path(__file__).parent\n"},
        )
        result = evaluate_l1(skill)
        assert result.overall_score == 100.0
        assert result.recommendations == []

    def test_evaluate_l1_generates_recommendations(self, tmp_path):
        """failed 메트릭이 있으면 recommendations 생성."""
        skill = make_skill(tmp_path, name="weak-skill")
        result = evaluate_l1(skill)
        assert len(result.recommendations) >= 1

    @pytest.mark.integration
    def test_evaluate_l1_real_skill(self):
        """실제 troubleshooting-cot-2 스킬의 L1 평가."""
        skill = parse_skill_md(TROUBLESHOOTING_COT_DIR)
        assert skill is not None

        result = evaluate_l1(skill)
        assert result.layer == "L1"
        assert result.skill_name == "troubleshooting-cot"
        assert result.overall_score > 50.0
        assert len(result.metrics) == 3

        yaml_metric = next(m for m in result.metrics if m.name == "yaml_validity")
        dir_metric = next(m for m in result.metrics if m.name == "directory_structure")

        assert yaml_metric.score >= 20.0
        assert dir_metric.score >= 25.0


# ──────────────────────────────────────────────
# CLI subprocess 테스트
# ──────────────────────────────────────────────

EVALUATE_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "evaluate.py"


class TestCLI:

    @pytest.mark.integration
    def test_cli_json_output(self):
        """CLI --format json 출력이 유효한 JSON인지 확인."""
        result = subprocess.run(
            [
                sys.executable, str(EVALUATE_SCRIPT),
                "--skills-root", str(SKILLS_ROOT),
                "--format", "json",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        data = json.loads(result.stdout)
        assert len(data["skills"]) == 8
        assert data["summary"]["total_skills"] == 8
        # 각 스킬에 layers와 weighted_score 존재
        for skill in data["skills"]:
            assert "layers" in skill
            assert "weighted_score" in skill
            assert "name" in skill

    @pytest.mark.integration
    def test_cli_text_output(self):
        """CLI 기본 텍스트 출력 확인."""
        result = subprocess.run(
            [
                sys.executable, str(EVALUATE_SCRIPT),
                "--skills-root", str(SKILLS_ROOT),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert "Skill Evaluator" in result.stdout
        assert "Weighted:" in result.stdout

    @pytest.mark.integration
    def test_cli_single_skill(self):
        """CLI --skill 옵션으로 특정 스킬만 평가."""
        result = subprocess.run(
            [
                sys.executable, str(EVALUATE_SCRIPT),
                "--skills-root", str(SKILLS_ROOT),
                "--skill", "troubleshooting-cot",
                "--format", "json",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        data = json.loads(result.stdout)
        assert len(data["skills"]) == 1
        assert data["skills"][0]["name"] == "troubleshooting-cot"

    @pytest.mark.integration
    def test_cli_single_layer(self):
        """CLI --layer 옵션으로 특정 레이어만 평가."""
        result = subprocess.run(
            [
                sys.executable, str(EVALUATE_SCRIPT),
                "--skills-root", str(SKILLS_ROOT),
                "--skill", "troubleshooting-cot",
                "--layer", "L1,L4",
                "--format", "json",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        data = json.loads(result.stdout)
        skill = data["skills"][0]
        assert "L1" in skill["layers"]
        assert "L4" in skill["layers"]
        assert "L2" not in skill["layers"]

    @pytest.mark.integration
    def test_cli_output_to_file(self, tmp_path):
        """CLI -o 옵션으로 파일 출력."""
        outfile = tmp_path / "result.json"
        result = subprocess.run(
            [
                sys.executable, str(EVALUATE_SCRIPT),
                "--skills-root", str(SKILLS_ROOT),
                "--format", "json",
                "-o", str(outfile),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert outfile.exists()
        data = json.loads(outfile.read_text(encoding="utf-8"))
        assert "skills" in data
        assert "summary" in data

    def test_cli_nonexistent_root(self, tmp_path):
        """존재하지 않는 디렉토리면 exit code 1."""
        result = subprocess.run(
            [
                sys.executable, str(EVALUATE_SCRIPT),
                "--skills-root", str(tmp_path / "nonexistent"),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 1

    def test_cli_empty_root(self, tmp_path):
        """스킬 없는 빈 디렉토리면 exit code 1."""
        result = subprocess.run(
            [
                sys.executable, str(EVALUATE_SCRIPT),
                "--skills-root", str(tmp_path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 1
        assert "No skills found" in result.stderr

    def test_cli_workers_results_equivalent(self, tmp_path):
        """--workers 1/2 결과가 동일해야 한다."""
        make_skill(
            tmp_path,
            name="worker-skill-a",
            create_scripts=True,
            script_contents={"a.py": "#!/usr/bin/env python3\n\"\"\"x\"\"\"\n"},
            create_references=True,
            reference_contents={"guide.md": "# Guide\nline\nline\nline\nline\nline\n"},
        )
        make_skill(
            tmp_path,
            name="worker-skill-b",
            create_scripts=True,
            script_contents={"b.py": "#!/usr/bin/env python3\n\"\"\"x\"\"\"\n"},
            create_references=True,
            reference_contents={"guide.md": "# Guide\nline\nline\nline\nline\nline\n"},
        )

        cmd_base = [
            sys.executable, str(EVALUATE_SCRIPT),
            "--skills-root", str(tmp_path),
            "--format", "json",
        ]
        seq = subprocess.run(
            cmd_base + ["--workers", "1"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        par = subprocess.run(
            cmd_base + ["--workers", "2"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert seq.returncode == 0, f"stderr: {seq.stderr}"
        assert par.returncode == 0, f"stderr: {par.stderr}"

        data_seq = json.loads(seq.stdout)
        data_par = json.loads(par.stdout)
        assert data_seq["summary"] == data_par["summary"]
        seq_skills = sorted(data_seq["skills"], key=lambda x: x["name"])
        par_skills = sorted(data_par["skills"], key=lambda x: x["name"])
        assert seq_skills == par_skills

    @pytest.mark.integration
    def test_cli_skill_not_found(self):
        """존재하지 않는 스킬 이름이면 exit code 1."""
        result = subprocess.run(
            [
                sys.executable, str(EVALUATE_SCRIPT),
                "--skills-root", str(SKILLS_ROOT),
                "--skill", "nonexistent-skill-xyz",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 1
        assert "not found" in result.stderr

    @pytest.mark.integration
    def test_cli_markdown_output(self):
        """CLI --format markdown 출력 확인."""
        result = subprocess.run(
            [
                sys.executable, str(EVALUATE_SCRIPT),
                "--skills-root", str(SKILLS_ROOT),
                "--skill", "troubleshooting-cot",
                "--format", "markdown",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert "# Skill Evaluation Report" in result.stdout
        assert "troubleshooting-cot" in result.stdout

    @pytest.mark.integration
    def test_cli_ecosystem(self):
        """CLI --ecosystem 옵션 확인."""
        result = subprocess.run(
            [
                sys.executable, str(EVALUATE_SCRIPT),
                "--skills-root", str(SKILLS_ROOT),
                "--ecosystem",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert "Ecosystem Health" in result.stdout

    @pytest.mark.integration
    def test_cli_ci_mode(self):
        """CLI --ci-mode 옵션 확인."""
        result = subprocess.run(
            [
                sys.executable, str(EVALUATE_SCRIPT),
                "--skills-root", str(SKILLS_ROOT),
                "--ci-mode",
                "--threshold", "30.0",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert "CI PASSED" in result.stderr

    @pytest.mark.integration
    def test_cli_show_history(self):
        """CLI --show-history 옵션 확인."""
        result = subprocess.run(
            [
                sys.executable, str(EVALUATE_SCRIPT),
                "--show-history",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        # show-history는 skills-root 없이도 동작
        assert result.returncode == 0
