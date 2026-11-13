# CALF Connect · 0.1.0-dev.1

[English](README.md) · **[설치부터 시작](INSTALL_KR.md)** · [화면 매뉴얼](MANUAL_KR.md) · [검증 범위](QUALIFICATION.json)

평소 쓰는 IDE에서 CALF Workbench를 열고 작업 주의 목록을 읽습니다. 프로젝트마다 한 번 연결하면 다음에도 같은 명령을 사용합니다.

VS Code·Cursor·Antigravity IDE는 공통 VSIX 하나를 사용합니다. PyCharm은 같은 전송 정의를 쓰는 별도의 IntelliJ 어댑터입니다. 분리 프로필에서 실제 메뉴 → 연결 설정 → 네이티브 조회 → Workbench 실행을 **macOS·Windows·Debian, 12개 조합**으로 확인했습니다.

![실제로 표시된 공통 CALF 명령 팔레트](docs/images/macos-antigravity-commands.png)

## 다운로드·연결

[GitHub 릴리즈](https://github.com/VibePakcr/CALF-Extensions/releases/tag/connect-v0.1.0-dev.1) · [GitLab 릴리즈](https://gitlab.com/vibepackr-group/CALF-Extensions/-/releases/connect-v0.1.0-dev.1)

VS Code 계열은 VSIX를 설치하고 PyCharm은 `Plugins → Install Plugin from Disk…`에서 ZIP을 선택합니다. 프로젝트를 열고 **Configure this workspace connection**에서 기존 CALF 코어·기록 폴더·Workbench 실행 파일을 지정하세요. [설치 안내](INSTALL_KR.md)에 선택 대상과 OS별 경로를 설명했습니다.

| 명령 | 용도 |
| --- | --- |
| Configure this workspace connection | 이 프로젝트의 연결을 직접 저장 |
| Read work attention | 네이티브 읽기 전용 응답 확인 |
| Open Workbench | 기존 Workbench 열기 |
| Copy read-only MCP server entry | 호환 클라이언트에서 직접 설정할 연결 항목 복사 |

작업 제출·모델 호출·승인·계약 변경·완료 판정은 수행하지 않습니다. 활성화할 때 서버도 시작하지 않습니다. Workbench 실행은 창 열기 요청이며 실제 기록 위치를 확인하는 방법은 매뉴얼에 설명했습니다. 토큰 절감률은 주장하지 않습니다.

## 검증 범위

[매뉴얼](MANUAL_KR.md#검증-범위)에 IDE별 버전과 실제 화면을 정리했습니다. JavaScript 전송 테스트와 Java 검사에서도 유니코드 경로 전달·응답 크기 제한·실행 파일 변경 차단·읽기 전용 동작·제어 플래그 부재를 확인합니다. PyCharm은 macOS에서 정상 종료·재시작 후 연결 유지도 확인했습니다.

직접 설치하는 서명 없는 개발 프리뷰이며 마켓플레이스 등록이나 운영 수락을 뜻하지 않습니다. 다른 JetBrains 제품과 Cursor 빈 창 동작은 미검증입니다. 기존 기록·계약·설정·이전 런타임은 별도로 유지하며 기존 작업이 참조하는 동안 보관하세요.

## 개발

작업 판단은 네이티브 API가 담당합니다. 빌더는 기존 Node와 설치된 macOS PyCharm의 JDK·API JAR을 사용합니다. 의존성을 내려받지 않으며 IDE·Gson·CALF 비공개 코어를 묶지 않습니다.

```sh
CALF_IDE_TEST_CORE=/absolute/calf python3 ide-connect/tools/build.py
```

프로젝트의 빌드·출력 규칙을 따르세요. 외부 빌드는 `VIBEPACKR_T9_BUILD`로 출력 루트를 지정할 수 있습니다. [라이선스 안내](LICENSE.txt).
