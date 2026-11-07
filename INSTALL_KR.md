# AI와 함께 설치하기

[English](INSTALL.md) · [README](README_KR.md) · [실제 화면으로 보는 영상 작업 관리](docs/media-jobs-manual/README_KR.md)

이 안내는 AI의 도움을 받아 CALF Extensions를 처음 준비하는 사용자를 위한 문서입니다. **영상 작업 관리 팩 0.1.0-preview.1**를 기준으로 설명합니다. 설치 과정에 AI 모델이나 생성 API 키를 등록할 필요는 없습니다. 영상 생성은 사용 중인 외부 도구에서 수행하고, CALF는 요청·반환·검사·채택·재수정 기록을 관리합니다.

## 먼저 다운로드하세요

**[ZIP 받기 · GitHub](https://github.com/VibePakcr/CALF-Extensions/releases/download/media-jobs-v0.1.0-preview.1/CALF-Video-Work-Management-Pack-0.1.0-preview.1.zip)** · [ZIP 받기 · GitLab](https://gitlab.com/vibepackr-group/CALF-Extensions/-/releases/media-jobs-v0.1.0-preview.1/downloads/CALF-Video-Work-Management-Pack-0.1.0-preview.1.zip)

0.1.0-preview.1을 **새 폴더에 압축 해제**한 뒤 그 안의 `INSTALL_KR.md`를 여세요. 파일 탐색기에서 “파일 확장자 표시”를 켜면 찾기 쉽습니다. 예전 FFmpeg 0.1.0 배포본과는 다른 파일입니다. 압축 해제만으로 기존 CALF나 활성 팩이 교체되지 않습니다.

다른 형식·SHA256SUMS·검증 보고서: [GitHub](https://github.com/VibePakcr/CALF-Extensions/releases/tag/media-jobs-v0.1.0-preview.1) · [GitLab](https://gitlab.com/vibepackr-group/CALF-Extensions/-/releases/media-jobs-v0.1.0-preview.1)

## 1. AI에게 이 문장을 전달하세요

폴더의 파일을 읽고 명령을 실행할 수 있는 AI 도구에서 CALF Extensions 폴더를 연 뒤 다음 요청을 붙여 넣으세요. 일반 채팅만 가능한 AI를 사용한다면 같은 요청으로 설명을 받고, 안내받은 명령을 직접 실행합니다.

```text
이 폴더의 INSTALL_KR.md, AGENTS.md, README_KR.md를 읽고 CALF Extensions의 영상 작업 관리 팩 0.1.0-preview.1를 처음 설치하도록 도와줘.
내 운영체제와 실제 파일 위치를 확인하고, Python 3.10 이상·CALF SDK·네이티브 calf 실행 파일·FFmpeg/ffprobe가 이미 있는지 먼저 찾아줘.
calf_extensions/media_jobs/cli.py가 포함되어 있는지 확인해줘. 없으면 어떤 소스가 필요한지 설명하고, 파일을 임의로 만들어 설치됐다고 하지 마.
있는 도구는 재사용하고, 없는 프로그램을 설치하거나 전역 설정을 바꿔야 한다면 변경 내용을 설명하고 내 확인을 받아줘.
기존 프로젝트·설정·기록·승인 영상은 보존하고, 별도의 새 폴더에서 첫 검증을 진행해줘.
AI API 키 등록, 유료 생성 호출, 기존 프로젝트의 후보 채택은 이번 설치에 포함하지 마.
완료 여부는 실제 명령과 검증 결과로 확인하고, 사용한 경로·첫 실행 명령·검증 결과 위치를 짧게 알려줘. 실행하지 못한 부분은 구분해서 알려줘.
```

## 2. 필요한 기능과 받은 파일을 확인하세요

| 하려는 일 | 준비할 것 / 안내 |
|---|---|
| AI 영상 작업의 요청·반환·재수정 관리 | 이 안내의 `media_jobs` 팩, Python, 별도 CALF SDK·네이티브 실행기, FFmpeg/ffprobe |
| 로컬 FFmpeg로 씬 후보 만들기 | [기존 FFmpeg 확장 안내](docs/FFMPEG_KR.md) |
| 소스 저장소 탐색 | 별도 Repository Navigator 다운로드와 [README의 설치 절차](docs/navigator-manual/README_KR.md). 이 모드는 CALF core·SDK를 요구하지 않습니다. |
| 로컬 Repository 팩 설치·업데이트 | [공통 팩 안내](docs/PACKS_GUIDE_KR.md) |

이 배포본에는 아래 파일이 포함되어 있습니다. README·INSTALL·소스·이미지 폴더를 함께 보관하세요. Python이 있으면 압축을 푼 폴더에서 `python3 -B VERIFY_PACKAGE.py`로 포함 파일의 해시부터 확인합니다. 이 검사는 SDK·CALF 없이 실행되며 실제 작업 성공을 뜻하지 않습니다. 저장소 소스를 사용하는 경우 이 파일 대신 해당 릴리스의 체크섬과 검증 보고서를 확인하세요.

```text
CALF-Video-Work-Management-Pack-0.1.0-preview.1/
  INSTALL_KR.md
  calf_extensions/
    media_jobs/
      cli.py
      verify.py
```

공식 안내: [CALF 네이티브 실행기](https://github.com/VibePakcr/CALF/blob/main/DOWNLOADS.md) · [CALF SDK 0.2.1](https://github.com/VibePakcr/CALF/releases/tag/sdk-v0.2.1) · [Python](https://www.python.org/downloads/) · [FFmpeg](https://ffmpeg.org/download.html)

## 3. AI와 함께 다섯 가지 위치를 찾으세요

| 항목 | 무엇을 선택하나요? |
|---|---|
| CALF Extensions | 이 문서와 `calf_extensions`가 들어 있는 폴더 |
| Python | 3.10 이상의 `python3`; Windows에서는 보통 `python` |
| SDK | 바로 아래에 `calf_sdk` 폴더가 있는 SDK 폴더 |
| 네이티브 실행기 | 실제 `calf` 파일; Windows에서는 `calf.exe`. GUI 앱 실행기를 선택하지 않습니다. |
| 미디어 도구 | 실제 `ffmpeg`·`ffprobe` 파일. Windows에서는 `.exe` 파일입니다. |

기본 권장 방식은 **소스 폴더에서 직접 실행**하는 것입니다. `pip install`이나 전역 셸·MCP 설정 변경은 필요하지 않습니다. 아래 경로는 예시이므로 AI에게 실제 위치로 바꾸도록 하세요. 폴더 이름에 공백이 있어도 따옴표를 유지하면 됩니다.

## 4. 먼저 도움말이 열리는지 확인하세요

macOS/Linux 셸 예시입니다. 이 관리 추가분의 실제 실행 검증은 macOS에서 수행했습니다.

```sh
cd "/absolute/path/to/CALF-Extensions"
export SDK="/absolute/path/to/CALF-SDK-0.2.1"
export NATIVE="/absolute/path/to/calf"
export FFMPEG="/absolute/path/to/ffmpeg"
export FFPROBE="/absolute/path/to/ffprobe"
export PYTHONPATH="$PWD:$SDK"
python3 --version
python3 -B -c 'import calf_sdk; print(calf_sdk.__file__)'
"$NATIVE" --version
python3 -B -m calf_extensions.media_jobs.cli --help
```

`register`, `request`, `receive`, `run`, `adopt`, `reconcile`, `status`가 도움말에 나오면 명령 진입점을 찾은 것입니다. 아직 영상 작업이나 외부 생성 서비스를 실행한 것은 아닙니다. 이 환경변수는 현재 터미널에서만 사용합니다.

Windows PowerShell에서는 다음과 같이 씁니다. 아래는 동등한 경로 설정·도움말 예시이며, 이 추가 관리 흐름의 Windows 실행을 검증했다는 뜻은 아닙니다.

```powershell
Set-Location 'C:\Work\CALF-Extensions'
$SDK = 'C:\Tools\CALF-SDK-0.2.1'
$NATIVE = 'C:\Tools\CALF\calf.exe'
$FFMPEG = 'C:\Tools\ffmpeg\bin\ffmpeg.exe'
$FFPROBE = 'C:\Tools\ffmpeg\bin\ffprobe.exe'
$env:PYTHONPATH = "$((Get-Location).Path);$SDK"
python --version
python -B -c "import calf_sdk; print(calf_sdk.__file__)"
& $NATIVE --version
python -B -m calf_extensions.media_jobs.cli --help
```

## 5. 내 영상 대신 짧은 데모로 첫 검증을 하세요

다음 명령은 FFmpeg로 짧은 합성 영상을 만들고, 별도의 기록·씬 프로젝트에서 요청·반환·검사·채택·복원을 확인합니다. 모델이나 외부 생성 API는 호출하지 않습니다. **아직 존재하지 않는 새 출력 폴더**를 정하세요.

macOS/Linux:

```sh
export CHECK="/absolute/path/to/new-media-install-check"
python3 -B -m calf_extensions.media_jobs.verify --calf "$NATIVE" --ffmpeg "$FFMPEG" --ffprobe "$FFPROBE" --output "$CHECK"
```

Windows PowerShell의 동등한 명령 표기:

```powershell
$CHECK = 'C:\Work\new-media-install-check'
python -B -m calf_extensions.media_jobs.verify --calf $NATIVE --ffmpeg $FFMPEG --ffprobe $FFPROBE --output $CHECK
```

성공하면 출력 폴더의 `verification.json`에 `"status": "PASS"`가 기록됩니다. 도움말만 열린 상태와 전체 검증 통과를 구분하세요. 실패하면 결과 폴더를 남기고 AI에게 실제 오류와 결과를 확인하도록 하세요. 기록을 지우거나 조건을 낮춰 통과시키지 않습니다.

## 6. 내 영상 작업을 시작하세요

이제 [화면을 보며 따라가는 사용 매뉴얼](docs/media-jobs-manual/README_KR.md)의 순서로 진행합니다.

1. 수정 요청과 참조 파일로 `request`를 만듭니다.
2. 생성된 `handoff.txt`와 참조 사본을 사용 중인 영상 도구에 전달합니다.
3. 내려받은 결과를 `receive`로 받고 `run`으로 검사합니다.
4. 원본과 반환본을 직접 검토한 뒤 채택할 버전에만 `adopt`를 사용합니다.

Gemini/Veo 등 외부 도구의 전달·다운로드는 현재 수동 방식입니다. CALF의 기술 검사 통과와 영상의 미적 품질·수정 의도 충족은 별도로 판단합니다.

## 막혔을 때 AI에게 보여 줄 것

| 메시지 또는 상황 | 확인할 것 |
|---|---|
| `No module named calf_extensions` | 터미널 위치가 CALF Extensions 루트인지, 폴더에 `media_jobs`가 있는지 |
| `No module named calf_sdk` | `SDK`가 `calf_sdk`의 부모 폴더인지, 현재 터미널의 `PYTHONPATH`가 맞는지 |
| 네이티브 실행기를 찾지 못함 | `NATIVE`가 실제 `calf`/`calf.exe`의 절대 경로인지 |
| FFmpeg·ffprobe 실행/검사 실패 | 실행 파일 경로, 코덱·필터 지원, 실제 오류 출력 |
| 새 폴더가 필요하다는 오류 | 기존 설정·결과 폴더를 지우지 말고 새 경로를 선택했는지 |
| `VIOLATED` 또는 `UNKNOWN` | 실제 결과와 규격을 확인합니다. 통과나 설치 성공으로 바꿔 보고하지 않습니다. |

AI에게는 운영체제, 사용한 명령, 오류 메시지, 결과 파일 위치를 알려 주면 됩니다. 이 설치에는 비밀번호·API 키가 필요하지 않습니다.

## 업데이트와 보관

새 버전은 별도 폴더에 준비하고 새 도구 설정으로 등록합니다. 기존 계약이 참조하는 소스·SDK·도구 파일을 덮어쓰거나 삭제하면 기존 증거가 무효가 될 수 있습니다. 이전 작업의 기록 폴더, 씬 프로젝트, 승인 영상과 해당 소스·도구 위치를 함께 보존하세요. 자세한 복구는 [영상 관리 안내](calf_extensions/media_jobs/README_KR.md)에서 확인할 수 있습니다.
