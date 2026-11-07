# CALF 프로젝트 지도 개발 미리보기

[English](REPOSITORY_NAVIGATOR.md) · [구현 계획](REPOSITORY_LOCAL_GIT_PLAN_KR.md) · [검증 범위](../REPOSITORY_VERIFICATION.json)

프로젝트의 기능·정의·문서·파일·심볼을 관계 지도로 만들고, 지도 아래에서 설명·원문·Diff·출처를 탐색하는 무료 확장입니다. Local Git은 정확한 원문과 버전을 확인하는 하위 계층입니다. 이 확장은 Git 작업 실행 화면을 제공하지 않습니다.

현재는 소스에서 실행하는 개발 미리보기입니다. Python 3.10 이상·Git 2.43 이상·최신 브라우저를 요구합니다. 실제 검증한 버전은 검증서에 따로 기록합니다. 기본 실행에는 SDK·CALF 코어·FFmpeg·계정·모델 API가 필요하지 않습니다.

## 프로젝트 열기

저장소 루트에서 다음처럼 실행합니다. `DATA_DIRECTORY`는 대상 저장소와 그 Git 디렉터리 밖의 별도 앱 데이터 폴더입니다.

```text
python -m calf_extensions.repository.cli open --repo PROJECT_DIRECTORY --data-dir DATA_DIRECTORY
```

브라우저가 프로젝트 포털을 엽니다. 서버는 `127.0.0.1`의 임의 포트에서 이 터미널 프로세스가 열린 동안만 실행합니다. `Ctrl+C`로 종료합니다. 자동으로 브라우저를 열지 않으려면 `--no-browser`를 붙입니다. 설치한 패키지에서는 같은 기능을 `calf-repo` 명령으로 실행할 수 있습니다.

등록한 폴더의 추적 파일만 수집합니다. PC나 GitHub·GitLab 계정 전체를 스캔하거나 등록하지 않습니다. 첫 사용 시 프로젝트를 명시적으로 지정하고, 이후 갱신도 새로고침으로 요청합니다. 원래 소스·refs·index·Git 설정·CALF 기록은 변경하지 않습니다. 수집본과 캐시는 별도 데이터 폴더에 생성합니다.

## 기능과 용어 연결

구조·문서 링크·Python 정의/docstring·해석 가능한 정적 연결은 자동 수집합니다. 제품 기능의 의미는 임의로 생성하지 않습니다. 별도 UTF-8 JSON을 `--project-map CONFIG_FILE`로 지정하면 기능·용어·문서 출처와 코드 대상을 연결할 수 있습니다.

```json
{
  "label": "Example project",
  "description": "Prepare and calculate a result.",
  "features": [{
    "id": "execution",
    "label": "Work execution",
    "definition": "Prepare an input and calculate one result.",
    "references": [{"path": "docs/architecture.md", "start_line": 1, "end_line": 3}],
    "targets": [{"path": "app/main.py", "symbol": "run"}]
  }],
  "terms": [{"id": "result", "label": "Result", "definition": "A calculated value."}]
}
```

경로는 프로젝트 상대 경로이며 심볼은 해당 파일의 `Class.method` 또는 `function` 형태입니다. 중복 ID·경로 탈출·잘못된 줄 범위는 거절합니다. 없는 파일·심볼·문서 범위는 미해결 연결로 표시합니다. 사용자 정의·주석·커밋 메시지·코드는 UI 언어 전환으로 번역하지 않습니다.

## 지도와 상세 패널

파일/심볼 보기, 들어옴/나감, 1·2·3단계/분석된 전체, 검색, 확대·이동·맞춤, 영향 후보를 사용합니다. 영향 후보는 역방향 정적 연결이며 실제 런타임 영향 확정이 아닙니다. 큰 지도는 표시 수와 전체 분석 범위를 구분합니다.

노드나 관계를 선택하면 맵 아래에서 설명·연결 기능·발견 위치·줄번호 코드를 확인합니다. 분석 시점 수집본과 HEAD·index·현재 작업 파일을 구분하고, HEAD와 선택 버전의 Diff를 제공합니다. 충돌 index는 삭제 파일로 표현하지 않고 stage 1/2/3을 따로 읽을 수 있습니다.

