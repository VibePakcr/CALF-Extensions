# Rust FFmpeg 씬 작업

[English](README.md) · [설치](../INSTALL_KR.md)

기존 CALF 씬 작업 규약을 Rust로 구현했습니다. 실행할 때마다 새 후보를 저장하고, 별도 검수기가 ffprobe와 FFmpeg 전체 디코딩으로 해당 파일의 정확한 바이트와 확정된 규격을 확인합니다. 채택은 현재 네이티브 SATISFIED 근거를 확인한 뒤 선택한 씬만 변경합니다. 원본·이전 후보·다른 승인 씬은 보존합니다.

## 명령

예시를 실제 절대 경로로 바꾸세요. Windows에서는 `calf.exe`, `calf-ffmpeg.exe`, `ffmpeg.exe`, `ffprobe.exe`를 사용합니다. 공백이 있는 경로는 따옴표로 묶어 인수 하나로 전달하세요.

```sh
calf-ffmpeg --version
calf-ffmpeg verify --calf /absolute/calf --ffmpeg /absolute/ffmpeg --ffprobe /absolute/ffprobe --output /absolute/new-test-folder
calf-ffmpeg init --project /absolute/new-project --scenes scene1 scene2
calf-ffmpeg --calf /absolute/calf --home /absolute/records register --configuration /absolute/new-config --ffmpeg /absolute/ffmpeg --ffprobe /absolute/ffprobe
calf-ffmpeg --calf /absolute/calf --home /absolute/records request --project /absolute/new-project --scene scene1 --source /absolute/source.mp4 --registration /absolute/new-config/registration.json --key first --profile /absolute/profile.json
calf-ffmpeg --calf /absolute/calf --home /absolute/records run --ticket /absolute/new-project/requests/first/ticket.json
calf-ffmpeg --calf /absolute/calf --home /absolute/records adopt --project /absolute/new-project --ticket /absolute/new-project/requests/first/ticket.json
calf-ffmpeg inspect --project /absolute/new-project
calf-ffmpeg restore --project /absolute/new-project --scene scene1 --version RETAINED_VERSION_SHA --expected-manifest CURRENT_MANIFEST_SHA
```

다음 예시를 `profile.json`으로 저장하세요.

```json
{"width":320,"height":180,"fps":25,"startMs":0,"durationMs":1000,"audio":true,"maxBlackMs":100,"maxSilenceMs":100}
```

## 제한과 복구

워커 하나, 작업당 시도 한 번, 시도당 30초, 입력·출력당 64 MiB, 최대 1280×720·30초 영상으로 제한합니다. 프로필과 렌더 인수는 고정하며 임의 FFmpeg 옵션은 받지 않습니다. CPU 렌더에는 스레드 두 개를 사용하고 도구·어댑터·설정 파일의 해시를 고정합니다.

의도적으로 새 후보를 만들 때는 새 요청 키를 사용하세요. 같은 키와 같은 요청은 보존된 티켓을 반환하며, 같은 키로 다른 내용을 요청하면 거절합니다. 연결 실패 후에는 같은 `--calf`, `--home`으로 `reconcile --project PROJECT --key KEY`를 실행하고 상태를 확인하세요. 실행 여부가 불명확한 작업을 다시 제출하지 않습니다. `restore`는 현재 채택 목록의 해시를 확인한 뒤 보존된 검증 버전을 선택합니다. 영상을 다시 만들거나 발생한 비용을 환불하지 않습니다.

메타데이터가 없거나 실행이 불명확하면 UNKNOWN, 영상 규격이 틀리면 VIOLATED로 남깁니다. 렌더러의 종료 코드 0만으로 검수 통과를 판정하지 않습니다. 기술 검사는 미적 품질·편집 의도를 판단하지 않으므로 채택 전에 후보를 직접 확인하세요. 공개 API를 사용하는 확장이며, 이를 거치지 않은 직접 호출을 통제하지는 않습니다.

기존 씬·프로젝트 기록은 v1 규약을 유지합니다. 과거 후보와 영수증을 다시 쓰지 않으며, Rust 확장을 별도로 설치했다고 이전 Python 워커의 영수증을 새 실행 근거로 바꾸지 않습니다.
