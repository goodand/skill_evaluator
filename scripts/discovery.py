"""SKILL.md 파서 + 스킬 자동 탐지."""

import re
from pathlib import Path
from typing import List, Optional

from models import SkillMetadata, TriggerInfo


def _parse_yaml_frontmatter(text: str) -> dict:
    """--- 구분자로 감싼 YAML frontmatter를 간단히 파싱 (stdlib only)."""
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return {}

    yaml_lines = []
    for line in lines[1:]:
        if line.strip() == "---":
            break
        yaml_lines.append(line)

    result = {}
    current_key = None
    for line in yaml_lines:
        # key: value 패턴
        match = re.match(r'^(\w[\w\s]*?):\s*(.+)$', line)
        if match:
            key = match.group(1).strip()
            value = match.group(2).strip().strip('"').strip("'")
            result[key] = value
            current_key = key
        # 들여쓰기된 continuation (description이 길 때)
        elif current_key and line.startswith("  "):
            result[current_key] += " " + line.strip()

    return result


def _extract_triggers_from_description(description: str) -> List[str]:
    """YAML description 필드에서 트리거 키워드 추출.

    패턴:
    - Korean: '트리거: kw1, kw2, ...' 또는 '트리거 키워드: ...'
    - English: 'Triggers on "kw1", "kw2", ...'
    - Quoted: "keyword1", "keyword2"
    """
    triggers = []

    # 패턴 1: Korean 트리거
    ko_match = re.search(r'트리거[:\s]+(.+?)(?:\.|$)', description)
    if ko_match:
        raw = ko_match.group(1)
        triggers.extend([t.strip().strip('"').strip("'") for t in raw.split(",") if t.strip()])

    # 패턴 2: English Triggers on
    en_match = re.search(r'[Tt]riggers?\s+on\s+(.+?)(?:\.|$)', description)
    if en_match:
        raw = en_match.group(1)
        quoted = re.findall(r'"([^"]+)"', raw)
        if quoted:
            triggers.extend(quoted)
        else:
            triggers.extend([t.strip() for t in raw.split(",") if t.strip()])

    # 패턴 3: 명시적 키워드 나열 ("kw1", "kw2" 패턴)
    if not triggers:
        quoted = re.findall(r'"([^"]+)"', description)
        if quoted:
            triggers.extend(quoted)

    return list(dict.fromkeys(triggers))  # 순서 유지 dedupe


def _extract_triggers_from_markdown(body: str) -> List[str]:
    """markdown 본문에서 ## 트리거 섹션의 키워드 추출 (depsolve-analyzer 대응)."""
    triggers = []

    match = re.search(
        r'##\s*트리거\s*\n((?:[-*]\s*.+\n?)+)',
        body,
        re.MULTILINE
    )
    if match:
        section = match.group(1)
        for line in section.split("\n"):
            line = line.strip()
            if line.startswith(("-", "*")):
                # "phantom", "팬텀", "유령 의존성" 같은 패턴
                items = re.findall(r'"([^"]+)"', line)
                if items:
                    triggers.extend(items)
                else:
                    # 따옴표 없는 경우: - keyword
                    kw = line.lstrip("-*").strip()
                    if kw:
                        triggers.extend([k.strip() for k in kw.split(",") if k.strip()])

    return list(dict.fromkeys(triggers))


def parse_skill_md(skill_dir: Path) -> Optional[SkillMetadata]:
    """SKILL.md를 파싱하여 SkillMetadata 생성."""
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        return None

    text = skill_md.read_text(encoding="utf-8")
    lines = text.split("\n")

    # YAML frontmatter 파싱
    yaml_data = _parse_yaml_frontmatter(text)
    name = yaml_data.get("name", skill_dir.name)
    description = yaml_data.get("description", "")

    # body (frontmatter 이후)
    body_start = 0
    if lines and lines[0].strip() == "---":
        for i, line in enumerate(lines[1:], 1):
            if line.strip() == "---":
                body_start = i + 1
                break
    body = "\n".join(lines[body_start:])

    # 트리거 추출 (이중 파싱)
    yaml_triggers = _extract_triggers_from_description(description)
    md_triggers = _extract_triggers_from_markdown(body)

    if yaml_triggers and md_triggers:
        all_triggers = list(dict.fromkeys(yaml_triggers + md_triggers))
        source = "both"
    elif yaml_triggers:
        all_triggers = yaml_triggers
        source = "yaml_description"
    elif md_triggers:
        all_triggers = md_triggers
        source = "markdown_section"
    else:
        all_triggers = []
        source = "yaml_description"

    # 파일시스템 스캔
    scripts_dir = skill_dir / "scripts"
    refs_dir = skill_dir / "references"
    bridges_dir = skill_dir / "bridges"
    tests_dir = skill_dir / "tests"

    script_files = []
    if scripts_dir.is_dir():
        script_files = [f.name for f in scripts_dir.rglob("*.py")]

    ref_files = []
    if refs_dir.is_dir():
        ref_files = [f.name for f in refs_dir.iterdir() if f.is_file()]

    return SkillMetadata(
        name=name,
        description=description,
        skill_path=skill_dir,
        triggers=TriggerInfo(keywords=all_triggers, source=source),
        has_scripts_dir=scripts_dir.is_dir(),
        has_references_dir=refs_dir.is_dir(),
        has_bridges_dir=bridges_dir.is_dir(),
        has_tests_dir=tests_dir.is_dir(),
        has_design_decision=(skill_dir / "DESIGN_DECISION.md").exists(),
        script_files=script_files,
        reference_files=ref_files,
        skill_md_lines=len(lines),
    )


def discover_skills(skills_root: Path) -> List[SkillMetadata]:
    """skills_root 아래에서 SKILL.md가 있는 모든 스킬을 탐지."""
    skills = []
    if not skills_root.is_dir():
        return skills

    for child in sorted(skills_root.iterdir()):
        if child.is_dir() and (child / "SKILL.md").exists():
            meta = parse_skill_md(child)
            if meta:
                skills.append(meta)

    return skills
