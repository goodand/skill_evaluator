# Agent Skills 평가 프레임워크 개발 계획서

## Context (배경 및 목적)

### 왜 이 작업이 필요한가?

현재 `.claude/skills` 디렉토리에는 8개의 스킬이 구현되어 있으나, **통합된 품질 평가 체계가 부재**합니다:
- 각 스킬이 독립적으로 개발되어 품질 기준이 상이함
- 새로운 스킬 추가 시 품질 검증 방법이 불명확함
- 스킬 간 통합 성능(Bridge 연계) 측정 불가능
- 개선이 필요한 영역을 데이터 기반으로 판단할 수 없음

### 해결하고자 하는 문제

사용자가 제공한 Mermaid 다이어그램의 **6단계 계층 구조**를 기반으로:

```
L1: 구조적 무결성 → L2: 활성화 → L3: 검색 →
L4: 워크플로우 → L5: 실행 → L6: 검증
```

이 계층별로 스킬의 성능을 **자동으로 측정**하고, **개선 우선순위를 도출**하며, **CI/CD 자동 검증**을 가능하게 하는 범용 평가 프레임워크를 구축합니다.

### 의도된 결과

1. **벤치마킹**: 현재 8개 스킬의 6단계별 점수 측정
2. **품질 검증**: 새 스킬 개발 시 자동 평가 (SKILL.md만 있으면 OK)
3. **개선 가이드**: Layer별 약점 분석 → 우선순위 액션 자동 추천
4. **CI/CD 통합**: PR 머지 전 자동 품질 게이트 (exit code 0/1)

---

## 전체 아키텍처

### 디렉토리 구조

```
.claude/skills/skill-evaluator/          # 신규 스킬
├── SKILL.md                             # 메타데이터 (triggers 포함)
├── DESIGN_DECISION.md                   # 설계 근거
├── README.md                            # 빠른 시작 가이드
│
├── scripts/                             # 핵심 엔진
│   ├── evaluator.py                     # 메인 오케스트레이터
│   ├── skill_discovery.py               # YAML 파싱 (자동 탐지)
│   ├── metrics_collector.py             # 메트릭 계산 엔진
│   ├── report_generator.py              # Markdown/JSON 출력
│   └── ci_validator.py                  # CI/CD 통합
│
├── evaluators/                          # 6개 Layer 평가기
│   ├── layer1_structural.py             # L1: YAML, 디렉토리, 독립성
│   ├── layer2_activation.py             # L2: Trigger, Intent 인식
│   ├── layer3_retrieval.py              # L3: Hit@k, Context Precision
│   ├── layer4_workflow.py               # L4: Plan Adherence, 다단계
│   ├── layer5_execution.py              # L5: TSR, ECR, Pass@k
│   └── layer6_validation.py             # L6: Faithfulness, 실패 분석
│
├── benchmarks/                          # 테스트 데이터셋
│   ├── L2_activation/
│   │   └── trigger_queries.json         # "디버깅 도와줘" → troubleshooting-cot
│   ├── L3_retrieval/
│   │   └── context_precision_tests.json # 쿼리 → 기대 참고 문서
│   └── L5_execution/
│       └── tool_call_tests.json         # 스크립트 실행 + 기대 결과
│
├── metrics/                             # 메트릭 정의 (모듈화)
│   ├── structural_metrics.py
│   ├── activation_metrics.py
│   ├── retrieval_metrics.py             # Hit@k, MRR, Precision/Recall
│   ├── workflow_metrics.py              # Plan Adherence
│   ├── execution_metrics.py             # TSR, ECR, Pass@k
│   └── validation_metrics.py            # Faithfulness
│
├── plugins/                             # 확장 시스템
│   ├── plugin_registry.py               # 동적 메트릭 로딩
│   └── custom_metrics/                  # 사용자 정의 메트릭
│       └── README.md
│
├── bridges/                             # 기존 스킬 통합
│   ├── skill_bridge.py                  # RunResult 표준 인터페이스
│   └── orchestrator_bridge.py           # troubleshooting-cot bridge 연동
│
└── references/
    ├── METRICS_GLOSSARY.md              # 전체 메트릭 정의서
    ├── BENCHMARK_GUIDE.md               # 벤치마크 추가 방법
    ├── PLUGIN_API.md                    # 커스텀 메트릭 API
    └── EVALUATION_REPORT_SCHEMA.json    # JSON 출력 스키마
```

