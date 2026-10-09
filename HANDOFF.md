# HANDOFF — telegram-slack-relay

## 작업 카드

- **목표**: 구독 중인 공개 텔레그램 채널의 새 글을 슬랙 채널 하나로 옮긴다. 맥이 꺼져 있어도 GitHub Actions에서 동작해야 한다.
- **상태**: 운영 중. 공개 레포 `engwoo09/telegram-slack-relay`, 워크플로 활성(10분 cron). 시크릿 `TG_CHANNELS`(1개 채널)와 `SLACK_WEBHOOK_URL` 등록 완료. 슬랙 수신처는 mrmk 워크스페이스의 비공개 채널 `#telegram-relay`.
- **경로**: `/Users/gim-yeong-u/Server/workspace/telegram-slack-relay`
- **다음 행동**: 없음. 채널을 추가할 때는 README의 운영 표를 따른다.
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

- 사용자 채널 로컬 dry-run: 최근 글 2건 파싱 정상(러시아어 본문, 미디어 표시, 해시태그).

- 클라우드 1회차(run 37891266838): 초기화 1건, 전송 0건, 상태 캐시 저장, 60일 비활성 방지 단계 정상.
- 웹후크 값을 잘못 넣은 상태의 실행 2회: `InvalidSchema`로 실패했고, 상태가 앞으로 넘어가지 않아 유실은 없었다. 이후 웹후크 형식을 먼저 확인하는 검사를 추가했다.
- 클라우드 `rewind=1` 실행(run 37892361146): 2건 전송 성공. `#telegram-relay`에 글 2181, 2182가 도착한 것을 확인했다. 로그에는 개수만 찍히고 웹후크는 `***`로 가려진다.

## 미검증

- 실제 새 글이 올라왔을 때 예약 실행으로 도착하는지(다음 새 글이 올라오면 자연히 확인된다)
- 장기 운영: 60일 비활성 방지 단계가 실제로 스케줄을 유지하는지
