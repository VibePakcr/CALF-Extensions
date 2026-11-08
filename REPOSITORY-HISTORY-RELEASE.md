# Repository Pack 0.1.1-preview.4 — local history queries

[English](#english) · [한국어](#한국어)

## English

Read a long CALF journal without loading all of it into the next task. This preview adds a streamed index, recent Markdown notes for explicitly mapped modules, a bounded search for older decisions and an exact-record reader. Shared tasks remain visible in every matching module; unmapped records stay in `unassigned`.

- The original `history.html`, hash chain, contracts and completion rules remain authoritative. Generated notes never count as verification evidence.
- Current status uses the selected native CALF executable. A historical `SATISFIED` entry cannot turn a current `UNKNOWN` into success.
- Python's standard library handles the local queries. No model, network, database or resident process is needed. Git is needed for the separate existing Git inspect mode.
- New boundary tests: 21 passed, zero skipped. Earlier regression evidence covers 24 Git, navigation, limit and compatibility tests. Exact references for 391 retained records were compared with their originals. Native 1.8.8 checks also rejected a damaged chain and returned `UNKNOWN` after a previously checked file changed.
- One measured journal contained 377 records / 848,806 bytes. Its module response was 6,049 bytes; the query read 9,145 bytes of index/notes and no journal body. This is a sample byte measurement, not an LLM-token reduction or a general speed claim. Derived files consume additional disk space.

**Installation:** use the ZIP and SHA256SUMS attached to this release. Stage, check and qualify it with the existing Local Pack Tools, then activate with the current active digest and `--experimental`. Keep the old pack, locks and bindings. For standalone queries, extract the ZIP into a new folder and follow [the English guide](docs/REPOSITORY_HISTORY.md). The older Local Pack Tools download remains available in `packs-v0.1.0-preview.1`.

**Qualification updated 2026-11-08:** the unchanged archive passed 21 history tests each on Windows x64 and Debian x64 with native Harness 1.8.8, in addition to its macOS qualification. Fresh Codex, Antigravity and scoped Claude Code/MCP context results are described in [the follow-up report](docs/REPOSITORY_HISTORY_QUALIFICATION.md). Only supported native v1 journals are indexed. New journal entries require a new index. Search covers IDs, kinds and 160-character excerpts, not full payloads. No Workbench panel, automatic host context injection or new core release is included. Existing release tags and files are retained.

## 한국어

긴 CALF 기록에서 필요한 모듈과 결정만 찾아 읽을 수 있게 했습니다. 기록을 순서대로 읽어 작은 인덱스를 만들고, 지정한 모듈의 최근 기록을 Markdown으로 제공합니다. 오래된 결정 검색과 원본 기록 한 건 조회도 지원합니다. 공통 작업은 해당하는 모듈 모두에 표시하고, 분류하지 못한 기록은 `unassigned`에 남깁니다.

- 원본 `history.html`, 해시 체인, 계약과 완료 판정은 그대로 유지합니다. 생성한 요약은 검증 증거로 쓰지 않습니다.
- 현재 판정은 사용자가 지정한 CALF 실행기로 확인합니다. 과거의 `SATISFIED` 기록으로 현재 `UNKNOWN`을 성공 처리하지 않습니다.
- 조회는 Python 표준 라이브러리만 사용합니다. 모델·네트워크·DB·상주 프로세스가 필요하지 않습니다. 기존 Git 조회 기능의 Git 요건은 별도입니다.
- 새 경계 검사 21개를 건너뜀 없이 통과했습니다. 기존 Git·탐색·상한·호환성 검사 24개의 회귀 근거도 확인했습니다. 실제 기록 참조 391개를 원본과 대조했고, 코어 1.8.8이 손상된 체인을 거절하며 검사 후 파일이 바뀌면 `UNKNOWN`을 반환하는 것도 확인했습니다.
- 기록 377개·848,806바이트 표본에서 모듈 응답은 6,049바이트였습니다. 조회 시 인덱스·요약 9,145바이트만 읽고 원본 본문은 읽지 않았습니다. 이 수치는 해당 표본의 바이트 측정이며 토큰 절약률이나 모든 환경의 속도를 뜻하지 않습니다. 인덱스는 별도 디스크 공간을 사용합니다.

**설치:** 이 릴리즈의 ZIP과 SHA256SUMS를 받으세요. 기존 Local Pack Tools로 stage·check·qualify 후 현재 active digest와 `--experimental`로 선택합니다. 이전 팩·잠금·작업 연결은 보관하세요. 독립 조회는 ZIP을 새 폴더에 풀고 [한국어 안내](docs/REPOSITORY_HISTORY_KR.md)를 따르면 됩니다. 기존 Local Pack Tools는 `packs-v0.1.0-preview.1`에서 계속 받을 수 있습니다.

**2026-11-08 추가 검증:** 같은 ZIP을 유지하면서 macOS에 이어 Windows x64·Debian x64에서도 Harness 1.8.8과 기록 조회 검사 21개를 각각 통과했습니다. Codex·Antigravity·작업 범위를 제한한 Claude Code/MCP 새 세션의 결과는 [추가 검증 안내](docs/REPOSITORY_HISTORY_QUALIFICATION_KR.md)를 참고하세요. 지원되는 네이티브 v1 기록만 읽으며, 기록이 추가되면 새 인덱스를 만들어야 합니다. 검색은 ID·종류·160자 요약을 대상으로 하고 본문 전체를 검색하지 않습니다. Workbench 화면·호스트 자동 문맥 주입·새 코어 릴리즈는 포함하지 않습니다. 기존 릴리즈와 파일은 계속 보관합니다.
