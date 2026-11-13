# CALF Extensions 설치

**IDE에서 Workbench 열기:** [CALF Connect 설치](ide-connect/INSTALL_KR.md) · [화면 매뉴얼](ide-connect/MANUAL_KR.md)

**영상 작업 관리:** 아래 FFmpeg 설치를 따르세요. 두 항목은 각각 설치합니다.

## Rust FFmpeg 확장 설치

1번의 버전은 현재 릴리즈에서 검증한 최소 조합이며 최신 버전 표시가 아닙니다. [현재·과거 검증 구분](CURRENT_VERIFICATION.md#한국어)을 확인하세요.

영상 준비 전에 프리뷰 한도인 입출력 각 64 MiB·1280×720·30초·짝수 가로세로·정수 24/25/30 fps를 확인하세요.

FFmpeg 0.2.0-preview.2는 [첫 작업 안내](native-ffmpeg/FIRST_TASK_KR.md)로 진입 명령을 하나로 줄이고 시각 검토·채택은 직접 선택하도록 했습니다. 기존 preview.1 다운로드는 [전체 명령 순서](native-ffmpeg/README_KR.md)를 사용합니다. 터미널·PowerShell 또는 IDE 내장 터미널에서 실행하며 IDE 설정은 바꾸지 않아도 됩니다.


[English](INSTALL.md)

1. CALF 공식 릴리즈에서 하네스 1.8.15 또는 워크벤치 1.9.11을 받으세요. 기존 기록 위치·계약·설정·과거 실행 파일은 보관합니다.
2. 현재 릴리즈에서 OS와 아키텍처에 맞는 FFmpeg 확장을 받으세요. 압축 파일의 SHA-256을 확인한 뒤 새 폴더에 풀고 이전 버전도 남겨 둡니다.
3. 이미 설치된 FFmpeg와 ffprobe 실행 파일을 선택하세요. 이 과정에서 도구를 자동 설치하거나 모델을 호출하지 않습니다.
4. 패키지의 `calf-ffmpeg --version`을 실행한 뒤 [명령 안내](native-ffmpeg/README_KR.md)를 따라 진행하세요. 실제 위치의 절대 경로를 사용합니다. Windows 실행 파일에는 `.exe`가 붙습니다.

코어의 `calf pack` 명령으로 임시 설치·호환성 확인·독립적인 합성 영상 검수·명시적 활성화·이전 버전 선택을 할 수 있습니다. 정확한 옵션은 `calf pack --help`에서 확인하세요. 체크섬은 파일의 무결성을 확인할 뿐 배포자의 신원을 보증하지 않습니다. 신뢰할 수 없는 패키지는 활성화하지 마세요.

Repository Intelligence는 이미 기본 기능입니다. 이전 Repository 팩을 중복 설치하지 마세요. 다른 과거 확장은 이번 배포에 포함하지 않습니다.

원본 영상·기록·계약·무관한 설정을 확장 폴더로 복사할 필요가 없습니다. 첫 검증은 새 합성 프로젝트에서 진행하세요. 기술 검사는 사용자의 시각적 검토를 대신하지 않습니다.

FFmpeg 0.2.0-preview.2에는 [첫 작업 안내](native-ffmpeg/FIRST_TASK_KR.md)의 `first-task`가 포함됩니다. 기존 preview.1은 변경하지 않습니다.


## FFmpeg 다운로드 · 0.2.0-preview.2

- [macos arm64](https://github.com/VibePakcr/CALF-Extensions/releases/download/ffmpeg-v0.2.0-preview.2/CALF-FFmpeg-0.2.0-preview.2-macos-arm64.zip)
- [windows x86_64](https://github.com/VibePakcr/CALF-Extensions/releases/download/ffmpeg-v0.2.0-preview.2/CALF-FFmpeg-0.2.0-preview.2-windows-x86_64.zip)
- [linux x86_64](https://github.com/VibePakcr/CALF-Extensions/releases/download/ffmpeg-v0.2.0-preview.2/CALF-FFmpeg-0.2.0-preview.2-linux-x86_64.tar.gz)