---

## 핵심 컴포넌트 설계

### 1. 메인 오케스트레이터 (`evaluator.py`)

**역할**: 스킬 발견 → Layer 평가 → 리포트 생성 → CI 판정

**주요 클래스**:

```python
@dataclass
class SkillMetadata:
    """SKILL.md YAML 프론트매터 파싱"""
    name: str
    description: str
    triggers: List[str]
    skill_path: Path

    @classmethod
    def from_skill_md(cls, skill_path: Path) -> 'SkillMetadata':
        # YAML 파싱 + Trigger 키워드 추출

@dataclass
class EvaluationResult:
    """단일 Layer 평가 결과"""
    layer: str                    # L1-L6
    skill_name: str
    metrics: Dict[str, float]     # 메트릭명 → 점수 (0-100)
    details: Dict[str, Any]       # 추가 컨텍스트
    passed: bool                  # 통과/실패

@dataclass
class SkillEvaluationReport:
    """전체 평가 리포트"""
    skill_name: str
    overall_score: float                    # 가중 평균
    layer_results: List[EvaluationResult]
    priority_actions: List[str]             # 개선 우선순위
    pass_fail: bool                         # CI/CD 게이트

class SkillEvaluator:
    """메인 오케스트레이터"""

    LAYER_WEIGHTS = {
        'L1': 0.20,  # 구조적 무결성 (기초)
        'L2': 0.15,  # 활성화 (트리거)
        'L3': 0.15,  # 검색 (컨텍스트)
        'L4': 0.15,  # 워크플로우
        'L5': 0.25,  # 실행 (가장 관찰 가능)
        'L6': 0.10,  # 검증 (보너스)
    }

    def discover_skills(self) -> List[SkillMetadata]:
        """SKILL.md가 있는 모든 스킬 자동 탐지"""

    def evaluate_skill(self, skill: SkillMetadata,
                      layers: List[str] = None) -> SkillEvaluationReport:
        """단일 스킬 평가 (지정 Layer만 또는 전체)"""

    def _generate_priorities(self, results: List[EvaluationResult]) -> List[str]:
        """가중치 기반 개선 우선순위 자동 도출"""
```

**CLI 인터페이스**:

```bash
# 전체 스킬 평가
python evaluator.py --all

# 특정 스킬만
python evaluator.py --skill troubleshooting-cot-2

# 특정 Layer만
python evaluator.py --layer L2,L5 --skill depsolve-analyzer

# CI/CD 모드 (threshold 70점, 실패 시 exit 1)
python evaluator.py --all --ci-mode --threshold 70

# JSON 출력
python evaluator.py --all --format json -o report.json
```

---

### 2. Layer별 평가 알고리즘

#### L1: 구조적 무결성 (`layer1_structural.py`)

**측정 항목**:

1. **YAML 프론트매터 유효성** (30점)
   - 필수 필드: `name`, `description`
   - Trigger 키워드 추출 가능 여부
   - YAML 문법 오류 감지

2. **디렉토리 구조** (40점)
   - `SKILL.md` 존재 (필수)
   - `scripts/` 디렉토리 (실행 스킬은 필수)
   - `references/` 디렉토리 (권장)
   - `tests/` 또는 `benchmarks/` (선택)

3. **리소스 독립성** (30점)
   - 하드코딩된 절대 경로 검색 (`grep -r /Users/`)
   - `skill-path-resolver` 사용 확인 (크로스 스킬 import 시)
   - 상대 경로 사용 권장

**자동 측정**: ✅ 100% 자동 (정적 분석)

---

#### L2: 활성화 (`layer2_activation.py`)

**측정 항목**:

