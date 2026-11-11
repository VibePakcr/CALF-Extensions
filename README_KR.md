# CALF Extensions

[English](README.md) · [설치 안내](INSTALL_KR.md) · [CALF 다운로드](https://github.com/VibePakcr/CALF/blob/main/DOWNLOADS.md)

**현재 선택 확장은 FFmpeg 하나입니다.** Repository Intelligence는 CALF 하네스 1.8.15와 워크벤치 1.9.11의 기본 기능으로 통합했습니다. 모듈 기록·정확한 원문 조회·CPU 레인과 검사 연결을 사용하기 위해 Repository 팩을 따로 설치할 필요가 없습니다.

## FFmpeg 씬 작업 · 0.2.0-preview.1

고칠 씬만 새 후보로 만들고, 별도 검사로 확인한 뒤 검증된 버전을 선택합니다. 다른 승인 씬과 이전 버전은 그대로 남습니다. 요청 키로 중복을 확인하며, 결과가 불명확한 요청을 무조건 다시 제출하지 않습니다.

확장은 CALF의 공개 작업 규약을 사용하는 **Rust 실행 파일**입니다. CALF와 설치된 FFmpeg·ffprobe가 필요합니다. Python·Node·SDK 실행 환경·로컬 모델·백그라운드 서비스는 필요하지 않습니다. 다른 앱에서 언어별 연결이 필요하면 SDK를 사용할 수 있습니다.

- [설치와 첫 실행](INSTALL_KR.md)
- [명령·제한·복구](native-ffmpeg/README_KR.md)
- [현재 확장 목록](catalog.json)
- [최신 릴리즈 다운로드](https://github.com/VibePakcr/CALF-Extensions/releases/latest)
- [GitLab 릴리즈](https://gitlab.com/vibepackr-group/CALF-Extensions/-/releases)

기술 검사는 확정된 영상 규격과 후보 해시를 확인합니다. 미적 품질을 판단하지 않으며, 채택은 사용자가 명시적으로 선택합니다. 외부 생성 API나 프로바이더 계정을 자동 호출하지 않습니다.

## 소스에서 빌드하기

```sh
cargo build --release --locked --manifest-path native-ffmpeg/Cargo.toml
cargo test --locked --manifest-path native-ffmpeg/Cargo.toml
```

사용 중인 OS와 아키텍처에 맞는 실행 파일을 선택하세요. 릴리즈 검증 보고서에 실제 시험한 플랫폼과 합성 데이터의 범위를 표시합니다. 빌드 성공만으로 실행 검증을 마쳤다고 판단하지 않습니다.

## 이전 작업 보존

Navigator·Video Work Management·모션 실험과 이전 Python 구현은 현재 목록과 패키지에서 제외합니다. 소스와 과거 릴리즈는 [이전 자료](legacy/README.md)로 남습니다. 새 실행 파일을 설치해도 기존 기록·계약·설정·원본 영상·승인 씬 버전을 삭제하거나 자동 이전하지 않습니다.

CALF의 비공개 코어는 별도로 유지합니다. 이 확장은 문서화된 인터페이스만 사용하며 새로운 실행 권한을 부여하지 않습니다. [확장 라이선스](LICENSE-EXTENSIONS.txt).
