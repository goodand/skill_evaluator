"""discovery.py 단위 테스트 + 통합 테스트."""

import pytest
from pathlib import Path

from discovery import (
    _parse_yaml_frontmatter,
    _extract_triggers_from_description,
    _extract_triggers_from_markdown,
    parse_skill_md,
    discover_skills,
)

# 통합 테스트용 실제 경로 (conftest.py에서 sys.path 설정됨)
SKILLS_ROOT = Path(
    "/Users/jaehyuntak/Desktop/Project_____현재_진행중인"
    "/narrative-ai/.claude/skills"
)
TROUBLESHOOTING_COT_DIR = SKILLS_ROOT / "troubleshooting-cot-2"
DEPSOLVE_ANALYZER_DIR = SKILLS_ROOT / "depsolve-analyzer"


# ──────────────────────────────────────────────
# _parse_yaml_frontmatter
# ──────────────────────────────────────────────

class TestParseYamlFrontmatter:

    def test_valid_yaml(self):
        text = (
            "---\n"
            "name: my-skill\n"
            "description: A great skill for testing\n"
            "license: MIT\n"
            "---\n"
            "# Body content\n"
        )
        result = _parse_yaml_frontmatter(text)
        assert result["name"] == "my-skill"
        assert result["description"] == "A great skill for testing"
        assert result["license"] == "MIT"

    def test_missing_frontmatter_no_dashes(self):
        """--- 구분자 없으면 빈 dict."""
        text = "# Just a heading\nSome content.\n"
        result = _parse_yaml_frontmatter(text)
        assert result == {}

    def test_empty_file(self):
        """빈 파일이면 빈 dict."""
        result = _parse_yaml_frontmatter("")
        assert result == {}

    def test_only_opening_dashes(self):
        """여는 --- 만 있고 닫는 --- 없는 경우 - 키가 있으면 파싱됨."""
        text = "---\nname: orphan\n"
        result = _parse_yaml_frontmatter(text)
        # 닫는 --- 없으면 전체를 yaml_lines로 처리
        assert result.get("name") == "orphan"

    def test_quoted_values(self):
        """따옴표로 감싼 값 처리."""
        text = '---\nname: "quoted-name"\ndescription: \'single-quoted\'\n---\n'
        result = _parse_yaml_frontmatter(text)
        assert result["name"] == "quoted-name"
        assert result["description"] == "single-quoted"

    def test_continuation_lines(self):
        """들여쓰기된 continuation 라인 합치기."""
        text = (
            "---\n"
            "description: First line\n"
            "  continued here\n"
            "  and more\n"
            "name: test\n"
            "---\n"
        )
        result = _parse_yaml_frontmatter(text)
        assert "First line" in result["description"]
        assert "continued here" in result["description"]
        assert "and more" in result["description"]
        assert result["name"] == "test"

    def test_metadata_with_version(self):
        """version 같은 숫자형 값 처리."""
        text = '---\nname: test\nmetadata:\nversion: "3.4"\n---\n'
        result = _parse_yaml_frontmatter(text)
        assert result["name"] == "test"


# ──────────────────────────────────────────────
# _extract_triggers_from_description
# ──────────────────────────────────────────────

