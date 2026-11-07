# 로컬 팩 설치·업데이트 프리뷰

[English](PACK_MANAGER.md) · [공통 규격](EXTENSION_PACK_SPEC_KR.md) · [FFmpeg](FFMPEG_KR.md)

v1 메타데이터 읽기, 명시적으로 고른 로컬 의존성 확인, 잠금 정보 보관, 로컬 후보 팩의 준비·검수·활성화를 지원합니다. Python 표준 라이브러리만 사용하며 JSON Schema 런타임 의존성·모델·다운로드 서비스·상주 데몬을 추가하지 않습니다. 메타데이터 확인기는 동봉된 v1 스키마의 제한된 문법만 해석하고 모르는 필드를 거부합니다. 범용 JSON Schema 서비스는 아닙니다.

**로컬 개발 프리뷰**이며 새 공개 릴리즈나 Workbench 팩 UI는 아닙니다. FFmpeg 씬과 [Repository 로컬 Git inspect](REPOSITORY_PACK_KR.md)는 각각의 설치·검수 드라이버를 사용합니다. Repository inspect는 Python·Git만 사용하고 SDK·영상 도구를 로드하지 않습니다. 모션과 계획 단계의 Repository 뷰어 모드는 `UNKNOWN / driver_not_implemented`를 반환합니다. 참조 매니페스트의 설치는 계속 거부합니다. `candidate` 상태는 격리된 설치 검사에 사용하며 experimental/preview 성숙도만 허용합니다. 로컬 검수를 통과한 뒤 명시적으로 실험용 활성화를 선택해야 합니다. 안정 릴리즈 검증은 별도입니다.

## 1. 로컬 경로 준비

CALF Extensions 소스 루트에서 명령을 실행합니다. Windows에서는 `python`과 실제 Windows 경로를 사용하세요. 향후 설치된 배포본에서는 `calf-pack` 진입점도 사용할 수 있습니다. 어떤 명령도 셸·전역 패키지·프로바이더 프로필·MCP 설정·CALF 개인 설정을 바꾸지 않습니다.

팩 파일 밖에 `environment.json`을 준비합니다. 인증정보를 넣지 않습니다.

```json
{
  "python": "/tools/python3",
  "sdk": "/tools/CALF-SDK-0.2.1",
  "calf": "/tools/CALF-Harness-1.8.7/calf",
  "edition": "harness",
  "ffmpeg": "/tools/ffmpeg",
  "ffprobe": "/tools/ffprobe"
}
```

심볼릭 링크 실행기 대신 실제 절대 경로를 선택합니다. `sdk`는 `calf_sdk/`가 있는 상위 폴더입니다. Workbench를 쓰면 GUI 실행기 대신 네이티브 코어와 `edition: workbench`를 지정합니다. 기록 위치를 자동 추정하지 않습니다. 고정된 읽기 전용 버전·기능 명령, import하지 않은 SDK 메타데이터, 공개 코어 버전 정보, 팩의 기존 실행 근거에 기록된 정확한 코어 신원으로 호환성을 확인합니다. 버전 문자열만으로 통과시키지 않습니다.

Windows에서는 `C:\Work\packs`, `C:\Work\media-records`처럼 짧은 로컬 경로를 선택하세요. 이 프리뷰는 네이티브 스냅샷 경로의 여유를 두기 위해 실제 생성되는 검수 자료 루트와 선택한 네이티브 기록 루트를 UTF-16 기준 96자 이내로 제한합니다. 넘으면 실행 전에 거부하며 Windows 전역 긴 경로 정책을 바꾸거나 기존 작업을 옮기지 않습니다. 소스·프로젝트의 CJK 경로는 호스트·도구의 길이 한도 안에서 지원합니다.

## 2. 매니페스트 조회와 준비

참조 자료를 읽을 때 도구를 실행하지 않습니다.

```sh
python3 -B -m calf_extensions.packs.cli inspect --manifest specs/pack-v1/examples/ffmpeg.json
```

신뢰한 로컬 소스로 시험할 때는 기존 배포판 0.1.0을 그대로 두고 **새 후보 팩**을 만듭니다.

```sh
python3 -B -m calf_extensions.packs.build_ffmpeg --source /work/CALF-Extensions --output /work/new-pack-build --version 0.1.1-dev.2
python3 -B -m calf_extensions.packs.cli --home /work/new-pack-store init
python3 -B -m calf_extensions.packs.cli --home /work/new-pack-store stage --archive /work/new-pack-build/CALF-FFmpeg-Pack-0.1.1-dev.2.zip --sha256 ARCHIVE_SHA256 --source owner-reviewed-local-build
```

`build_ffmpeg`는 기존 미디어 코드·공개 안내에 후보 메타데이터와 전체 파일 목록을 붙입니다. pip 배포본이 아니며 코어·SDK·FFmpeg를 동봉하지 않습니다. 신뢰한 빌드·전달 경로에서 얻은 해시를 사용하세요. 출처 문자열은 호출자가 남긴 기록이며 서명이나 실행 권한을 뜻하지 않습니다.

