# H5 공개 저장소·데스크톱 검증

[English](REPOSITORY_HOSTED_H5.md) · [계획](REPOSITORY_HOSTED_PLAN_KR.md) · [검증 근거](verification/repository-hosted-h5-20261107.json)

2026-11-07 · 공개 저장소 탐색 경로와 고정한 데스크톱 후보를 검증했습니다. 비공개 접근과 전체 provider·플랫폼 행렬은 아직 미완료입니다. 탐색 검증이며 릴리즈·CALF 실행 권한을 만들지 않습니다.

## 후보와 수정

r1은 검증 전에 H0–H4와 기존 패키지 파일의 해시를 고정했습니다. 실제 GitHub 원문에서 오프라인 렌더링 결함이 드러났습니다. 원문에 있는 `/*BOOTSTRAP*/`, `/*STYLE*/`, `/*SCRIPT*/`가 뒤이어 수행한 템플릿 치환에 걸려, 내보낸 bootstrap의 JSON·JavaScript가 깨졌습니다.

이제 원래 템플릿의 슬롯을 한 번만 치환합니다. 삽입한 원문·asset 내용은 그대로 유지합니다. 세 표식·script 종료 문자열·한글·Unicode 줄 구분자의 왕복 회귀를 추가했습니다. r2에 렌더러 수정, r3에 실제 Windows 시험의 이식성 보완을 기록했고 이전 후보·실패는 보존합니다.

Windows 제어문자 경로는 체크아웃이나 index 보호 해제 없이 native Git tree 객체로 구성하며 동일한 바이트 검사를 유지합니다. 보존 CLI 시험의 Windows `TerminateProcess` 정리는 콘솔 Ctrl+C 정상 종료 근거와 구분합니다. 제품 provider reader·분석·원문 보존·비교 코드는 H4와 같습니다.

최종 r3 manifest SHA256:

```text
b0e5dadc9e0e4f18f68e228f12f09ff849f3644d086b8eda6f0b44cc71772943
```

## 실제 공개 저장소 검증

| 경로 | 실제 검증 범위 |
| --- | --- |
| GitHub 익명 HTTP | API 한도 소진을 부분 수집으로 보존하고 완료 지도로 활성화하지 않음 |
| GitHub `gh` CLI | CLI의 기존 로그인을 사용하며 토큰 추출·저장 없음. 오른쪽/왼쪽 56/29파일 전체 목록과 85개 원문을 같은 commit의 독립 로컬 Git과 대조 |
| GitLab 익명 HTTP | 오른쪽/왼쪽 32/34파일 전체 목록, native Git blob 검사 66개. 독립 보존 로컬 Git과 같은 경로·blob 26/15개를 대조 |

GitHub commit은 `66bdf4a6e8d19ec87b4a10b9e541f1fe3870dc02`, `620447ca5dab2020e19221cda363e9c2b36d1048`입니다. GitLab commit은 `814b6c27fe9ac68ad3f9bb6db7fe2e8ba95f65d1`, `01370f6ad5de62709afd70b4d9a431c95509c6e8`입니다. GitLab API 계약에는 root tree OID가 없으며 같은 commit의 로컬 전체 목록 동등성까지 확인한 것은 아닙니다.

실제 Chrome에서 수동 등록·신원 확인·branch 고정·지도·하단 코드/직접 Diff·고정 provider 링크·에디터 보존 사본 URI·탐색 복원을 확인했습니다. 렌더러 수정 뒤에는 같은 실제 보존 입력을 최종 렌더러에 재생하고 HTTP 차단 상태에서 내보냈으며 원문이 정확히 왕복했습니다. 렌더링 근거를 다시 만들기 위해 provider 읽기를 반복하지 않았습니다.

소유자 지시에 따라 변경하지 않은 GitHub reader에 **검증 전용 고정 endpoint 전송**을 연결해 `gh`를 사용했습니다. 제품에 `gh` 인증 adapter나 계정 자동 연결을 추가한 것은 아닙니다. 기본 HTTP·인증 참조 동작은 그대로이며 CLI 성공으로 익명 한도 결과를 덮지 않습니다.