1. **Trigger 품질** (40점)
   - Trigger 개수 (5-15개가 최적)
   - Generic trigger 비율 (50% 이하 권장)
   - 다른 스킬과 중복도

2. **Intent Recognition** (40점)
   - 벤치마크: `benchmarks/L2_activation/trigger_queries.json`
   - 형식:
     ```json
     {
       "troubleshooting-cot-2": [
         {"query": "왜 안 되지?", "should_activate": true},
         {"query": "파일 읽어줘", "should_activate": false}
       ]
     }
     ```
   - 정확도 = (올바른 판정 / 전체 테스트) × 100

3. **False Positive 제어** (20점)
   - 활성화되면 안 되는 쿼리 테스트
   - FP Rate = (잘못 활성화 / 음성 테스트) × 100

**자동 측정**: ⚠️ 벤치마크 필요 (수동 작성 후 자동)

---

#### L3: 검색 및 리소스 (`layer3_retrieval.py`)

**측정 항목**:

1. **참고 문서 품질** (50점)
   - `references/` 디렉토리 존재
   - 참고 문서 개수
   - 표준 참고 타입 커버리지 (API_REFERENCE, EXAMPLES, PATTERN_LIBRARY 등)

2. **Context Precision** (30점)
   - 벤치마크: `benchmarks/L3_retrieval/context_precision_tests.json`
   - Hit@k 메트릭: 쿼리 → 올바른 참고 문서 찾기
   - MRR (Mean Reciprocal Rank)

3. **Progressive Disclosure** (20점)
   - SKILL.md < 5000 단어 (간결성)
   - 상세 내용은 references/로 분리

**자동 측정**: ⚠️ 벤치마크 필요

---

#### L4: 워크플로우 (`layer4_workflow.py`)

**측정 항목**:

1. **워크플로우 구조 감지** (60점)
   - Phase 구조 존재 (`Phase \d` 패턴)
   - Step 구조 존재 (`Step \d` 패턴)
   - Pipeline 아키텍처 언급
   - Phase별 개수 추출

2. **Plan Adherence** (40점)
   - Phase 건너뛰기 허용 여부 명시
   - 워크플로우 유연성 (조건부 실행)

**자동 측정**: ✅ 정적 분석 가능

---

#### L5: 실행 및 액션 (`layer5_execution.py`)

**측정 항목**:

1. **스크립트 품질** (30점)
   - `scripts/` 디렉토리 존재
   - Shebang (`#!/usr/bin/env python3`)
   - `--help` 또는 `argparse` 사용
   - Zero dependencies (표준 라이브러리만)

2. **Tool Success Rate (TSR)** (50점)
   - 벤치마크: `benchmarks/L5_execution/tool_call_tests.json`
   - 형식:
     ```json
     {
       "troubleshooting-cot-2": [
         {
           "script": "semantic_diff.py",
           "args": ["--good", "abc", "--bad", "def"],
           "expected_exit_code": 0,
           "expected_output_contains": "MODIFIED"
         }
       ]
     }
     ```
   - TSR = (성공 실행 / 전체 테스트) × 100

3. **Execution Correctness (ECR)** (20점)
   - 출력이 스펙과 일치하는가
   - JSON 출력 시 스키마 준수

**자동 측정**: ⚠️ 벤치마크 필요 (스크립트 실제 실행)

---

#### L6: 검증 (`layer6_validation.py`)

**측정 항목**:

1. **자가 검증 인프라** (50점)
   - `tests/` 디렉토리 존재
   - `--verify` 플래그 스크립트
   - Validation 패턴 (bisect, syntax_checker 등)

2. **Faithfulness** (30점)
   - 출력이 스펙을 준수하는가
   - 검증 스크립트가 실제 작동하는가

3. **Failure Handling** (20점)
   - 에러 처리 로직 존재
   - 실패 시 명확한 에러 메시지

**자동 측정**: ✅ 정적 분석 + 일부 실행

---

### 3. 확장성 시스템 (Plugin)

**목적**: 새로운 메트릭을 코어 코드 수정 없이 추가

**구조**:

