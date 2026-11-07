# Repository 팩: 로컬 설치와 작업 보존

[English](REPOSITORY_PACK.md) · [팩 관리기](PACK_MANAGER_KR.md) · [프로젝트 탐색기](REPOSITORY_NAVIGATOR_KR.md)

기존 Local Git 읽기 기능을 공통 팩 관리기에 연결한 후보 팩입니다. HEAD·인덱스·작업 파일의 버전을 수집하고 각 항목의 출처를 확인할 수 있는 프로젝트 지도를 만듭니다. 읽기 전용 모드에는 Python 3.10 이상과 Git 2.43 이상만 필요합니다. CALF 코어·SDK, 모델 계정, 영상 도구, 상주 서비스는 필요하지 않습니다.

관리되는 모드는 `inspect`입니다. GitHub·GitLab 원격 자료와 실시간 브라우저 화면은 별도 안내·검증 범위를 따릅니다. 이 팩을 설치해도 자동으로 연결되지 않습니다. 오프라인 페이지는 저장된 수집 결과이며, 실시간 워크벤치나 프로젝트 테스트 통과 증거는 아닙니다.

## 별도 로컬 저장소에 설치

실제 절대 경로를 사용하세요. 명령은 압축을 푼 Local Pack Tools 폴더 또는 CALF Extensions 소스 루트에서 실행합니다. 전역 Python 환경에는 설치하지 않습니다. 팩 파일이 들어 있는 폴더 밖에 `environment.json`을 만드세요.

```json
{"python":"/physical/path/to/python3","git":"/physical/path/to/git"}
```

Windows에서는 `python`과 Windows 경로를 사용하세요. 시험·저장소 경로는 짧게 지정해야 합니다. 기존 관리기는 Windows 경로 길이 한도를 넘는 검수 폴더를 거부하며 OS 설정을 바꾸지 않습니다.

검토한 로컬 소스로 새 후보를 만들거나 제공된 ZIP과 SHA-256을 사용합니다.

```sh
python3 -B -m calf_extensions.packs.build_repository --source /work/CALF-Extensions --output /work/repo-pack-build --version 0.1.0-preview.1
python3 -B -m calf_extensions.packs.cli --home /work/repo-pack-store init
python3 -B -m calf_extensions.packs.cli --home /work/repo-pack-store stage --archive /work/repo-pack-build/CALF-Repository-Pack-0.1.0-preview.1.zip --sha256 TRUSTED_ARCHIVE_SHA256 --source reviewed-local-build
python3 -B -m calf_extensions.packs.cli --home /work/repo-pack-store check --id calf.repository.local-git --version 0.1.0-preview.1 --mode inspect --environment /work/environment.json
python3 -B -m calf_extensions.packs.cli --home /work/repo-pack-store qualify --id calf.repository.local-git --version 0.1.0-preview.1 --mode inspect --environment /work/environment.json
python3 -B -m calf_extensions.packs.cli --home /work/repo-pack-store activate --lock LOCK_FROM_QUALIFY --expected-active none --experimental
```

`check`는 지정한 Python·Git의 해시와 지원 버전을 확인합니다. 드라이버의 읽기 정책과 실제 동작 검수는 구분합니다. `qualify`는 폐기 가능한 로컬 저장소에서 Git 계약, 탐색 계약, 제한 조건의 세 시험 그룹을 실행합니다. 건너뛰거나 누락·실패한 그룹이 있으면 통과시키지 않습니다. 호환성 확인만으로는 팩을 활성화할 수 없습니다. 기존 저장소, CALF 기록, 호스트 설정은 설치 검수에 사용하지 않습니다.

## 설치한 버전으로 작업

기존 저장소와, 그 저장소·팩 저장소 바깥의 빈 데이터 폴더를 선택하세요. 데이터 폴더에는 수집 결과를 보존합니다. 기존 CALF 기록을 이곳으로 옮기지 않습니다.

