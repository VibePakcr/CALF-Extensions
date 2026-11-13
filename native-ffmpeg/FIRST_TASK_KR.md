# 첫 장면 작업 시작하기

[English](FIRST_TASK.md) · [설치](../INSTALL_KR.md) · [전체 명령](README_KR.md)

`first-task` 명령은 **0.2.0-preview.2에 포함**됩니다. 기존 0.2.0-preview.1 다운로드는 전체 명령 안내의 순서를 사용합니다.

CALF·FFmpeg·ffprobe 실행 파일, 지원되는 짧은 영상 하나, 새 결과 폴더를 지정하세요. 도구 등록·두 장면 프로젝트·고정 규격·보존할 요청을 준비하고 후보를 렌더·독립 검사합니다. JSON 파일을 직접 만들거나 명령 사이에서 식별자를 옮기는 준비가 줄어듭니다.

터미널·PowerShell 또는 VS Code·Cursor·PyCharm·Antigravity IDE의 내장 터미널에서 실행할 수 있습니다. 운영체제에 맞는 실행 파일을 사용하세요. 이 명령에 Python·Node·프로젝트 인터프리터·AI 계정·IDE 플러그인은 필요하지 않습니다.

## 먼저 영상 조건 확인하기

별도로 고른 시험용 짧은 영상을 사용하세요. 영상 스트림 하나와 오디오 최대 하나를 지원합니다. 한도는 **입출력 각 64 MiB, 1280×720, 30초, 짝수 가로·세로, 정사각 픽셀, 정수 24·25·30 fps**입니다. 프레임 수와 일치하는 길이가 확인돼야 하며, 회전·지원하지 않는 메타데이터는 거부합니다. 입력 해상도·프레임률·길이를 유지하고 한도에 맞추려 자동 축소·자르기를 하지 않습니다. 출력은 기존 H.264/yuv420p 및 선택적 스테레오 48 kHz AAC 규격입니다.

기존 100 ms 검은 화면·무음 검사를 유지합니다. 무음 검사는 오디오가 있을 때만 적용합니다. 의도한 페이드·무음도 실패할 수 있습니다. 요구 규격이 다르면 명시적 request 경로에서 검토하되, 통과만을 위해 검사를 낮추지 마세요. 기술 검사는 미적 품질을 판단하지 않습니다.

## 명령 하나 실행하기

아래 경로를 실제 경로로 바꾸세요. 새 결과 폴더의 상위 폴더는 있어야 하며 결과 폴더 자체는 없어야 합니다.

macOS/Linux:

```sh
'/absolute/calf-ffmpeg' first-task \
  --calf '/absolute/calf' \
  --ffmpeg '/absolute/ffmpeg' --ffprobe '/absolute/ffprobe' \
  --source '/absolute/clip.mp4' --output '/absolute/new-first-task'
```

Windows PowerShell:

```powershell
& 'C:\Tools\calf-ffmpeg.exe' first-task --calf 'C:\Tools\calf.exe' --ffmpeg 'C:\Tools\ffmpeg.exe' --ffprobe 'C:\Tools\ffprobe.exe' --source 'C:\Media\clip.mp4' --output 'C:\Media\new-first-task'
```

기록·설정·프로젝트를 **새 폴더 안에** 만듭니다. 기존 기록 위치나 설정을 선택하지 않습니다. 어느 장면도 자동 채택하지 않습니다.

## 결과를 보고 선택하기

결과 폴더의 `NEXT.txt`를 여세요. 실제 경로가 들어간 POSIX·PowerShell 명령이 준비됩니다. `first-task-result.json`에 표시된 후보를 재생하고 기술 검사 결과를 확인하세요. `REVIEW_REQUIRED`는 기술 검사를 통과해 사람이 봐야 한다는 뜻이며 승인된 납품물이 아닙니다.

후보를 수락할 때만 채택 명령을 실행하세요. 기존 채택 API가 정확한 파일을 다시 검사합니다. 수락하지 않으려면 채택하지 않은 채 폴더를 보관하면 됩니다.

중단되거나 NOT_READY라면 같은 폴더와 inspect/reconcile 명령을 사용하세요. 렌더 전에 `first-task-prepared.json`을 저장합니다. 자동 재시도를 위해 새 first-task 폴더를 만들거나 시도 수를 초기화하지 마세요. 기존 요청이 참조하는 실행 파일을 교체하지 마세요. 이미 있는 결과 폴더를 재사용하면 거부합니다.

측정값은 기계 처리 단계 시간과 진입 명령 1회입니다. 사람의 준비 시간·클릭 수·토큰 절감은 미측정입니다. 원격 측정·제공자 호출·자동 다운로드는 없습니다.