```python
# plugins/plugin_registry.py

class MetricPlugin(ABC):
    @abstractmethod
    def name(self) -> str:
        """메트릭 이름"""

    @abstractmethod
    def layer(self) -> str:
        """대상 Layer: L1-L6"""

    @abstractmethod
    def compute(self, skill: SkillMetadata) -> float:
        """점수 계산 (0-100)"""

# 사용 예시: plugins/custom_metrics/my_metric.py
class ComplexityMetric(MetricPlugin):
    def name(self) -> str:
        return "cyclomatic_complexity"

    def layer(self) -> str:
        return "L5"

    def compute(self, skill: SkillMetadata) -> float:
        # 복잡도 계산 로직
        return 75.0
```

**자동 로딩**: `PluginRegistry`가 `custom_metrics/` 스캔 → 동적 import

---

### 4. 출력 형식

#### JSON 스키마

```json
{
  "metadata": {
    "framework_version": "1.0.0",
    "timestamp": "2025-02-10T15:30:00",
    "evaluated_skills": 8
  },
  "skills": [
    {
      "skill_name": "troubleshooting-cot-2",
      "overall_score": 87.3,
      "pass_fail": true,
      "layer_results": [
        {
          "layer": "L1",
          "metrics": {
            "yaml_compliance": 100,
            "directory_structure": 100,
            "resource_independence": 100,
            "overall": 100
          },
          "details": {...},
          "passed": true
        }
      ],
      "priority_actions": [
        "⚠️ L5 score: 75.0 (improve for +3.1 overall)"
      ]
    }
  ],
  "summary": {
    "total_skills": 8,
    "passed_skills": 7,
    "failed_skills": 1,
    "average_score": 78.5,
    "layer_averages": {
      "L1": 95.2,
      "L2": 72.3,
      "L3": 68.1,
      "L4": 85.4,
      "L5": 81.7,
      "L6": 62.9
    }
  }
}
```

#### Markdown 리포트

```markdown
# Agent Skills Evaluation Report

## Executive Summary

| Metric | Value |
|--------|-------|
| Total Skills | 8 |
| Passed Skills | 7 (87.5%) |
| Average Score | 78.5 |

## Layer Performance

| Layer | Avg | Status |
|-------|-----|--------|
| L1: Structural | 95.2 | ✅ Excellent |
| L2: Activation | 72.3 | ⚠️ Needs Work |
| L5: Execution | 81.7 | ✅ Good |

## Improvement Roadmap

### Critical
1. **depsolve-analyzer** - L2 실패
   - Issue: Trigger 키워드 너무 generic
   - Fix: 도메인 특화 키워드 5-10개 추가

### High Priority
2. **troubleshooting-cot-2** - L5 TSR 60%
   - Fix: semantic_diff.py 엣지 케이스 처리
```

#### CI/CD 통합

```bash
# 종료 코드
0: 모든 스킬 통과 (threshold 이상)
1: 1개 이상 스킬 실패

# CI 요약 출력
✅ 7/8 skills passed (87.5%)
❌ FAILED: depsolve-analyzer (score: 65.2)

Exit code: 1
```

---

## 우선순위 및 의존성

### 구현 단계 (6주 계획)

#### Phase 1: 기초 인프라 (Week 1) — CRITICAL PATH

**목표**: 최소 기능 프로토타입 (CI/CD 가능)

1. **디렉토리 구조 생성**
   - `skill-evaluator/` 폴더 생성
   - SKILL.md, README.md 작성

2. **SkillMetadata 파서** ✅ 의존성 없음
   - `skill_discovery.py` 구현
   - YAML 프론트매터 파싱
   - Trigger 키워드 추출

3. **SkillEvaluator 오케스트레이터** (의존: SkillMetadata)
   - `evaluator.py` 메인 클래스
   - `discover_skills()` 메서드
   - CLI 인터페이스 (argparse)

4. **L1 Structural 평가기** (의존: SkillMetadata)
   - `layer1_structural.py` 구현
   - YAML, 디렉토리, 독립성 체크
   - **가장 기초적이고 의존성 없음**

