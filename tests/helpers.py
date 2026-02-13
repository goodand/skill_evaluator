"""테스트 공용 상수 + 스킬 팩토리 함수."""

import sys
from pathlib import Path

# scripts/ 디렉토리를 import 경로에 추가 (conftest.py에서도 하지만 독립 사용 가능하게)
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from discovery import parse_skill_md

# ──────────────────────────────────────────────
# 통합 테스트용 실제 스킬 경로 상수
# ──────────────────────────────────────────────

SKILLS_ROOT = Path(
    "/Users/jaehyuntak/Desktop/Project_____현재_진행중인"
    "/narrative-ai/.claude/skills"
)

TROUBLESHOOTING_COT_DIR = SKILLS_ROOT / "troubleshooting-cot-2"
DEPSOLVE_ANALYZER_DIR = SKILLS_ROOT / "depsolve-analyzer"


# ──────────────────────────────────────────────
# 공용 스킬 팩토리 함수
# ──────────────────────────────────────────────

def make_skill(
    tmp_path,
    *,
    name="test-skill",
    dir_name=None,
    description="A test skill",
    triggers=None,
    create_scripts=False,
    create_references=False,
    create_tests=False,
    create_design_decision=False,
    script_contents=None,
    reference_contents=None,
    skill_md_body="",
):
    """테스트용 스킬 디렉토리 생성 후 parse_skill_md 호출.

    Args:
        tmp_path: pytest tmp_path fixture
        name: 스킬 이름 (YAML name 필드)
        dir_name: 디렉토리 이름 (기본: name과 동일). name과 다르면 yaml_validity 만점 가능.
        description: 스킬 설명
        triggers: 트리거 키워드 리스트 (description에 추가)
        create_scripts: scripts/ 디렉토리 생성 여부
        create_references: references/ 디렉토리 생성 여부
        create_tests: tests/ 디렉토리 생성 여부
        create_design_decision: DESIGN_DECISION.md 생성 여부
        script_contents: dict[filename, content] - scripts/ 에 파일 생성
        reference_contents: dict[filename, content] - references/ 에 파일 생성
        skill_md_body: SKILL.md 본문 (frontmatter 아래 추가)
    """
    skill_dir = tmp_path / (dir_name or name)
    skill_dir.mkdir(exist_ok=True)

    trigger_str = ""
    if triggers:
        trigger_str = f" 트리거: {', '.join(triggers)}."

    skill_md = skill_dir / "SKILL.md"
    frontmatter = f"---\nname: {name}\ndescription: {description}{trigger_str}\n---\n"
    body = skill_md_body or "# Body\n"
    skill_md.write_text(frontmatter + body, encoding="utf-8")

    if create_scripts or script_contents:
        scripts_dir = skill_dir / "scripts"
        scripts_dir.mkdir(exist_ok=True)
        if script_contents:
            for fname, content in script_contents.items():
                (scripts_dir / fname).write_text(content, encoding="utf-8")
        else:
            (scripts_dir / "main.py").write_text("# placeholder", encoding="utf-8")

    if create_references or reference_contents:
        refs_dir = skill_dir / "references"
        refs_dir.mkdir(exist_ok=True)
        if reference_contents:
            for fname, content in reference_contents.items():
                (refs_dir / fname).write_text(content, encoding="utf-8")
        else:
            (refs_dir / "guide.md").write_text("# Guide", encoding="utf-8")

    if create_tests:
        (skill_dir / "tests").mkdir(exist_ok=True)

    if create_design_decision:
        (skill_dir / "DESIGN_DECISION.md").write_text("# Decisions", encoding="utf-8")

    return parse_skill_md(skill_dir)