```sh
python3 -B -m calf_extensions.packs.cli --home /work/repo-pack-store repo-bind --repo /work/my-project --data-dir /work/project-captures
python3 -B -m calf_extensions.packs.cli repo-run --binding /work/repo-pack-store/bindings/BINDING_ID/binding.json
python3 -B -m calf_extensions.packs.cli repo-inspect --binding /work/repo-pack-store/bindings/BINDING_ID/binding.json
python3 -B -m calf_extensions.packs.cli repo-export --binding /work/repo-pack-store/bindings/BINDING_ID/binding.json --output /work/project-map
```

`repo-bind`는 현재 검수를 통과한 팩 잠금 정보와 선택 경로를 고정합니다. `repo-run`은 그 버전으로 한 번 수집합니다. 같은 바인딩을 다시 실행하면 새로 수집하지 않고 기존 영수증을 돌려줍니다. 실행은 시작됐지만 영수증이 없다면 `UNKNOWN`으로 남깁니다. 다음 동작 전에 상태를 확인하세요. 새로 수집하려면 새 바인딩을 명시적으로 만들어야 합니다.

워커가 끝난 뒤 부모 프로세스가 수집 파일·프로젝트 맵·포함된 소스 캐시의 해시를 별도로 확인합니다. 읽기 경로에서는 커밋·체크아웃·fetch나 저장소의 훅·필터·인증 도구를 호출하지 않습니다. 정확한 파일 버전과 수집 범위의 한계도 표시합니다. `PARTIAL`은 전체 수집 완료가 아니며 CLI도 0 이외의 결과를 반환합니다. 수집 결과는 관측 자료이고, 프로젝트의 애플리케이션 테스트를 통과한 CALF 네이티브 `CHECK` 영수증과는 다릅니다.

오프라인 내보내기는 기본적으로 소스 본문을 제외합니다. 캡처된 코드를 새 내보내기 폴더에 복사하려는 경우에만 `--include-source`를 추가하세요. 기존 내보내기는 덮어쓰지 않습니다. 보존된 결과를 조회할 때 원래 저장소를 다시 수집하지 않습니다.

## 업데이트·이전 버전 선택·중단 복구

다음 버전을 새 폴더에서 빌드·저장·검수하세요. `status`에 나온 현재 digest를 `--expected-active`로 지정해 활성화합니다.

```sh
python3 -B -m calf_extensions.packs.cli --home /work/repo-pack-store status --id calf.repository.local-git
python3 -B -m calf_extensions.packs.cli --home /work/repo-pack-store activate --lock NEW_LOCK --expected-active CURRENT_DIGEST --experimental
python3 -B -m calf_extensions.packs.cli --home /work/repo-pack-store rollback --lock OLD_LOCK --expected-active NEW_DIGEST --experimental
python3 -B -m calf_extensions.packs.cli --home /work/repo-pack-store recover
```

두 버전, 잠금 정보, 최초 작업 기록과 수집 결과를 모두 보존합니다. 업데이트·이전 버전 선택은 앞으로 만드는 바인딩에만 적용됩니다. 기존 바인딩은 활성 팩이 바뀌어도 원래 팩·의존성·영수증을 사용합니다. 소스·의존성이 달라진 잠금은 사용할 수 없으며, 새 실행 파일로 자동 대체하지 않습니다.

설치·활성화 중 종료됐다면 `recover`로 남아 있는 의도와 실제 바이트를 대조합니다. `recover --acknowledge 작업_ID`는 확인된 설치 기록만 정리하며 수집을 다시 실행하거나 기존 결과를 고치지 않습니다. 불확실하게 종료된 수집은 계속 불확실한 상태로 남습니다. 페이지별 조회와 프로세스 중단 검증의 한계는 팩 관리기 안내를 참고하세요.

의존성 자동 다운로드, 레지스트리 접속, 캐시 자동 삭제, 팩 삭제, 모델 위임, 멀티 에이전트 실행기는 추가하지 않습니다. 해시는 작은 청크로 읽고 선택한 수집 결과만 로드합니다. 호스트·OS의 기존 권한과 읽기 드라이버의 통제 범위는 별개입니다.