5. **Report Generator** (의존: EvaluationResult)
   - `report_generator.py` 구현
   - JSON 출력 (기본)
   - Markdown 출력 (선택)

**산출물**: `python evaluator.py --skill troubleshooting-cot-2 --layer L1` 실행 가능

---

#### Phase 2: 핵심 Layer 구현 (Week 2-3)

**목표**: 가장 영향력 큰 Layer 추가 (L2, L5)

1. **L5 Execution 평가기** (가중치 25%, 최우선)
   - `layer5_execution.py` 구현
   - 스크립트 품질 체크
   - TSR 벤치마크 실행 로직

2. **L5 벤치마크 작성** (수동 작업)
   - `benchmarks/L5_execution/tool_call_tests.json`
   - 각 스킬별 2-5개 테스트 케이스
   - 우선: troubleshooting-cot-2, depsolve-analyzer

3. **L2 Activation 평가기**
   - `layer2_activation.py` 구현
   - Trigger 품질 분석
   - Intent Recognition 로직

4. **L2 벤치마크 작성**
   - `benchmarks/L2_activation/trigger_queries.json`
   - 각 스킬별 10-20개 쿼리

5. **CI Validator** (의존: 전체 리포트)
   - `ci_validator.py` 구현
   - Pass/Fail 로직 (threshold, critical layer)
   - 종료 코드 처리

**산출물**: CI/CD에서 사용 가능한 품질 게이트

---

#### Phase 3: 고급 Layer 구현 (Week 4)

1. **L3 Retrieval 평가기**
   - `layer3_retrieval.py` 구현
   - 참고 문서 품질 체크
   - Context Precision (벤치마크 필요)

2. **L4 Workflow 평가기**
   - `layer4_workflow.py` 구현
   - Phase/Step 구조 감지
   - Plan Adherence 분석

3. **L6 Validation 평가기**
   - `layer6_validation.py` 구현
   - 자가 검증 인프라 체크
   - Faithfulness 측정

4. **Plugin System**
   - `plugin_registry.py` 구현
   - `MetricPlugin` 추상 클래스
   - 동적 로딩 메커니즘

**산출물**: 6개 Layer 전체 평가 가능

---

#### Phase 4: 벤치마크 & 검증 (Week 5)

1. **전체 스킬 벤치마크 작성**
   - L2: 8개 스킬 × 15개 쿼리
   - L3: 주요 5개 스킬 × 10개 컨텍스트 테스트
   - L5: 8개 스킬 × 3-5개 스크립트 테스트

2. **문서화**
   - `METRICS_GLOSSARY.md`: 전체 메트릭 정의
   - `BENCHMARK_GUIDE.md`: 벤치마크 추가 방법
   - `PLUGIN_API.md`: 커스텀 메트릭 작성법

3. **통합 테스트**
   - `python evaluator.py --all` 실행
   - 8개 스킬 전체 평가
   - JSON/Markdown 출력 검증

**산출물**: 프로덕션 레디 평가 프레임워크

---

#### Phase 5: 통합 & 최적화 (Week 6)

1. **Bridge 통합**
   - `bridges/skill_bridge.py` 구현
   - troubleshooting-cot `bridge.py`와 연동
   - RunResult 표준 인터페이스

2. **성능 최적화**
   - 벤치마크 실행 병렬화
   - 캐싱 (동일 스킬 재평가 시)

3. **CI/CD 예시**
   - `.github/workflows/skill-evaluation.yml` 작성
   - PR 검증 자동화

4. **사용자 문서**
   - README.md 업데이트
   - Quick Start 가이드

**산출물**: 완전 자동화된 평가 시스템

---

### 의존성 그래프

```
SkillMetadata Parser (Week 1)
    ↓
SkillEvaluator 오케스트레이터 (Week 1)
    ↓
    ├─→ L1 Structural (Week 1) → Report Generator (Week 1)
    ├─→ L5 Execution (Week 2) ──→ CI Validator (Week 3)
    ├─→ L2 Activation (Week 2)
    ├─→ L3 Retrieval (Week 4)
    ├─→ L4 Workflow (Week 4)
    └─→ L6 Validation (Week 4)

Plugin Registry (Week 4) → SkillEvaluator
Benchmarks (Week 2-5) → L2, L3, L5
Bridge Integration (Week 6) → SkillEvaluator
```

