"""GitHub Actions가 실행하는 배치 진입점(DATA-14).

DATA-12(패치 감지) -> 변경 있으면 DATA-08(op.gg)/DATA-09(Community Dragon) 수집 ->
DATA-10(정규화) -> DATA-11(임베딩) -> DATA-13(원자적 전환)을 순서대로 잇는다.
개별 단계 함수는 전부 이미 pytest로 검증돼 있으므로, 이 파일은 배선(glue)만
담당하고 별도 로직을 추가하지 않는다.

주의: 아직 GitHub Actions 워크플로우의 `schedule` 트리거는 켜지 않았다(PM 결정,
2026-08-04) — `workflow_dispatch`(수동 실행)로만 동작한다. 매시간 자동 실행은
PM이 수동 실행으로 먼저 검증한 뒤 별도로 켜기로 함.
"""

from __future__ import annotations

import os
import sys

from cache_cleanup import delete_stale_chat_answer_cache
from comps_refresh import refresh_comps
from db_session import create_session
from embeddings import HuggingFaceEmbeddingClient, collect_chunks, upsert_embeddings
from id_name_mapping import CommunityDragonClient, build_name_maps
from normalize import (
    augment_rows,
    champion_item_build_rows,
    champion_rows,
    comp_champion_rows,
    comp_rows,
    comp_trait_rows,
    ensure_patch,
    item_rows,
    mark_stale_comps_inactive,
    replace_champion_item_builds,
    trait_rows,
    upsert_augments,
    upsert_champions,
    upsert_comp_champions,
    upsert_comp_traits,
    upsert_comps,
    upsert_items,
    upsert_traits,
    validate_champion_collection,
)
from opgg_client import OpggMcpClient
from patch_detection import run_patch_detection
from patch_transition import BatchStep, run_batch_with_atomic_promotion

# 무료 티어 호출량을 고려해 임베딩은 패치 변경분 전체가 아니라 상한을 두고 처리한다.
# 나머지는 다음 실행(다음 시간) 때 이어서 처리되도록 doc_type별 upsert가 이미
# 멱등적이라 여러 번 나눠 돌려도 안전하다(DATA-11 결정).
MAX_CHUNKS_PER_RUN = int(os.environ.get("MAX_EMBED_CHUNKS_PER_RUN", "500"))


