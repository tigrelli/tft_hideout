# DATA-25 : 작업결과

- **TASK**: champion_item_builds 디스크 IO 개선(인덱스·일괄 교체·지난 패치 정리)
- **상태**: 완료(PM 승인 2026-10-26, 커밋 `a5846c4`, 브랜치 `task/DATA-25`)
- **선행 TASK**: DATA-10, DATA-13
- **근거**: 2026-10-26 Supabase "Disk IO Budget 고갈" 경고 메일, 진행현황.md 2026-10-26 이력
- **변경 파일**
  - backend: `alembic/versions/202610261200_data25_add_champion_item_builds_patch_champion_index.py`(신규), `db/models.py`(인덱스 선언), `tests/test_data25_migration.py`(신규)
  - batch: `normalize.py`(`replace_champion_item_builds` → `replace_patch_item_builds`, `prune_old_item_builds` 신규), `run_patch_batch.py`(배선, 매일 정리), `tests/test_data10_normalize.py`(기존 1건 → 신규 6건)
  - 문서: `docs/reference/schema.md`, `TFT_Hideout_WBS.xlsx`(DATA-25·DATA-26·CHAT-37·SET-18·SET-19 행), `진행현황.md`

## 원인(운영 DB 읽기 전용 조회)

| 관측 | 값 |
|---|---|
| `champion_item_builds` 누적 삽입·삭제 | 146만 행 · 106만 행(다른 테이블은 수천 행 수준) |
| 인덱스 | PK(id)뿐 |
| 누적 순차 스캔 | 2,010회, 약 5.4억 행 읽음(DB 전체 145MB 대비 비정상) |
| 테이블 크기 / 행 수 | 80MB / 40만 행(17.8~18.5, 깨진 18.1만 13만 행) |
| IO 최다 쿼리(pg_stat_statements) | 챔피언별 `DELETE FROM champion_item_builds WHERE champion_id=? AND patch_version=?` 1,739회 |

10/7부터 HF 402로 패치 승격이 매일 실패하면서, 다음 날 같은 패치를 다시 "새 패치"로 감지해 전체 재수집을 반복했다(CHAT-36으로 해소). 그때마다 챔피언별 DELETE 약 65회가 인덱스 없이 테이블 전체를 스캔했고, 6~7만 행을 다시 넣었다. 반복 재수집은 CHAT-36 머지로 멈췄다. 하지만 인덱스 부재와 누적 데이터는 그대로라 다음 패치 때 같은 비용이 다시 발생한다.

## 구현

1. **인덱스**: `ix_champion_item_builds_patch_champion (patch_version, champion_id)`. 배치 DELETE와 카탈로그 `GET /items/builds`(patch_version + champion_id 조건)가 함께 쓴다.
2. **패치 단위 교체**(`replace_patch_item_builds`): 챔피언별 DELETE 65회를 패치 조건 DELETE 1회로 바꿨다. INSERT는 5,000행 청크로 나눈다. 패치당 6~7만 행을 한 문장에 넣으면 psycopg 파라미터 한도(65,535)를 넘기 때문이다. 이번 응답에 없는 챔피언의 옛 빌드도 함께 지워져 패치 전체가 응답과 일치한다.
3. **지난 패치 정리**(`prune_old_item_builds`): `patches.id`(감지 순서) 기준 최근 2개 패치와 `is_current` 패치를 제외하고 지운다. 실행 시점은 **매일 배치 끝**이다. 승격 성공 때만 돌리면 다음 패치까지 쌓인 행이 남기 때문이다. 실패해도 크론은 계속 돈다.
   - 운영 예상(읽기 전용 계산): 다음 배치에서 **263,309행 삭제**(17.8·17.9·18.1·18.2·18.3), 18.5·18.4의 142,646행은 유지.
   - 화면·챗봇은 현재 패치만 조회한다. 프론트는 `?patch=`를 쓰지 않고, 사후 패인 분석(PGA)은 이 테이블을 쓰지 않는다. 따라서 지난 패치를 지워도 사용자 영향이 없다.

## 자체 검증

```
backend: 473 passed (DATA-25 마이그레이션 테스트 3건 추가 — 인덱스 생성, 패치 DELETE가 인덱스 사용(EXPLAIN), downgrade/upgrade)
batch:   145 passed (기존 replace 테스트 1건 → 패치 교체·타 패치 무영향·청크 경계·빈 입력·최근 2개 보존·현재 패치 보존 6건)
ruff check / ruff format: 클린
```

변이 확인: "현재 패치 보호" 조건 제거, "첫 청크만 삽입" 두 가지로 구현을 망가뜨리자 각각 해당 테스트가 실패했다. 확인 후 원복했다.

## 참고 / 한계

- 첫 정리 실행(26만 행 삭제)은 1회성 쓰기 부하가 생긴다. 배치가 새벽 03:00 KST에 도는 시간대라 영향은 작을 것으로 본다.
- Postgres DELETE는 파일 크기를 바로 줄이지 않는다(autovacuum이 공간을 재사용 가능하게 표시). 80MB 파일이 그대로 보일 수 있지만, 이후 삽입이 그 공간을 재사용해 더 커지지 않는다. 공간을 즉시 반환하려면 `VACUUM FULL champion_item_builds`가 필요한데, 테이블 잠금이 걸리므로 필요할 때만 PM이 직접 실행한다.
- 실제 IO 감소 효과는 Supabase Disk IO 그래프에서 다음 패치 배치 때 확인이 필요하다.

## 배포 시 참고(승인 후)

main 머지 → Render 빌드의 `alembic upgrade head`가 인덱스를 생성한다. 40만 행 기준 수 초 걸리고 그동안 테이블 쓰기가 잠기지만 배치 시간대가 아니면 영향이 없다. 정리는 다음 정기 배치(03:00 KST)에서 자동 실행되며, 바로 보려면 배치를 수동 실행하면 된다.