현재 파일이 수집 후 바뀌거나 사라지면 새로고침을 요구합니다. 분석 중 변경도 완료된 지도를 대체하지 못합니다. 탐색 이력·파일 고정·코드 높이·줄·카메라 상태를 유지하고, 다른 수집본의 링크는 같은 버전으로 오인하지 않도록 거절합니다. VS Code URI와 경로·줄 복사를 제공합니다. 실제 편집기 실행 검증 여부는 검증서를 확인합니다.

## 수집과 오프라인 보존

```text
python -m calf_extensions.repository.cli scan --repo PROJECT_DIRECTORY --data-dir DATA_DIRECTORY --project-map CONFIG_FILE
python -m calf_extensions.repository.cli export --data-dir DATA_DIRECTORY --capture CAPTURE_ID --output NEW_DIRECTORY
python -m calf_extensions.repository.cli export --data-dir DATA_DIRECTORY --capture CAPTURE_ID --output NEW_DIRECTORY --include-source
```

`scan`은 포털을 열지 않고 수집 ID·범위·개체/관계 수를 반환합니다. `export`는 기존 수집본만 사용하고 원본 저장소를 다시 읽지 않습니다. 새 출력 폴더에 `START_HERE.html`, `project-navigation.json`, `MANIFEST.json`을 만듭니다. 원문은 기본 제외이며 `--include-source`로 이미 수집한 원문과 캐시된 Diff를 포함합니다. 출력 manifest에 실제 포함·제외 범위를 기록합니다.

정적 포털은 원본 저장소와 서버 없이 열립니다. 이 미리보기의 오프라인 코드 보기는 분석 시점에 보존한 원문에 한정됩니다. 다른 버전의 원문이나 Diff가 보존되지 않았으면 미확보로 표시합니다. 원래 절대 root·에디터 경로·접근 토큰·Git 설정·CALF 기록을 자동으로 포함하지 않습니다. 원문 포함은 사용자가 선택한 실제 프로젝트 내용의 공유입니다.

## 검증한 범위와 후속 단계

커밋 범위의 소스로 macOS wheel 빌드·격리 설치·`calf-repo --help`·자산/스키마 포함·SDK 비의존 실행도 확인했습니다. Windows·Linux의 wheel 설치는 미검증이며 기존 릴리즈 압축파일은 유지합니다.

2026-11-07 합성 검증에서 macOS Chrome·Windows Edge·Debian Chrome을 확인했습니다. Debian은 백엔드 검사 22개 통과, Windows는 21개 통과와 POSIX 전용 수명주기 검사 1개 제외입니다. 실제 브라우저에서 지도와 하단 상세 패널·호출 줄·Diff·탐색 복원·반응형 폭·핀치 에뮬레이션을 확인했습니다. 실제 휴대전화·Windows 네이티브 프로세스 트리 제한·실제 에디터 실행은 미검증입니다. 최초 실패 이력과 정확한 버전은 연결된 검증서를 확인하십시오.

첫 분석기는 Python 표준 AST를 사용합니다. 동적 호출·모호한 재바인딩·미지원 구문은 해석된 호출로 만들지 않습니다. Rust·JS/TS 등은 파일·문서·버전 탐색을 제공하며 심볼/호출 분석은 아직 미지원입니다. Bare·partial/promisor repository는 거절하고 shallow 경계를 표시합니다. LFS payload·submodule·symlink 대상은 자동으로 따라가지 않습니다.

CALF 검증 근거 연결, GitHub·GitLab API, 계정 탐색, 언어별 추가 분석기와 배포 전 검수는 후속 단계입니다. 이 색인은 수집한 자료를 탐색하기 위한 것입니다. 릴리즈 권한이나 검사 성공을 판정하는 근거는 아닙니다. 기존 FFmpeg 확장과 CALF 기록을 이동하거나 다시 쓰지 않습니다.
