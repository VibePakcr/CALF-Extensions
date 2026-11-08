# 로컬 기록 조회

[English](REPOSITORY_HISTORY.md) · [Repository 팩](REPOSITORY_PACK_KR.md)

선택한 CALF `history.html`에 경량 인덱스와 모듈별 문서를 만드는 소스 프리뷰입니다. 원본 기록·해시 체인·계약·완료 판정은 바꾸지 않습니다. 파생 문서는 다시 만들 수 있는 조회 자료이며 CALF의 검증 근거로 역수입하지 않습니다.

생성·조회에는 Python 3.10 이상과 표준 라이브러리만 필요합니다. Git·SDK·모델·네트워크·상주 서비스는 사용하지 않습니다. 네이티브 기록 확인과 현재 판정 조회에만 사용자가 선택한 CALF 실행 파일이 필요합니다. 실제 코어 연동은 Harness 1.8.8로 확인했으며 다른 버전과 운영체제는 별도 검증이 필요합니다.

## 모듈 정의

별도의 UTF-8 JSON 파일에 작성합니다.

```json
{
  "schema": "calf.repository.history-modules.v1",
  "modules": [
    {"id": "map", "label": "지도", "paths": ["src/map"], "dependsOn": ["api"]},
    {"id": "api", "label": "API", "paths": ["src/api"]},
    {"id": "auth", "label": "인증", "paths": ["src/auth"]}
  ]
}
```

ID에는 영문 소문자·숫자·밑줄·하이픈을 쓰고, 표시 이름은 다국어를 지원합니다. 경로는 안전한 프로젝트 상대 경로 접두어입니다. 작업 범위와 겹치는 모듈에 기록을 연결합니다. 겹침은 양방향으로 확인하므로 `src` 범위의 작업은 `src/map`과 `src/api` 모두에 영향을 줄 수 있습니다. 공유 작업은 각 모듈에 표시합니다. 선언된 범위가 실제 변경 파일의 증명은 아닙니다.

파일 범위가 없는 관측용 작업에는 `"tasks": ["정확한-task-id"]`를 사용합니다. 경로와 작업 ID를 함께 지정해도 됩니다. 매핑되지 않았거나 아직 확인되지 않은 참조는 `unassigned`에 남깁니다. 문장만 보고 기능 의미를 만들지 않으며 의존관계도 명시적으로 지정합니다. `--related`는 직접 연결된 모듈을 최대 4개 추가하고 생략 수를 표시합니다.

## 생성과 조회

압축을 푼 Repository 팩 또는 CALF Extensions 소스 루트에서 실행합니다. 물리 절대 경로를 사용하고 출력의 부모 폴더는 미리 준비합니다. 출력은 **원본 기록의 작업 폴더 밖에 있는 새 폴더**여야 합니다.

```text
python -B -m calf_extensions.repository.cli history build --history /work/project/history.html --modules /work/config/modules.json --output /work/data/history-view-001
python -B -m calf_extensions.repository.cli history modules --index /work/data/history-view-001
python -B -m calf_extensions.repository.cli history module --index /work/data/history-view-001 --module map
python -B -m calf_extensions.repository.cli history module --index /work/data/history-view-001 --module map --related --json
python -B -m calf_extensions.repository.cli history search --index /work/data/history-view-001 --module map --kind DECISION
python -B -m calf_extensions.repository.cli history search --index /work/data/history-view-001 --module map --query architecture --before 120 --limit 10
python -B -m calf_extensions.repository.cli history record --index /work/data/history-view-001 --seq 42
```

출력에는 `INDEX.json`, `pages/` 아래 메타데이터 페이지와 `sub_map.md`·`sub_api.md`·`sub_auth.md`·`sub_unassigned.md`가 생깁니다. 문서마다 최근 기록을 최대 20개까지 보여주고 원래 순번·ID·해시, 과거 판정과 생략 수를 표시합니다. 오래된 기록은 순번으로 조회합니다. 기록 본문은 인용 자료이며 조회기가 내리는 지시가 아닙니다.

모듈 조회는 인덱스와 선택한 Markdown만 읽고 다른 모듈 문서나 원본 기록 본문은 불러오지 않습니다. 개별 기록 조회는 메타데이터 한 페이지와 원본의 해당 바이트 구간만 읽어 보관한 원문 해시·ID와 대조합니다. 문서나 메타데이터 페이지가 바뀌면 거절합니다.