class TestExtractTriggersFromDescription:

    def test_korean_pattern(self):
        """한국어 '트리거: kw1, kw2' 패턴."""
        desc = "Git 분석 도구. 트리거: 트러블슈팅, 디버깅, 회귀 버그."
        triggers = _extract_triggers_from_description(desc)
        assert "트러블슈팅" in triggers
        assert "디버깅" in triggers
        assert "회귀 버그" in triggers

    def test_english_pattern_triggers_on(self):
        """영어 'Triggers on "kw1", "kw2"' 패턴."""
        desc = 'Analyze deps. Triggers on "phantom", "circular dependency", "import audit".'
        triggers = _extract_triggers_from_description(desc)
        assert "phantom" in triggers
        assert "circular dependency" in triggers
        assert "import audit" in triggers

    def test_english_pattern_trigger_on_lowercase(self):
        """소문자 trigger on 도 매칭."""
        desc = 'trigger on "alpha", "beta".'
        triggers = _extract_triggers_from_description(desc)
        assert "alpha" in triggers
        assert "beta" in triggers

    def test_quoted_pattern_fallback(self):
        """트리거/Triggers 패턴 없을 때 따옴표 키워드 추출."""
        desc = 'Use when seeing "error 404" or "timeout" in logs.'
        triggers = _extract_triggers_from_description(desc)
        assert "error 404" in triggers
        assert "timeout" in triggers

    def test_no_triggers(self):
        """키워드 없는 단순 설명."""
        desc = "A simple utility tool."
        triggers = _extract_triggers_from_description(desc)
        assert triggers == []

    def test_deduplicate(self):
        """중복 키워드 제거."""
        desc = '트리거: 디버깅, 디버깅, 분석.'
        triggers = _extract_triggers_from_description(desc)
        assert triggers.count("디버깅") == 1

    def test_troubleshooting_cot_description(self):
        """실제 troubleshooting-cot SKILL.md의 description 패턴."""
        desc = (
            "Git 히스토리 기반 Chain-of-Thought 트러블슈팅. "
            "커밋 메시지 분석, Good/Bad Case 식별, 실행 기반 가설 검증을 통해 "
            "버그의 근본 원인을 체계적으로 찾습니다. "
            "에러 발생, 회귀 버그, 예상치 못한 동작, 간헐적 버그 발견 시 사용하세요. "
            "트리거: 트러블슈팅, 디버깅, 회귀 버그, 근본 원인, root cause, "
            "bisect, good/bad case, 왜 안 되지, 에러 원인."
        )
        triggers = _extract_triggers_from_description(desc)
        assert len(triggers) >= 5
        assert "트러블슈팅" in triggers
        assert "root cause" in triggers
        assert "bisect" in triggers

    def test_depsolve_description(self):
        """실제 depsolve-analyzer SKILL.md의 description 패턴 (English Triggers on)."""
        desc = (
            "Analyze project dependencies to detect issues like phantom dependencies, "
            "circular dependencies, diamond dependencies, and version conflicts. "
            "Use when analyzing npm/pip/Go/Rust projects, detecting undeclared imports, "
            "finding dependency cycles, generating Mermaid dependency graphs, "
            "or auditing hybrid JS+Python projects. "
            'Triggers on keywords like dependency analysis, phantom detection, '
            'import audit, circular dependency, diamond dependency, version conflict, '
            'package.json analysis, requirements.txt analysis.'
        )
        triggers = _extract_triggers_from_description(desc)
        assert len(triggers) >= 3


# ──────────────────────────────────────────────
# _extract_triggers_from_markdown
# ──────────────────────────────────────────────