## 데스크톱·패키지·측정

| 환경 | 최종 후보 결과 |
| --- | --- |
| macOS / Python 3.12 | repository 123개 통과. 실제 Chrome 공개·보존·오프라인과 독립 Local Git/v1 회귀 |
| debian-work / Python 3.13.5 / Git 2.47.3 | 123개 통과. 실제 Chrome 공통 GitHub·GitLab fixture 화면과 오프라인 |
| packr-win / Python 3.12.10 / Git 2.55 | 123개 실행 중 121개 통과·명시적 제외 2개. 실제 Edge 공통 fixture 화면과 오프라인 |

Windows에서는 native OpenSSL이 없는 부정 TLS fixture와 POSIX 전용 실행 파일 fixture를 제외로 유지했습니다. 이를 통과로 바꾸지 않습니다. macOS의 실제 provider 읽기와 다른 OS의 Git 기반 합성 provider 응답을 구분합니다. 한·영, 1440/390/320 폭, 하단 코드·Diff, 늦은 응답 격리와 보존 사본 URI를 확인했습니다. 별도 데스크톱 제스처 검사는 코드 스크롤·핀치 에뮬레이션·휠 확대·키보드 이동을 포함하며 실제 모바일 기기 시험은 아닙니다.

새 T9 가상환경에서 시험용 wheel을 빌드·설치해 assets·schemas·`calf-repo`를 확인했습니다. 네트워크 차단·SDK 부재 상태에서 설치한 Local Git가 작동하고 core·model을 import하지 않습니다. 빌드 의존성은 새 빌드 환경에만 고정 설치했으며 소유자·시스템 도구 Home에 설치하거나 게시하지 않았습니다. 동일한 SHA256의 wheel을 macOS·Debian·Windows의 새 환경에 설치했습니다. 원격은 기존 Python/venv 도구를 사용한 오프라인 설치이며 소스 실행 브라우저 검증과 구분합니다. 기존 FFmpeg 계약도 3개 통과했습니다.

301파일·서로 다른 원문 5개의 합성 fixture에서 초기 진행 약 0.0002초, cold 수집·분석 약 0.24초, 보존 context/payload 열기 약 0.023초, 취소 정리 0.001초 미만, 서비스 최대 RSS 약 40MiB를 측정했습니다. 이 fixture에서 서비스 목표를 충족했습니다. 실제 공개 보존 포털의 브라우저 재열기 수치는 JSON 기록을 따릅니다. 외부 provider 지연·브라우저 전체 메모리·훨씬 큰 부하까지 이 수치로 검증한 것은 아닙니다.

## 보존과 남은 범위

최종 기록에 소스·후보·보조기 해시, 실제 요청 감사, 바이트 검사, 플랫폼 영수증, 제외 검사, 측정 범위와 정리를 연결합니다. H0–H4 기록과 v1·FFmpeg·CALF 자산을 보존합니다. 보호 파일 607개와 H0–H4 역사 파일 15개의 기준 해시가 모두 일치했습니다. 설정을 복구·덮어쓰기하지 않았습니다.

미검증: 명시적으로 허용한 비공개 fixture·권한, Enterprise/Self-Managed, Windows/Linux의 실제 공개 저장소 읽기, 외부 에디터 실행, 실제 모바일 기기, Windows 콘솔 정상 중단, 넓은 성능·메모리 범위. HG01–HG32 전체 행렬을 완료로 선언하지 않고 H5 범위별 결과를 별도로 기록합니다. 저장소 커밋·push, provider 쓰기, webhook·CI 기동이나 조사한 프로젝트 코드 실행은 포함하지 않습니다.

다른 작업의 README 동시 변경과 새 pack 검증 모듈 추가는 그대로 보존하고 이번 고정 탐색 후보에서 제외했습니다.