---

### Critical Path (MVP for CI/CD)

**최소 5개 컴포넌트**로 CI/CD 통합 가능:

1. SkillMetadata Parser
2. SkillEvaluator 오케스트레이터
3. L1 Structural 평가기
4. L5 Execution 평가기 + 벤치마크
5. CI Validator

→ **Week 1-3 완료 시 CI/CD 배포 가능**

나머지 Layer는 **점진적 추가** (기존 기능 영향 없음)

---

## 주요 파일 경로

### 핵심 구현 파일

1. **/Users/jaehyuntak/Desktop/Project_____현재 진행중인/narrative-ai/.claude/skills/skill-evaluator/scripts/evaluator.py**
   - 메인 오케스트레이터, CLI 엔트리포인트
   - 가장 먼저 구현 (Week 1)

2. **/Users/jaehyuntak/Desktop/Project_____현재 진행중인/narrative-ai/.claude/skills/skill-evaluator/scripts/skill_discovery.py**
   - YAML 파싱, 스킬 자동 탐지
   - 의존성 없음 (Week 1)

3. **/Users/jaehyuntak/Desktop/Project_____현재 진행중인/narrative-ai/.claude/skills/skill-evaluator/evaluators/layer1_structural.py**
   - L1 평가기 (Critical Path)
   - Week 1 완료 목표

4. **/Users/jaehyuntak/Desktop/Project_____현재 진행중인/narrative-ai/.claude/skills/skill-evaluator/evaluators/layer5_execution.py**
   - L5 평가기 (가중치 25%, 최우선)
   - Week 2 완료 목표

5. **/Users/jaehyuntak/Desktop/Project_____현재 진행중인/narrative-ai/.claude/skills/skill-evaluator/scripts/ci_validator.py**
   - CI/CD 통합 로직
   - Week 3 완료 목표

### 벤치마크 파일

6. **/Users/jaehyuntak/Desktop/Project_____현재 진행중인/narrative-ai/.claude/skills/skill-evaluator/benchmarks/L2_activation/trigger_queries.json**
   - L2 Intent Recognition 테스트

7. **/Users/jaehyuntak/Desktop/Project_____현재 진행중인/narrative-ai/.claude/skills/skill-evaluator/benchmarks/L5_execution/tool_call_tests.json**
   - L5 TSR 테스트

### 참고할 기존 파일

8. **/Users/jaehyuntak/Desktop/Project_____현재 진행중인/narrative-ai/.claude/skills/troubleshooting-cot-2/DESIGN_DECISION.md**
   - KPI 정의 패턴 참고

9. **/Users/jaehyuntak/Desktop/Project_____현재 진행중인/narrative-ai/.claude/skills/troubleshooting-cot-2/scripts/bridge.py**
   - Bridge 통합 패턴 참고

10. **/Users/jaehyuntak/Desktop/Project_____현재 진행중인/narrative-ai/.claude/skills/depsolve-analyzer/bridges/codebase_orchestrator.py**
    - 4단계 파이프라인 참고

---

## 검증 방법 (End-to-End)

### 개발 중 검증

```bash
# Week 1 검증
python evaluator.py --skill troubleshooting-cot-2 --layer L1
# 기대: L1 점수 출력, JSON 리포트 생성

# Week 2 검증
python evaluator.py --skill troubleshooting-cot-2 --layer L1,L5
# 기대: L1 + L5 점수, TSR 벤치마크 실행

# Week 3 검증 (CI 통합)
python evaluator.py --all --ci-mode --threshold 70
# 기대: Exit code 0 (전체 통과) 또는 1 (실패)
```

### 최종 검증