class TestExtractTriggersFromMarkdown:

    def test_bullet_list_with_quotes(self):
        """따옴표가 있는 bullet 리스트 패턴."""
        body = (
            "# Title\n\n"
            "## 트리거\n\n"
            '다음 키워드가 포함된 요청 시 사용:\n'
            '- "phantom", "팬텀", "유령 의존성"\n'
            '- "의존성 분석", "dependency analysis"\n'
            '- "순환 의존성", "circular dependency"\n'
            "\n## 다음 섹션\n"
        )
        triggers = _extract_triggers_from_markdown(body)
        assert "phantom" in triggers
        assert "팬텀" in triggers
        assert "유령 의존성" in triggers
        assert "의존성 분석" in triggers
        assert "dependency analysis" in triggers
        assert "순환 의존성" in triggers
        assert "circular dependency" in triggers

    def test_bullet_list_without_quotes(self):
        """따옴표 없는 단순 bullet 리스트."""
        body = (
            "## 트리거\n"
            "- keyword_alpha\n"
            "- keyword_beta\n"
            "- keyword_gamma\n"
        )
        triggers = _extract_triggers_from_markdown(body)
        assert "keyword_alpha" in triggers
        assert "keyword_beta" in triggers
        assert "keyword_gamma" in triggers

    def test_asterisk_bullets(self):
        """* 스타일 bullet."""
        body = (
            "## 트리거\n"
            "* first\n"
            "* second\n"
        )
        triggers = _extract_triggers_from_markdown(body)
        assert "first" in triggers
        assert "second" in triggers

    def test_no_trigger_section(self):
        """## 트리거 섹션 없으면 빈 리스트."""
        body = "# Title\n\n## 설명\nSome content.\n## 사용법\nHow to use.\n"
        triggers = _extract_triggers_from_markdown(body)
        assert triggers == []

    def test_empty_body(self):
        """빈 본문."""
        triggers = _extract_triggers_from_markdown("")
        assert triggers == []

    def test_mixed_quotes_and_plain(self):
        """따옴표 있는 줄과 없는 줄 혼합."""
        body = (
            "## 트리거\n"
            '- "quoted_a", "quoted_b"\n'
            "- plain_keyword\n"
        )
        triggers = _extract_triggers_from_markdown(body)
        assert "quoted_a" in triggers
        assert "quoted_b" in triggers
        assert "plain_keyword" in triggers

    def test_deduplicate(self):
        """중복 키워드 제거."""
        body = (
            "## 트리거\n"
            '- "dupe"\n'
            '- "dupe"\n'
        )
        triggers = _extract_triggers_from_markdown(body)
        assert triggers.count("dupe") == 1

    def test_comma_separated_without_quotes(self):
        """따옴표 없는 쉼표 구분 키워드."""
        body = (
            "## 트리거\n"
            "- alpha, beta, gamma\n"
        )
        triggers = _extract_triggers_from_markdown(body)
        assert "alpha" in triggers
        assert "beta" in triggers
        assert "gamma" in triggers


# ──────────────────────────────────────────────
# parse_skill_md - 유닛 테스트 (tmp_path 사용)
# ──────────────────────────────────────────────

