# telegram-slack-relay

공개 텔레그램 채널의 새 글을 슬랙 채널 하나로 옮깁니다. GitHub Actions가 1시간마다(매시 10분) 실행하므로 맥이 꺼져 있어도 동작합니다. GitHub 무료 예약 실행은 몇 시간씩 밀리거나 건너뛸 수 있습니다.

- 텔레그램 로그인 없이 공개 웹 미리보기(`https://t.me/s/<채널>`)만 읽습니다.
- 슬랙은 Incoming Webhook 하나로 받습니다.
- 공개 레포라 실행 로그를 누구나 볼 수 있습니다. 그래서 로그에는 개수만 남고 채널 이름이나 본문은 남지 않습니다.

## 처음 설정

1. **슬랙 웹후크 만들기**: [api.slack.com/apps](https://api.slack.com/apps)에서 Create New App → From scratch로 앱을 만들고, Incoming Webhooks를 켠 뒤 "Add New Webhook to Workspace"에서 받을 채널을 고릅니다. 만들어진 주소는 채팅이나 문서에 붙여넣지 마세요.
2. **시크릿 등록** (이 폴더에서 실행):

   ```bash
   gh secret set SLACK_WEBHOOK_URL      # 프롬프트에 웹후크 주소 붙여넣기
   gh secret set TG_CHANNELS            # 예: channel_a,channel_b
   ```

   `TG_CHANNELS`에는 `@아이디`, `아이디`, `https://t.me/아이디` 형태를 쉼표로 섞어 써도 됩니다.
3. **첫 실행**: `gh workflow run relay.yml`. 첫 실행은 채널마다 최신 글 번호만 기록하고 슬랙에는 보내지 않습니다. 그다음부터 새 글만 전송합니다.

## 운영

| 하고 싶은 일 | 방법 |
| --- | --- |
| 채널 추가/삭제 | `gh secret set TG_CHANNELS`로 목록 전체를 다시 입력합니다. 새 채널은 다음 실행 때 기록만 되고, 그 이후 글부터 전송됩니다. |
| 슬랙 채널 변경, 웹후크 재발급 | 슬랙 앱에서 새 웹후크를 만든 뒤 `gh secret set SLACK_WEBHOOK_URL` |
| 상태 초기화 | `gh cache list`로 `relay-state-*`를 확인하고 `gh cache delete --all`로 지웁니다. 다음 실행은 첫 실행처럼 기록만 합니다. |
| 즉시 한 번 실행 | `gh workflow run relay.yml` |
| 전송 시험 (마지막 N건 다시 보내기) | `gh workflow run relay.yml -f rewind=1` |
| 최근 실행 확인 | `gh run list --workflow relay.yml --limit 5` |
| 일시 중지/재개 | `gh workflow disable relay.yml` / `gh workflow enable relay.yml` |

## 로컬 확인

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python relay.py --dry-run --channels "@채널아이디"
```

`--dry-run`은 슬랙에 보내지 않고 상태도 저장하지 않습니다. 상태가 없는 채널은 최근 글 몇 개(`--show`, 기본 3개)를 미리 보여줍니다. 본문이 공개 로그에 찍히지 않도록 GitHub Actions 안에서는 실행되지 않게 막혀 있습니다.

## 동작 규칙

- 슬랙 메시지 형식: `*[채널 제목]*`, 원문 본문 전체(잘라내지 않음), `원문: https://t.me/<채널>/<번호>`, ``게시물 ID: `<채널>/<번호>` ``. 번역은 이 레포가 하지 않고, ChatGPT 예약 작업이 `#telegram-relay`를 읽어서 처리합니다.
- 채널별 마지막 글 번호는 `actions/cache`의 `state.json`에 보관합니다. 커밋하지 않습니다. 글을 하나 보낼 때마다 바로 저장하므로, 실행이 중간에 끊겨도 이미 보낸 글을 다시 보내지 않습니다.
- `rewind` 시험 실행은 일부러 같은 글을 다시 보냅니다. 평소에는 쓰지 않습니다.
- 한 번에 20개 넘게 밀렸으면 `?before=`로 이전 페이지를 최대 5페이지까지 더 읽습니다.
- 슬랙 전송에 성공한 글까지만 상태가 갱신되므로, 실패한 글은 다음 회차에 다시 시도합니다.
- 상태가 없는 채널은 기록만 하고 보내지 않습니다. 캐시가 사라지면 그 사이에 올라온 글은 빠질 수 있습니다.
- 슬랙 전송이 실패했거나 모든 채널 읽기가 실패하면 워크플로가 실패로 표시됩니다.

## 한계

- GitHub 예약 실행은 몰리는 시간에 10~30분까지 늦어질 수 있습니다.
- 운영자가 웹 미리보기를 꺼둔 채널이나 비공개 채널은 읽을 수 없습니다. 그런 채널은 계정 로그인 방식(Telethon)이 따로 필요합니다.
- 사진·영상은 옮기지 않고 원문 링크로 대신합니다.