```bash
# 전체 스킬 평가 + JSON 출력
python evaluator.py --all --format json -o evaluation_report.json

# Markdown 리포트 생성
python evaluator.py --all --format markdown -o EVALUATION_REPORT.md

# CI/CD 시뮬레이션
python evaluator.py --all --ci-mode --threshold 70
echo $?  # 0이면 성공, 1이면 실패
```

### 성공 기준

1. **자동 발견**: 8개 스킬 모두 자동 탐지
2. **6단계 평가**: 모든 Layer 점수 산출 (벤치마크 없어도 기본 점수)
3. **우선순위 도출**: 개선 액션 3개 이상 추천
4. **CI 통합**: Exit code로 pass/fail 판정
5. **확장성**: 새 스킬 추가 시 코드 수정 없이 평가 가능

---

## 핵심 설계 결정

### 1. 왜 6단계인가?

에이전트 라이프사이클을 반영:
- L1: 로드 가능한가?
- L2: 트리거 가능한가?
- L3: 컨텍스트 찾기 가능한가?
- L4: 다단계 계획 가능한가?
- L5: 도구 실행 가능한가?
- L6: 결과 검증 가능한가?

### 2. 왜 Plugin 시스템인가?

- **확장성**: 코어 코드 수정 없이 새 메트릭 추가
- **도메인 특화**: depsolve만의 "패키지 신선도" 같은 메트릭 가능
- **실험**: 새 평가 방법 테스트 안전

### 3. 왜 벤치마크 기반인가?

**정적 분석**(L1, L4, L6)은 자동 가능하지만,
**행동 메트릭**(L2, L3, L5)은 **테스트 케이스** 필요:
- L2: Intent 인식 = 쿼리 예시 필요
- L3: Context Precision = 기대 참고 문서 필요
- L5: TSR = 기대 출력 필요

→ 재현 가능하고 정량적인 평가

### 4. 왜 가중치 점수인가?

모든 Layer가 동등하지 않음:
- L5 Execution (25%): 가장 관찰 가능한 실패
- L1 Structural (20%): 모든 것의 기초
- L2/L3/L4 (15%): 중요하지만 덜 치명적
- L6 Validation (10%): 보너스 기능

→ 실제 스킬 실패 영향도 반영

### 5. 왜 범용적인가?

**SKILL.md 표준만 준수**하면:
1. `SkillMetadata.from_skill_md()`로 자동 파싱
2. 6개 Layer 평가기가 자동 실행
3. 벤치마크 없어도 기본 점수 산출

→ 새 스킬 추가 시 코드 수정 불필요

---

## 위험 및 대응

### 위험 1: 벤치마크 작성 비용

**위험**: L2, L3, L5 벤치마크를 8개 스킬 × 10-20개씩 작성하는 시간

**대응**:
- Phase 1-2에서는 2개 스킬만 (troubleshooting-cot-2, depsolve-analyzer)
- 나머지는 Phase 4에서 점진적 추가
- 벤치마크 없어도 기본 점수(50점) 반환 → 점진적 개선

### 위험 2: Plugin 복잡도

**위험**: Plugin 시스템이 과도하게 복잡해질 수 있음

**대응**:
- Phase 3까지는 Plugin 없이 진행
- Week 4에 추가 (선택 사항)
- 사용하지 않아도 핵심 기능 동작

### 위험 3: 스킬마다 평가 기준이 다름

**위험**: troubleshooting-cot-2는 Phase 구조, mapper는 파이프라인

**대응**:
- L4에서 **다양한 워크플로우 패턴** 모두 인식
- Phase, Step, Pipeline 모두 점수 부여
- 단일 실행 스킬도 50점 기본 점수

---

## 다음 단계

1. **Plan 승인 대기**
2. **Week 1 시작**: `evaluator.py` + `layer1_structural.py` 구현
3. **첫 평가 실행**: `python evaluator.py --skill troubleshooting-cot-2 --layer L1`
4. **결과 검증**: JSON 출력 확인, 점수 타당성 검토
5. **Week 2-3**: L5 + L2 + CI Validator → CI/CD 배포
6. **점진적 확장**: L3, L4, L6 추가

---

**END OF PLAN**