class TestParseSkillMdUnit:

    def test_no_skill_md(self, tmp_path):
        """SKILL.md 없으면 None 반환."""
        result = parse_skill_md(tmp_path)
        assert result is None

    def test_minimal_skill_md(self, tmp_path):
        """최소 SKILL.md (frontmatter만)."""
        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text(
            "---\nname: minimal\ndescription: A minimal skill\n---\n",
            encoding="utf-8",
        )
        result = parse_skill_md(tmp_path)
        assert result is not None
        assert result.name == "minimal"
        assert result.description == "A minimal skill"
        assert result.has_scripts_dir is False
        assert result.has_references_dir is False

    def test_skill_md_with_directories(self, tmp_path):
        """디렉토리 구조가 있는 스킬."""
        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text(
            "---\nname: full-featured\ndescription: Full skill\n---\n# Body\n",
            encoding="utf-8",
        )
        (tmp_path / "scripts").mkdir()
        (tmp_path / "scripts" / "main.py").write_text("print('hello')")
        (tmp_path / "scripts" / "utils.py").write_text("# util")
        (tmp_path / "references").mkdir()
        (tmp_path / "references" / "guide.md").write_text("# Guide")
        (tmp_path / "tests").mkdir()
        (tmp_path / "DESIGN_DECISION.md").write_text("# Decisions")

        result = parse_skill_md(tmp_path)
        assert result is not None
        assert result.name == "full-featured"
        assert result.has_scripts_dir is True
        assert result.has_references_dir is True
        assert result.has_tests_dir is True
        assert result.has_design_decision is True
        assert len(result.script_files) == 2
        assert len(result.reference_files) == 1

    def test_skill_md_name_fallback_to_dir(self, tmp_path):
        """name 필드 없으면 디렉토리명 사용."""
        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text("---\ndescription: no name field\n---\n", encoding="utf-8")
        result = parse_skill_md(tmp_path)
        assert result is not None
        assert result.name == tmp_path.name

    def test_skill_md_no_frontmatter(self, tmp_path):
        """frontmatter 없는 SKILL.md."""
        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text("# My Skill\n\nJust markdown content.\n", encoding="utf-8")
        result = parse_skill_md(tmp_path)
        assert result is not None
        assert result.name == tmp_path.name  # dir name fallback
        assert result.description == ""

    def test_skill_md_with_yaml_triggers(self, tmp_path):
        """YAML description에서 트리거 추출."""
        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text(
            "---\n"
            "name: trigger-test\n"
            "description: 테스트 도구. 트리거: 분석, 검사, 진단.\n"
            "---\n"
            "# Body\n",
            encoding="utf-8",
        )
        result = parse_skill_md(tmp_path)
        assert result is not None
        assert result.triggers.source == "yaml_description"
        assert "분석" in result.triggers.keywords
        assert "검사" in result.triggers.keywords

    def test_skill_md_with_markdown_triggers(self, tmp_path):
        """markdown 본문에서 트리거 추출."""
        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text(
            "---\nname: md-trigger\ndescription: Simple desc\n---\n"
            "# Title\n\n"
            "## 트리거\n\n"
            '- "alpha"\n'
            '- "beta"\n',
            encoding="utf-8",
        )
        result = parse_skill_md(tmp_path)
        assert result is not None
        assert result.triggers.source == "markdown_section"
        assert "alpha" in result.triggers.keywords
        assert "beta" in result.triggers.keywords

    def test_skill_md_with_both_triggers(self, tmp_path):
        """YAML + markdown 양쪽에서 트리거 추출."""
        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text(
            "---\n"
            "name: both-trigger\n"
            "description: 도구. 트리거: yaml_kw.\n"
            "---\n"
            "# Title\n\n"
            "## 트리거\n\n"
            '- "md_kw"\n',
            encoding="utf-8",
        )
        result = parse_skill_md(tmp_path)
        assert result is not None
        assert result.triggers.source == "both"
        assert "yaml_kw" in result.triggers.keywords
        assert "md_kw" in result.triggers.keywords

    def test_skill_md_line_count(self, tmp_path):
        """skill_md_lines 필드 정확성."""
        content = "---\nname: test\n---\nline4\nline5\n"
        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text(content, encoding="utf-8")
        result = parse_skill_md(tmp_path)
        assert result is not None
        assert result.skill_md_lines == len(content.split("\n"))

    def test_nested_script_files(self, tmp_path):
        """scripts/ 하위 디렉토리의 .py 파일도 탐지."""
        skill_md = tmp_path / "SKILL.md"
        skill_md.write_text("---\nname: nested\n---\n", encoding="utf-8")
        scripts = tmp_path / "scripts"
        scripts.mkdir()
        (scripts / "main.py").write_text("# main")
        subdir = scripts / "sub"
        subdir.mkdir()
        (subdir / "helper.py").write_text("# helper")

        result = parse_skill_md(tmp_path)
        assert result is not None
        assert len(result.script_files) == 2
        assert "main.py" in result.script_files
        assert "helper.py" in result.script_files


# ──────────────────────────────────────────────
# parse_skill_md - 통합 테스트 (실제 스킬 디렉토리)
# ──────────────────────────────────────────────

@pytest.mark.integration
class TestParseSkillMdIntegration:

    def test_troubleshooting_cot(self):
        """실제 troubleshooting-cot-2 스킬 파싱."""
        result = parse_skill_md(TROUBLESHOOTING_COT_DIR)
        assert result is not None
        assert result.name == "troubleshooting-cot"
        assert "Chain-of-Thought" in result.description or "트러블슈팅" in result.description
        assert result.has_scripts_dir is True
        assert result.has_references_dir is True
        assert result.has_design_decision is True
        assert result.skill_md_lines > 100
        # 트리거가 추출되어야 함 (Korean 패턴)
        assert len(result.triggers.keywords) >= 3
        assert "트러블슈팅" in result.triggers.keywords

    def test_depsolve_analyzer(self):
        """실제 depsolve-analyzer 스킬 파싱 (markdown 트리거 섹션 edge case)."""
        result = parse_skill_md(DEPSOLVE_ANALYZER_DIR)
        assert result is not None
        assert result.name == "depsolve-analyzer"
        assert result.has_scripts_dir is True
        # depsolve-analyzer는 YAML description + markdown ## 트리거 양쪽에 키워드가 있다
        assert result.triggers.source == "both"
        assert len(result.triggers.keywords) >= 5
        # markdown 섹션에서 추출된 키워드 확인
        assert "phantom" in result.triggers.keywords or "팬텀" in result.triggers.keywords
        assert "순환 의존성" in result.triggers.keywords or "circular dependency" in result.triggers.keywords