Stage는 파일이 바로 루트에 있는 제한된 ZIP/tar를 받습니다. 위험한 경로·링크·중복·대소문자 충돌·한도 초과·목록 불일치·참조 매니페스트를 활성화 전에 거부합니다. 복사한 압축파일과 최초 오류를 작업 기록에 보존합니다. 같은 ID·버전을 다른 바이트로 덮어쓸 수 없습니다. 같은 파일로 stage를 반복하면 기존 신원만 확인하며 생성기를 실행하지 않습니다.

## 3. 호환 확인·검수·활성화

```sh
python3 -B -m calf_extensions.packs.cli --home /work/new-pack-store check --id calf.media.ffmpeg --version 0.1.1-dev.2 --mode scenes --environment /work/environment.json
python3 -B -m calf_extensions.packs.cli --home /work/new-pack-store qualify --id calf.media.ffmpeg --version 0.1.1-dev.2 --mode scenes --environment /work/environment.json
python3 -B -m calf_extensions.packs.cli --home /work/new-pack-store activate --lock LOCK_ID --expected-active none --experimental
python3 -B -m calf_extensions.packs.cli --home /work/new-pack-store status --id calf.media.ffmpeg
```

`check`는 네이티브 등록·작업 생성을 하지 않습니다. `COMPATIBLE`·`INCOMPATIBLE`·`UNKNOWN`, 관측 기능과 파일 해시를 반환합니다. `qualify`는 새 기록·프로젝트에 기존 합성 미디어 검사를 명시적으로 실행합니다. 선택한 후보·인터프리터·SDK를 `-I -S -B -X utf8`로 실행한 뒤 실제 검사 보고서, 팩 파일과 의존성 해시를 확인합니다. 새 바인딩의 어댑터도 호출마다 유니코드 출력을 명시하며 시스템 언어 설정은 바꾸지 않습니다. 모델·계정 호출은 없습니다.

검수 후 해당 패키지·플랫폼·코어·의존성에 대한 불변 로컬 잠금 ID와 영수증을 만듭니다. 다른 장비의 결과나 종료 코드만으로 통과시키지 않습니다. 선택한 코어의 FFmpeg 검사 12개 그룹에 계약 단위 검사 3개가 포함됩니다. 선택적인 두 번째 코어 비교는 설치 검사의 일부가 아닙니다. 로컬 검수는 미적 수락이나 안정 릴리즈 인증을 뜻하지 않습니다.

활성화에는 잠금 정보, 현재 검증된 파일, 정확한 `expected-active` 해시가 필요합니다. 활성 팩이 없을 때만 `none`을 쓰고, 이후에는 `status`의 `digest`를 사용합니다. 그 사이 선택이 바뀌면 거부합니다. 후보·프리뷰에는 `--experimental`도 필요합니다. 이전 버전과 잠금 정보는 함께 보관하며 다음 작업용 포인터만 바꿉니다. 의존성 검사가 실패해도 `status`는 포인터·해시와 `current: false`를 반환하고 종료 코드 2로 알립니다.

## 4. 실제 FFmpeg 작업 연결

팩 저장소 밖에 별도 미디어 기록 폴더와 [기존 FFmpeg 안내](FFMPEG_KR.md)로 준비한 씬 프로젝트를 둡니다. 기록 폴더는 미리 만들어야 합니다. 현재 활성 팩으로 씬 하나를 요청합니다.

```sh
python3 -B -m calf_extensions.packs.cli --home /work/new-pack-store scene-request --records /work/media-records --project /work/scenes --scene scene-3 --source /media/scene-3.mp4 --key edit-3-first --profile /work/scene-profile.json
python3 -B -m calf_extensions.packs.cli scene-run --binding /work/new-pack-store/bindings/BINDING_ID/binding.json
python3 -B -m calf_extensions.packs.cli scene-inspect --binding /work/new-pack-store/bindings/BINDING_ID/binding.json
```

요청 결과에 바인딩 경로가 표시됩니다. 활성 팩·잠금 정보·기록/프로젝트·복사한 워커·요청 자료를 고정합니다. 이 파일들은 공개 네이티브 어댑터 등록에도 포함되어 실행 전 파일 신원 검사를 받습니다. 등록·제출은 기존 SDK를 사용하며 관리자가 네이티브 저널·SQLite를 직접 쓰지 않습니다. 씬 프로필·소스·범위는 기존 FFmpeg 계약을 따릅니다.

실제 검사와 승인을 확인한 뒤 `scene-adopt --binding PATH`로 기존 씬 채택 검사를 거쳐 선택합니다. `scene-run` 통과에는 현재 네이티브 `verified`와 `SATISFIED`가 모두 필요합니다. 생성기 정상 종료·연결·AI의 설명으로 통과시키지 않습니다. 팩 관리자가 채택·재시도·에이전트 호출을 자동 수행하지 않습니다.

