# SET-18 : 작업결과

- **TASK**: Supabase Data API(PostgREST) 미사용 설정 정리 → 실제로는 Supabase Disk IO 고갈 원인 제거로 확대
- **상태**: 완료(PM 승인 2026-11-01). 문서 변경은 다음 작업 커밋에 포함 예정
- **선행 TASK**: -
- **근거**: 2026-11-01 Supabase "Disk IO Budget 고갈" 경고 메일 재수신(DATA-25 이후), 진행현황.md 2026-11-01 이력
- **변경**: 코드 변경 없음(운영 설정·DB 조작만). 문서: `docs/verification/smoke-tests.md`, `진행현황.md`, `TFT_Hideout_WBS.xlsx`(우선순위·설명 갱신)

## 조사 경과(오판 정정 포함)

1. `pg_stat_database.temp_bytes` 누적 5,209GB(7/24 이후), 실측 하루 약 280GB의 임시 파일 쓰기. 정상 완료 쿼리 통계(pg_stat_statements)엔 2.7GB뿐이었다.
2. **1차 판단(오판)**: 임시 파일 생성과 실패 트랜잭션이 70초 동안 각 3건으로 짝이 맞았고, 둘 다 약 30초 주기라 PostgREST 에러(`schema "pg_pgrst_no_exposed_schemas" does not exist`)를 주범으로 봤다.
   - PostgREST를 정상화하자 실패 트랜잭션은 0이 됐다. 그러나 임시 파일은 계속 생겼다(100초 3개, 230MB). 결국 **두 현상은 주기만 같은 별개 문제**였다.
3. **실제 원인**: 쿼리별 전후 비교 중, `pg_stat_statements` 조회 한 번이 14초 동안 107MB 임시 파일을 쓰는 것을 확인했다.
   - 저장된 쿼리 텍스트가 **101MB**였고, 그중 **100MB가 `INSERT INTO champion_item_builds` 1,556개 항목**(최대 317KB)이었다.
   - DATA-25 이전 배치가 챔피언별 빌드를 행 수가 매번 다른 VALUES 목록으로 넣어서, 문장이 전부 달라 각각 별도 항목으로 저장된 것이다.
   - Supabase 대시보드와 내부 모니터링이 이 뷰를 주기적으로 읽을 때마다 100MB 텍스트를 불러오며 임시 파일을 썼다.
4. 새 항목이 쌓이는 문제는 DATA-25(5,000행 고정 청크)로 이미 실행당 1~2개 수준으로 줄어 있었다. 남은 것은 기존 누적분이었다.

## 조치

| 조치 | 실행 | 비고 |
|---|---|---|
| 빈 스키마 `api` 생성 | 클로드 코드(운영 DB, `COMMENT ON SCHEMA`로 "테이블·함수 두지 말 것" 명시) | `pg_` 접두어는 PostgreSQL 예약어라 에러가 찾는 스키마는 만들 수 없음 |
| Data API Exposed schemas = `api` 단독 | PM(Supabase 대시보드) | `public`·`graphql_public` 노출 금지(아래 보안 참고) |
| `select pg_stat_statements_reset()` | 클로드 코드(PM 승인) | 쿼리 통계 이력만 소실, 데이터·앱 영향 없음(코드에서 pg_stat_statements를 쓰는 곳 없음) |

## 검증

| 항목 | 조치 전 | 조치 후 |
|---|---|---|
| 실패 트랜잭션(PostgREST) | 70초당 3건 | 100초당 0건, PostgREST `LISTEN "pgrst"` 정상 대기 |
| pg_stat_statements 텍스트 | 101MB | 33 bytes |
| 임시 파일 쓰기 | 100초당 3~7개, 230~570MB(하루 약 280GB) | **3분간 0개, 0MB** |
| 운영 API / 키 없는 REST 요청 | 200 / - | 200 / 401 |

## 보안 관련 확인(별도 결정 필요)

- `anon`·`authenticated` 역할이 public 21개 테이블 전부에 SELECT/INSERT/UPDATE/DELETE/TRUNCATE 권한을 갖고 있고, RLS도 미적용이다.
- `public`을 노출하면 공개 키만으로 전체 DB를 읽고 쓰고 지울 수 있다. `graphql_public`의 `graphql()` 함수도 public을 반영하므로 노출하면 안 된다.
- 지금은 노출 경로가 없어 안전하다. 다만 대시보드 실수 한 번으로 유출될 수 있는 구조라, 권한 회수(REVOKE) 보안 강화를 별도 TASK로 검토할 것을 제안한다.

## 남은 관찰 사항

- 실제 Disk IO 회복은 Supabase Disk IO 그래프(일·시간)로 하루 이틀 뒤 확인이 필요하다.
- 정상 쿼리 중에서는 `GET /catalog/items/builds`가 1회당 약 10MB 임시 파일을 쓴다. 패치당 6~7만 행 전체에 window 정렬을 하기 때문이다. 배치에서 챔피언당 상위 10개만 저장하면 해소된다(후속 TASK 후보).