`search`는 최근 문서에 나오지 않는 오래된 모듈 기록도 작은 메타데이터 페이지에서 찾습니다. 검색 범위는 ID·종류·본문 첫 160자이며 전체 데이터 검색은 아닙니다. 최신 순으로 참조를 최대 20개 반환합니다. `nextBefore`가 있으면 이어서 조회하며 `PARTIAL`을 전체 이력 조회 완료로 해석하면 안 됩니다. 한 번에 메타데이터 8MiB와 제한된 페이지 하나까지 읽고 원본 본문은 읽지 않습니다. 결과의 `seq`로 정확한 전체 기록을 선택합니다.

기본 최신성 검사는 원본의 파일 식별자·크기·수정 시각·변경 시각을 비교합니다(`STAT_MATCH`). 조회 명령에 `--verify-source`를 추가하면 원본 전체 SHA-256도 대조합니다(`SHA256_MATCH`). 이때는 원본을 모두 읽으므로 I/O가 늘어납니다. 기록이 추가되면 기존 인덱스를 오래된 상태로 거절하며 다른 새 폴더에 다시 만듭니다. 자동 감시·갱신·캐시 삭제는 설치하지 않습니다.

## 무결성과 현재 판정

기본 생성은 기록 연결 순서만 확인하며 CALF 고유의 스키마·해시 알고리즘을 재구현하지 않습니다. 코어가 확인한 마지막 해시와의 일치를 요구하려면 검토한 실행 파일을 지정합니다.

```text
python -B -m calf_extensions.repository.cli history build --history /work/project/history.html --modules /work/config/modules.json --output /work/data/history-view-002 --calf /work/tools/calf
python -B -m calf_extensions.repository.cli history status --index /work/data/history-view-002 --task exact-task-id --calf /work/tools/calf --verify-source
```

기존의 읽기 전용 `calf status WORKSPACE TASK`를 사용합니다. 해당 작업의 구조화된 응답을 받고 호출 전후 원본 SHA-256이 같으며, 네이티브 `head`도 이 전체 파일 해시와 일치해야 확인으로 인정합니다. 검증한 코어에서 이 값은 마지막 레코드 해시와 다르므로 두 식별자를 각각 보관합니다. 작업은 여전히 `UNKNOWN` 또는 `VIOLATED`일 수 있습니다. 명시적인 현재 판정 조회는 응답을 반환하기 전에 원본 해시도 다시 확인합니다. 문서의 현재 완료 표시는 항상 `NOT EVALUATED`이며 저장된 `SATISFIED`는 과거 사실로 남깁니다. 현재 파일 버전·실행 환경·증거 규칙을 그대로 적용하므로 이전 호스트에서 통과했어도 다른 환경에서는 `UNKNOWN`일 수 있습니다. 검사·워커·수정·재시도·채택은 실행하지 않습니다.

원본은 32KiB씩 읽습니다. 기록 하나는 1MiB, 원본은 256MiB, 기록은 100,000개, 작업은 4,096개, 설정 모듈은 64개로 제한합니다. 중단·거절된 생성 작업은 새 부분 폴더를 남길 수 있지만 마지막 `INDEX.json`이 없으면 조회할 수 없습니다. 기존 출력은 덮어쓰지 않습니다. 생성 중 원본이 바뀌면 완성하지 않습니다. 지원하는 비활성 기록 블록이 없는 일반 HTML은 변환하지 않고 거절합니다.

조회 자료에는 비공개 경로와 발췌문이 들어갈 수 있으며 공개 배포용 자동 가림은 하지 않습니다. 생성·조회만으로 업로드나 AI 전송이 이뤄지지는 않습니다. 해시는 검사 시점의 변경을 확인하며, 같은 파일을 마음대로 바꿀 수 있는 프로세스에 대한 인증·격리 수단은 아닙니다.

## 검수

```text
python -B -m unittest calf_extensions.repository.tests.test_history_index -v
```

정확한 위치 읽기·선택적 조회·보존·CJK·공유 범위·명시적 매핑·오래되거나 수정된 자료·상한을 검사합니다. 이 검사는 팩 관리기의 기존 Git `inspect` 검수 묶음과 별개입니다. 실제 코어 연동과 보관 작업 비교도 따로 확인하며 Git 검수 결과를 새 기능의 결과로 사용하지 않습니다.

구조화된 응답의 `sourceBytesRead`·`indexBytesRead`는 Python 조회기가 읽은 양이며 네이티브 내부 I/O는 미측정으로 표시합니다. 같은 원본을 기준으로 응답 바이트·조회 시간·참조 누락 여부를 비교해야 합니다. 일정한 토큰 절약률이나 속도 배수는 보장하지 않습니다. 이번 추가에는 Workbench 패널·MCP 서버·추가분 전용 인덱서·새 코어 릴리즈가 포함되지 않습니다.
