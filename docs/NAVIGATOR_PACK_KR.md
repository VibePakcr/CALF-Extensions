# CALF Repository Navigator - 무료 프리뷰

[English](NAVIGATOR_PACK.md)

Local Git·GitHub.com·GitLab.com에서 사용할 저장소를 직접 선택하고, 같은 화면에서 관계 지도·설명·코드·Diff를 탐색하는 확장팩입니다. Python 3.10 이상·Git 2.43 이상과 최신 브라우저가 필요하며 CALF 코어·SDK·모델은 필요하지 않습니다.

신뢰할 수 있는 배포본을 새 폴더에 풉니다. 라이선스 고지와 배포 SHA256을 확인하고 그 폴더에서 실행하십시오.

```text
python START_NAVIGATOR.py install --home STORE --data-dir DATA --preview
python START_NAVIGATOR.py open --home STORE
```

STORE와 DATA는 서로 다른 폴더이며 조사하는 저장소 밖에 둡니다. 현재 폴더 기준 상대 경로도 물리적인 절대 경로로 변환합니다. `install`이나 `open`에 `--repo PROJECT`를 붙이면 기존 Local Git worktree 하나를 연결합니다. 저장소·계정을 자동 탐색하지 않으며 프로젝트 없이 열면 수동 소스 등록 화면이 나타납니다.

설치는 Python·Git의 정확한 신원을 확인하고 임시 저장소에서 로컬·원문·원격 fixture·포털 검사를 네트워크 없이 수행합니다. 설치 검수 잠금 정보와 명시적인 프리뷰 활성화를 보존합니다. 전역 도구 설치·CALF 기록 이전을 하지 않습니다. 브라우저·실제 계정 검증은 별도 범위입니다.

소스 메뉴에서 GitHub·GitLab URL을 등록하세요. 브랜치·태그·전체 커밋 ID 중 기준을 고르고 이름을 지정한 뒤 수집을 시작합니다. 작업 파일과 인덱스는 Local Git에서만 사용하며, 원격 Diff는 고정한 양쪽 스냅샷을 직접 비교합니다. 부분 수집·원문 미확보·미확인 범위를 그대로 표시합니다. 원격 수집은 파일당 1MiB·원문 총 64MiB·요청 300회/120초로 제한하며 지도 표시 범위는 500개 노드입니다.

인증 참조가 필요하면 `open --credential-env MY_TOKEN_NAME`으로 실행합니다. 지정한 환경 변수의 값만 파이프로 설치 워커에 전달하며 소스 등록에도 같은 변수 이름을 적습니다. 토큰 값을 명령·URL·스크린샷·매뉴얼에 넣지 마십시오. 공개 저장소에 익명으로 접근할 때도 제공자의 API 한도가 적용됩니다. 비공개 계정 사용은 공개 프리뷰의 검증 범위에 포함되지 않습니다. gh 인증 어댑터도 제공하지 않습니다.

작업 공간과 수집본은 설치된 팩 폴더 밖에 보존합니다. 각 뷰어 세션은 설치 검수를 통과한 팩 버전과 작업 공간 잠금을 유지합니다. Windows를 포함해 **뷰어 종료** 버튼으로 정상 정지한 뒤 탭을 닫으십시오. 중단된 세션이 수집 성공을 뜻하지 않습니다.

반환한 바인딩으로 `python START_NAVIGATOR.py run --binding BINDING -- sources list` 등 기존 `calf-repo` 명령을 사용합니다. Local root·data·Git·매핑 경로는 바인딩에 고정해 전달 인수로 덮어쓰지 못합니다. `inspect --binding BINDING`으로 세션 결과를 조회합니다.

실화면 설명서는 `manuals/en.html`, `manuals/ko.html`과 각 PDF입니다. 설치 뷰어의 사용 안내 링크도 같은 로컬 문서를 엽니다. 오프라인 내보내기의 원문·origin 포함은 명시적이며 기존 수집본을 덮어쓰지 않습니다. 원격 소스의 에디터 기능은 별도 보존 사본을 준비합니다. Local Git 링크는 선택한 파일 경로를 열며 작업 파일을 편집하면 해당 프로젝트가 바뀝니다. 에디터를 열기 전에 버전과 경로를 확인하세요. 외부 에디터를 실제로 실행하는 동작은 검증하지 않았습니다.

업데이트는 새 배포본의 `install`에 같은 저장소·작업 공간과 `--preview`, 현재 active digest를 `--expected-active`로 지정합니다. 보존 버전 선택은 `rollback --home STORE --lock OLD_LOCK --expected-active CURRENT_DIGEST --preview`입니다. 이전 바인딩은 원래 버전을 유지하며 팩·수집본·영수증을 보존합니다. 자동 이전·제거·캐시 정리·원격 쓰기·상주 서비스는 제공하지 않습니다.