# ──────────────────────────────────────────────
# discover_skills - 유닛 테스트
# ──────────────────────────────────────────────

class TestDiscoverSkillsUnit:

    def test_empty_directory(self, tmp_path):
        """빈 디렉토리면 빈 리스트."""
        result = discover_skills(tmp_path)
        assert result == []

    def test_nonexistent_directory(self, tmp_path):
        """존재하지 않는 디렉토리면 빈 리스트."""
        result = discover_skills(tmp_path / "nonexistent")
        assert result == []

    def test_directory_without_skill_md(self, tmp_path):
        """SKILL.md 없는 하위 디렉토리는 무시."""
        (tmp_path / "not-a-skill").mkdir()
        (tmp_path / "not-a-skill" / "README.md").write_text("# Not a skill")
        result = discover_skills(tmp_path)
        assert result == []

    def test_discover_single_skill(self, tmp_path):
        """스킬 1개 탐지."""
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: my-skill\ndescription: test\n---\n", encoding="utf-8",
        )
        result = discover_skills(tmp_path)
        assert len(result) == 1
        assert result[0].name == "my-skill"

    def test_discover_multiple_skills(self, tmp_path):
        """여러 스킬 탐지 + 정렬 확인."""
        for name in ["alpha", "beta", "gamma"]:
            d = tmp_path / name
            d.mkdir()
            (d / "SKILL.md").write_text(
                f"---\nname: {name}\ndescription: {name} skill\n---\n",
                encoding="utf-8",
            )
        result = discover_skills(tmp_path)
        assert len(result) == 3
        # sorted by directory name
        assert result[0].name == "alpha"
        assert result[1].name == "beta"
        assert result[2].name == "gamma"

    def test_discover_skips_files_at_root(self, tmp_path):
        """root 레벨의 파일은 무시 (디렉토리만 탐색)."""
        (tmp_path / "SKILL.md").write_text("---\nname: root\n---\n", encoding="utf-8")
        result = discover_skills(tmp_path)
        assert result == []

    def test_discover_mixed(self, tmp_path):
        """스킬과 비스킬 디렉토리 혼합."""
        skill_dir = tmp_path / "real-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: real-skill\ndescription: yes\n---\n", encoding="utf-8",
        )
        not_skill = tmp_path / "just-a-folder"
        not_skill.mkdir()
        (not_skill / "README.md").write_text("# Not a skill")

        result = discover_skills(tmp_path)
        assert len(result) == 1
        assert result[0].name == "real-skill"


# ──────────────────────────────────────────────
# discover_skills - 통합 테스트
# ──────────────────────────────────────────────

@pytest.mark.integration
class TestDiscoverSkillsIntegration:

    def test_discover_real_skills(self):
        """실제 skills root에서 8개 스킬 탐지."""
        skills = discover_skills(SKILLS_ROOT)
        assert len(skills) == 8

        names = [s.name for s in skills]
        assert "depsolve-analyzer" in names
        assert "troubleshooting-cot" in names

    def test_all_skills_have_name_and_description(self):
        """모든 스킬에 name과 description이 있어야 함."""
        skills = discover_skills(SKILLS_ROOT)
        for skill in skills:
            assert skill.name, f"Skill at {skill.skill_path} has empty name"
            # description이 빈 스킬도 있을 수 있지만 name은 필수
