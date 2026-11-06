# 로컬 FFmpeg 씬 작업

[English](FFMPEG.md) · [처음으로](../README_KR.md)

씬 하나의 새 후보를 만들고 검사한 뒤, 권한 있는 호출자가 채택하는 프리뷰입니다. 타임라인 합성, AI 이미지·영상 생성, 미적 품질 판단은 포함하지 않습니다.

## 실행 환경 준비

CALF SDK 0.2.1을 별도로 압축 해제합니다. 이 저장소 루트에서 현재 프로세스가 SDK를 읽을 수 있도록 경로를 지정합니다. 전역 셸 설정이나 CALF 설정을 변경할 필요는 없습니다.

macOS/Linux 셸:

```sh
export PYTHONPATH="/절대경로/CALF-SDK-0.2.1"
python3 -B -m calf_extensions.media_ffmpeg.cli --help
```

Windows PowerShell:

```powershell
$env:PYTHONPATH = 'C:\Tools\CALF-SDK-0.2.1'
python -B -m calf_extensions.media_ffmpeg.cli --help
```

설치된 네이티브 `calf`/`calf.exe`, FFmpeg, ffprobe의 실제 절대 경로를 사용합니다. GUI 실행기를 선택하지 마세요. Python 3.10 이상이 필요하며 FFmpeg에 libx264·AAC·검출 필터가 있어야 합니다. 확장이 도구를 내려받거나 설치하지는 않습니다.

개발 중에는 소스 폴더에서 바로 실행할 수 있습니다. setuptools가 있는 별도 환경에서는 `python -m pip install --no-build-isolation --no-deps .`로 로컬 설치할 수도 있습니다. 같은 환경에 별도 SDK도 준비해야 합니다. 이 프리뷰를 PyPI에 게시한 것은 아닙니다.

## 씬 하나의 후보 만들기

아래 경로는 예시입니다. 실제 사용 경로로 모두 바꾸세요. Windows에서도 같은 인수를 사용하되 Windows 절대 경로와 `python` 명령을 사용합니다.

```sh
python3 -B -m calf_extensions.media_ffmpeg.cli --calf /tools/calf --home /work/demo-records register --configuration /work/demo-tools --ffmpeg /tools/ffmpeg --ffprobe /tools/ffprobe
python3 -B -m calf_extensions.media_ffmpeg.cli init --project /work/demo-scenes --scenes scene-1 scene-2 scene-3
python3 -B -m calf_extensions.media_ffmpeg.cli --calf /tools/calf --home /work/demo-records request --project /work/demo-scenes --scene scene-3 --source /media/scene-3.mp4 --registration /work/demo-tools/registration.json --key scene3-first --profile /path/to/CALF-Extensions/calf_extensions/media_ffmpeg/profile.json
python3 -B -m calf_extensions.media_ffmpeg.cli --calf /tools/calf --home /work/demo-records run --ticket /work/demo-scenes/requests/scene3-first/ticket.json
```

등록은 도구·Python 실행 파일·SDK 파일·어댑터 소스를 고정합니다. 요청 생성은 입력과 계약을 보존할 뿐 렌더링하지 않습니다. `run`은 네이티브 작업을 한 단계 실행합니다. 현재 판정이 `SATISFIED`가 아니면 종료 코드 2를 반환합니다. 렌더러 정상 종료만으로 통과하지 않습니다.

후보를 확인하고 채택을 승인했다면 실행합니다.

```sh
python3 -B -m calf_extensions.media_ffmpeg.cli --calf /tools/calf --home /work/demo-records adopt --project /work/demo-scenes --ticket /work/demo-scenes/requests/scene3-first/ticket.json
python3 -B -m calf_extensions.media_ffmpeg.cli inspect --project /work/demo-scenes
```

최초 승인본은 씬별로 요청 → 실행 → 채택을 순서대로 반복합니다. 수정할 때는 **새 요청 키**와 대상 씬 ID, 새 원본을 지정합니다. 다른 씬은 렌더링하지 않습니다. 같은 키·같은 내용은 기존 티켓을 돌려주며, 같은 키의 다른 내용은 거절합니다. 그동안 프로젝트가 바뀌었다면 현재 상태를 확인하거나 새 요청을 만들어야 합니다. 자동으로 오래된 후보를 채택하지 않습니다.

## 기술 검사 범위

[예제 프로필](../calf_extensions/media_ffmpeg/profile.json)은 1초·320×180·25 fps의 H.264/yuv420p MP4와 48 kHz 스테레오 AAC를 요구하며 100 ms를 넘는 검은 화면·무음 구간을 거절합니다. 실제 제작에서 의도한 페이드나 무음은 정상일 수 있으므로 작업에 맞게 프로필을 정하세요.