이후 실행·조회·채택은 현재 활성 포인터가 아니라 바인딩의 원래 잠금 정보를 사용합니다. 업데이트·팩 복귀 뒤에도 준비된 작업과 소비한 시도가 유지됩니다. 참조된 팩·SDK·인터프리터·도구·잠금·바인딩 파일은 같은 위치와 내용으로 남아 있어야 합니다. 의존성 누락 시 필요하면 공개 네이티브 API로 상태를 확인하며 다른 버전으로 몰래 대체하지 않습니다.

제출 응답이 유실되면 `scene-reconcile --binding PATH`로 같은 영속 요청을 조회합니다. 다시 제출하지 않습니다. 등록 중단·네이티브 정리 미확인은 미해결 상태로 남기며, 새 요청 키로 실패를 숨기지 않습니다.

## 5. 업데이트·버전 복귀·중단 후 복구

새 버전을 새 폴더에 만들고 stage·qualify한 뒤, `status`의 해시로 활성화합니다. **다음 작업의 선택 버전**을 이전 것으로 바꾸려면 다음과 같이 실행합니다.

```sh
python3 -B -m calf_extensions.packs.cli --home /work/new-pack-store rollback --lock RETAINED_LOCK_ID --expected-active CURRENT_ACTIVE_DIGEST --experimental
python3 -B -m calf_extensions.packs.cli --home /work/new-pack-store recover
python3 -B -m calf_extensions.packs.cli --home /work/new-pack-store recover --acknowledge OPERATION_ID
```

`recover`는 관리자 변경 의도·결과와 현재 신원을 대조합니다. 미디어를 실행하거나 네이티브 기록을 고치거나 작업을 취소·예약 해제하지 않습니다. `COMMITTED_UNACKNOWLEDGED`는 포인터 변경 후 응답·영수증이 유실된 경우, `NOT_APPLIED`는 이전 포인터가 그대로인 경우입니다. `RESUMABLE_STAGE`는 정확한 준비 파일을 확인해 중단된 설치 메타데이터 기록을 마칠 수 있는 경우입니다. 명시적으로 acknowledge하면 이 로컬 기록 정리만 마치며 최초 실패·변경 의도는 남깁니다.

`UNKNOWN`·`SUPERSEDED_OR_UNKNOWN`을 추측으로 해제하지 않습니다. 미완료·실패한 설치 검수도 보존하며 자동 재실행하지 않습니다. 복구 목록은 한 페이지에 작업 항목 128개까지 읽고 `nextCursor`·`pageOnly`를 반환합니다. `--cursor`로 이어서 읽으며 그 사이 목록 세대가 달라지면 처음부터 조회해야 합니다. 한 페이지를 전체 이력 검사라고 표시하지 않습니다.

이전 씬 복원은 별도의 FFmpeg 동작입니다. 팩 복귀는 씬 프로젝트·과거 네이티브 채택·파일·시도·설정을 되돌리지 않습니다. 이 프리뷰는 참조된 작업을 지울 수 있는 자동 이전·삭제/제거·캐시 정리를 제공하지 않습니다.

## 6. 검증과 보장 범위

```sh
python3 -B -m calf_extensions.packs.verify --source /work/CALF-Extensions --environment /work/environment.json --output /work/new-pack-lifecycle-test
```

새 저장소·별도 기록/프로젝트·합성 영상으로 메타데이터/압축파일 거부, 설치 중단, 선택 의존성, 두 버전 설치, 업데이트·복귀 전후 대기 작업 보존, 포인터 교체 전후 실제 프로세스 강제 종료, CAS, 네이티브 바인딩 변조 거부를 확인합니다. `report.json`·각 설치 보고서·최초 실패를 남깁니다. 재사용한 미디어 검사도 이번 후보에서 실제 실행하며 오래된 증거·규격 실패·씬 복원·범위 보존을 확인합니다.

해시는 32 KiB씩 읽습니다. 목록 조회에서 SDK·CV를 import하거나 작업·영상 전체 이력을 올리지 않습니다. 명시적으로 실행한 전경 관리자와 기존 네이티브 실행 경계를 사용하며 자식 실행 시간·출력을 제한합니다. POSIX는 프로세스 그룹을 종료합니다. Windows 호스트 보조기의 시간 초과 정리는 직접 자식만 종료하므로 전체 자식 트리 종료를 보장하지 않습니다. 정상 네이티브 어댑터는 CALF의 기존 프로세스/Job 제어를 유지합니다. 시간 초과·종료 미확인 후에는 다음 변경 전에 상태를 대조해야 합니다.

영수증은 파일 flush·원자적 교체를 사용하며 POSIX에서는 디렉터리도 flush합니다. 프로세스 중단을 시험한 범위이며 갑작스러운 전원 차단의 내구성을 인증하지 않습니다. 메모리/장시간 시험, 등록소 서명, 같은 사용자 권한의 악성 프로세스 격리, GUI 연결, 클라우드 전송, 새 프로바이더 세션도 주장하지 않습니다. 이번 작업은 기존 배포 압축파일을 바꾸거나 새 릴리즈를 게시하지 않습니다.