def _build_steps(session, set_number: int, state: dict) -> list[BatchStep]:
    def step_collect() -> None:
        with CommunityDragonClient() as cd:
            state["cdragon_ko"] = cd.fetch_tft_data(lang="ko_kr")
            state["cdragon_en"] = cd.fetch_tft_data(lang="en_us")
        with OpggMcpClient() as opgg:
            state["items_ko"] = opgg.list_item_combinations(lang="ko_KR")
            state["items_en"] = opgg.list_item_combinations(lang="en_US")
            state["augments_ko"] = opgg.list_augments(lang="ko_KR")
            state["augments_en"] = opgg.list_augments(lang="en_US")
            state["meta_decks"] = opgg.list_meta_decks()
            # tft_get_champion_item_build은 챔피언 1명당 1회 호출해야 하는 도구라
            # (DATA-05 스파이크) cdragon에서 이미 확인한 챔피언 목록을 순회한다.
            champions = champion_rows(
                state["cdragon_ko"], state["cdragon_en"], set_number
            )
            validate_champion_collection(champions, set_number)
            state["item_builds_by_champion"] = {
                c["riot_champion_id"]: opgg.get_champion_item_build(
                    c["riot_champion_id"]
                )
                for c in champions
            }

    def step_normalize() -> None:
        patch_version = state["patch_version"]
        champion_ids = upsert_champions(
            session,
            patch_version,
            champion_rows(state["cdragon_ko"], state["cdragon_en"], set_number),
        )
        trait_ids = upsert_traits(
            session,
            patch_version,
            trait_rows(state["cdragon_ko"], state["cdragon_en"], set_number),
        )
        upsert_items(
            session,
            patch_version,
            item_rows(state["items_ko"], state["items_en"], state["cdragon_ko"]),
        )
        upsert_augments(
            session,
            patch_version,
            augment_rows(state["augments_ko"], state["augments_en"]),
        )
        for riot_champion_id, build_response in state[
            "item_builds_by_champion"
        ].items():
            db_champion_id = champion_ids.get(riot_champion_id)
            if db_champion_id is not None:
                replace_champion_item_builds(
                    session,
                    db_champion_id,
                    patch_version,
                    champion_item_build_rows(build_response),
                )
        name_maps = build_name_maps(state["cdragon_ko"], set_number)
        comp_ids = upsert_comps(
            session, patch_version, comp_rows(state["meta_decks"], name_maps.champions)
        )
        # DATA-17: 이번 배치 op.gg 응답에 없는(메타 회전으로 상위 10위 밖으로
        # 밀려난) 기존 조합은 소프트 삭제한다.
        mark_stale_comps_inactive(session, patch_version, set(comp_ids.keys()))
        session.flush()
        for deck in state["meta_decks"]["data"]:
            comp_id = comp_ids.get(deck["id"])
            if comp_id is not None:
                upsert_comp_champions(
                    session, comp_id, comp_champion_rows(deck), champion_ids
                )
                upsert_comp_traits(session, comp_id, comp_trait_rows(deck), trait_ids)

    def step_embed() -> None:
        chunks = collect_chunks(session, state["patch_version"])[:MAX_CHUNKS_PER_RUN]
        if not chunks:
            return
        hf_key = os.environ["HUGGINGFACE_API_KEY"]
        with HuggingFaceEmbeddingClient(api_key=hf_key) as client:
            vectors = client.embed_batch([c["content_text"] for c in chunks])
        upsert_embeddings(session, state["patch_version"], chunks, vectors)

    return [
        BatchStep("collect", step_collect),
        BatchStep("normalize", step_normalize),
        BatchStep("embed", step_embed),
    ]


def main() -> int:
    session = create_session()
    state: dict = {}

    def on_trigger(before: str | None, after: str) -> None:
        state["patch_version"] = after
        with OpggMcpClient() as opgg:
            set_number = opgg.list_item_combinations().get("set")
        ensure_patch(session, after, int(set_number))
        session.commit()

        result = run_batch_with_atomic_promotion(
            session, after, _build_steps(session, int(set_number), state)
        )
        if result.success:
            deleted = delete_stale_chat_answer_cache(session, after)
            print(f"캐시 정리(DATA-15): chat_answer_cache {deleted}행 삭제")
        session.commit()
        print(
            f"배치 실행 결과: success={result.success} failed_step={result.failed_step}"
        )

    with OpggMcpClient() as opgg:
        detection = run_patch_detection(session, opgg, on_trigger)
    session.commit()
    print(
        f"패치 감지: triggered={detection.triggered} {detection.patch_version_before} -> {detection.patch_version_after}"
    )

    if not detection.triggered:
        # DATA-18: patch_version이 안 바뀌어 전체 배치(step_normalize)가 돌지
        # 않은 경우에도, 같은 크론 안에서 comps/comp_champions만이라도 op.gg
        # 최신 메타 조합으로 갱신한다(FE-05·DATA-17에서 겪은 "패치 미변경 시
        # 메타 회전이 반영 안 되는" 구조적 공백 재발 방지). op.gg 호출 실패 등은
        # 배치 크론 전체를 죽이지 않고 로그로만 알린다(patch_transition.py와
        # 동일한 방침).
        try:
            with OpggMcpClient() as opgg:
                refresh = refresh_comps(session, opgg, detection.patch_version_after)
            session.commit()
            print(
                f"comps 주기 재수집(DATA-18): comp_count={refresh.comp_count} "
                f"deactivated={refresh.deactivated_count} "
                f"embedded_chunks={refresh.embedded_chunk_count}"
            )
        except Exception as exc:  # noqa: BLE001 - 배치 크론을 죽이지 않고 로그로만 알림
            session.rollback()
            print(f"comps 주기 재수집(DATA-18) 실패: {exc}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
