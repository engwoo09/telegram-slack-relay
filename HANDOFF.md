# HANDOFF — telegram-slack-relay

## 작업 카드

- **목표**: 구독 중인 공개 텔레그램 채널의 새 글을 슬랙 채널 하나로 옮긴다. 맥이 꺼져 있어도 GitHub Actions에서 동작해야 한다.
- **상태**: 코드와 워크플로 작성 완료. 공개 GitHub 레포 `engwoo09/telegram-slack-relay`에 올림. 시크릿 등록과 클라우드 첫 실행은 아래 검증 결과를 본다.
- **경로**: `/Users/gim-yeong-u/Server/workspace/telegram-slack-relay`
- **다음 행동**: 아래 "미검증"에 남은 항목을 하나씩 처리한다.
- **금지사항**
  - 웹후크 주소, 채널 목록, 메시지 본문을 커밋하거나 로그에 출력하지 않는다(공개 레포라 로그도 공개된다).
  - GitHub Actions 안에서 `--dry-run`을 실행하지 않는다.
  - 텔레그램 계정 세션(Telethon 등)을 이 공개 레포에 넣지 않는다. 필요해지면 비공개 레포로 따로 만든다.
  - 맥 LaunchAgent로 되돌리지 않는다.

## 변경 파일

- `relay.py` — 미리보기 파싱, 상태 비교, 슬랙 전송, `--dry-run`
- `requirements.txt`, `.gitignore`
- `.github/workflows/relay.yml` — 10분 cron, cache 상태, 60일 비활성 방지
- `README.md`, `HANDOFF.md`

## 검증 결과

- 로컬 dry-run(`@telegram`, `@durov`): 파싱, 슬랙 서식(굵게, 링크, 이모지), 이전 페이지 이어 읽기(425→460, 34건), 없는 채널을 읽기 실패로 처리(exit 1), Actions 안에서 dry-run 차단(exit 2)을 확인했다.

## 미검증

- 사용자 채널로 로컬 dry-run
- 시크릿 `SLACK_WEBHOOK_URL`, `TG_CHANNELS` 등록(사용자가 직접)
- `workflow_dispatch` 1회차: 초기화만, 슬랙 0건
- 2회차 이후: 실제 슬랙 도착, 로그에 개수만 찍히는지