| 설정 | 프리뷰 한도·의미 |
|---|---|
| 크기 | 짝수 해상도, 가로 16–1280·세로 16–720 |
| 프레임률 | 정수 24·25·30 fps |
| 구간 길이 | 100–30,000 ms, 프레임 수가 정확히 정수인 길이 |
| 시작점 | 원본의 0–3,600,000 ms |
| 오디오 | `true`: AAC 스테레오 48 kHz 요구, `false`: 오디오 제외 |
| 검은 화면·무음 | `null`: 검사하지 않음, 수치: 100 ms 이상·영상 길이 이하 |
| 파일 크기 | 개별 입력·출력 64 MiB 이하 |
| 씬 수 | 1–32개, OS 공용으로 안전한 씬 ID |

MP4/MOV 계열 입력을 파일 프로토콜로만 읽고 MP4로 출력합니다. 독립 검사기는 스트림 구성·해상도·프레임률·디코딩한 프레임 수·길이(허용 오차 50 ms)·코덱과 전체 디코딩을 확인합니다. 검출 창은 100 ms이며, 검은 화면은 설정된 픽셀 임계값에서 화면 비율 98% 이상, 무음은 −50 dB 미만을 기준으로 합니다. 내용의 적절성이나 미적 완성도를 승인하는 검사는 아닙니다.

인코더·디코더 스레드는 2개, 필터 스레드는 1개로 요청합니다. OS 전체 CPU 할당량을 강제하는 것은 아닙니다. 개별 하위 프로세스 제한은 25초이며 진단 출력도 제한합니다. 네이티브 작업 제한은 30초입니다. 시간 초과나 검사 불가 상태는 미확인으로 남기며, 새 시도를 자동 제출하지 않습니다.

## 승인본 보존과 복원

`manifest.json`이 씬별 선택 버전을 가리킵니다. 승인 파일은 `versions/SCENE/VERSION/video.mp4`, 이전 선택 이력은 `manifests/`에 남습니다. 새 미디어를 승인 버전 위에 쓰지 않습니다. 버전 기록은 복사한 파일과 원래 CALF 계약·산출물 목록·검사 영수증을 연결합니다.

검사기는 실제 후보 경로와 해시를 길이가 제한된 영수증 상세 정보(`calf.media.ffmpeg.validation.v1`)에 담습니다. 클라이언트는 이 공개 응답을 읽고 다시 해시를 확인하며, CALF 내부 저장 경로를 추측하지 않습니다. 선택 전에는 네이티브 영수증·후보 파일·프로젝트 해시·현재 선택된 모든 씬을 확인합니다. 프로젝트 잠금과 예상 해시 대조로 이 API를 사용하는 클라이언트 간의 오래된 덮어쓰기를 막습니다.

`inspect`에서 확인한 **현재** 프로젝트 해시와 보존된 버전 ID로 복원합니다.

```sh
python3 -B -m calf_extensions.media_ffmpeg.cli restore --project /work/demo-scenes --scene scene-3 --version RETAINED_VERSION_HASH --expected-manifest CURRENT_MANIFEST_HASH
```

보존된 검증 파일을 다시 선택하는 동작입니다. 재렌더링하거나 네이티브 작업 이력을 다시 쓰지 않습니다. 복사본에는 당시의 검사 증거가 남으며, 변경될 수 있는 원래 후보에 대한 최신 네이티브 판정과는 구분합니다.

제출 응답이 끊겼다면 `--calf`·`--home`과 함께 `reconcile --project /work/demo-scenes --key scene3-first`를 사용합니다. 공개 조회 API로만 확인하며 재제출하지 않습니다. 확인할 수 없으면 미해결 상태로 남깁니다. 남은 잠금이나 불완전한 복사본도 자동 삭제·덮어쓰기하지 않습니다.

읽기 전용 속성은 예방 조치이며 불변 저장소나 OS 샌드박스가 아닙니다. 통제 경로 밖에서 승인 파일이 바뀌면 감지하고 후속 선택을 거절합니다. CALF 채택과 프로젝트 선택을 하나의 원자적 트랜잭션으로 보장하거나, 정전 복구·무제한 파일 접근 권한을 가진 프로세스의 변경까지 방지하지는 않습니다. 중단 후에는 현재 상태를 확인하세요.

## 실제 수락 시험

**새 출력 폴더**를 사용합니다. 짧은 합성 영상과 별도 기록을 만들며, 모델이나 네트워크 서비스를 호출하지 않습니다.

```sh
python3 -B -m calf_extensions.media_ffmpeg.verify --calf /tools/calf --workbench /tools/workbench-core/calf --ffmpeg /tools/ffmpeg --ffprobe /tools/ffprobe --output /work/new-media-test
```

`--workbench`는 같은 기록을 읽을 두 번째 네이티브 코어가 있을 때 지정하는 선택 항목입니다. 승인 씬 3개·3번 씬만 수정·실패 후보·증거 무효화·복원·중복 요청·응답 유실 복구·읽기 전용 MCP·승인 파일 외부 변경 감지를 확인합니다. 실제 검증 범위와 미검증 플랫폼은 [VERIFICATION.json](../VERIFICATION.json)에 기록합니다.
