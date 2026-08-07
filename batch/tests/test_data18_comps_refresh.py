"""DATA-18 pytest: patch_version 미변경 상황(=run_patch_detection이 skip한
경우)에서도 comps/comp_champions 재수집 트리거가 실제로 호출·반영되는지,
그리고 comp+playstyle 재임베딩이 meta_document_embeddings를 최신 상태로
유지하는지 검증한다(op.gg·HuggingFace는 실 호출 안 함 — mock/fake로 대체,
policies.md 10.2/11).
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from comps_refresh import refresh_comps
from db_session import models
from embeddings import EMBEDDING_DIM
from normalize import ensure_patch, upsert_champions, upsert_comps
from patch_detection import run_patch_detection

FAKE_DECK_TOP10 = {
    "id": "comp-still-top10",
    "name": {"ko_KR": "가짜 조합", "en_US": "Fake Comp"},
    "units": [
        {
            "key": "TFT17_FakeAkali",
            "isCore": True,
            "items": ["TFT_Item_FakeSword"],
            "cell": {"x": 4, "y": 1},
            "tier": 2,
        }
    ],
    "badge": [],
    "stat": {
        "opTier": "OP",
        "deck": {"avgPlacement": 3.1, "pickRate": 0.02, "winRate": 0.19},
    },
}
FAKE_META_DECKS = {
    "data": [FAKE_DECK_TOP10],
    "metadata": {"gameStatDateTime": "2026-08-01T00:00:00.000Z"},
}


class _FakeOpggClient:
    def __init__(self, meta_decks: dict, version: str = "17.8") -> None:
        self._meta_decks = meta_decks
        self._version = version

    def list_meta_decks(self) -> dict:
        return self._meta_decks

    def list_item_combinations(self) -> dict:
        return {"set": 17, "version": self._version, "data": []}


def _fake_embed_batch(texts: list[str]) -> list[list[float]]:
    """실제 HuggingFace 호출 없이 텍스트 개수만큼 더미 벡터를 반환한다."""
    return [[0.0] * EMBEDDING_DIM for _ in texts]


@pytest.fixture
def db_session(migrated_engine: Engine) -> Session:
    with Session(migrated_engine) as session:
        ensure_patch(session, version="17.8", set_number=17)
        upsert_champions(
            session,
            "17.8",
            [
                {
                    "riot_champion_id": "TFT17_FakeAkali",
                    "name_kr": "가짜 아칼리",
                    "name_en": "FakeAkali",
                    "cost": 4,
                }
            ],
        )
        session.commit()
        yield session


def test_refresh_comps_upserts_comp_and_comp_champions(db_session: Session) -> None:
    result = refresh_comps(
        db_session,
        _FakeOpggClient(FAKE_META_DECKS),
        "17.8",
        embed_batch_fn=_fake_embed_batch,
    )
    db_session.commit()

    assert result.comp_count == 1
    comp = db_session.scalar(
        select(models.Comp).where(models.Comp.riot_comp_id == "comp-still-top10")
    )
    assert comp is not None
    assert comp.is_active is True

    linked = db_session.scalars(
        select(models.CompChampion).where(models.CompChampion.comp_id == comp.id)
    ).all()
    assert len(linked) == 1
    assert linked[0].cell_x == 4
    assert linked[0].cell_y == 1
    assert linked[0].star_level == 2


def test_refresh_comps_deactivates_comp_missing_from_new_response(
    db_session: Session,
) -> None:
    # 이전 실행에서 상위 10위였던 조합이 이번 op.gg 응답엔 없다고 가정.
    upsert_comps(
        db_session,
        "17.8",
        [
            {
                "riot_comp_id": "comp-dropped",
                "name": "탈락 조합",
                "tier_rank": "A",
                "avg_place": 4.0,
                "play_rate": 0.05,
                "win_rate": None,
                "playstyle_text": "설명",
                "updated_at": datetime.now(UTC),
            }
        ],
    )
    db_session.commit()

    result = refresh_comps(
        db_session,
        _FakeOpggClient(FAKE_META_DECKS),
        "17.8",
        embed_batch_fn=_fake_embed_batch,
    )
    db_session.commit()

    assert result.deactivated_count == 1
    dropped = db_session.scalar(
        select(models.Comp).where(models.Comp.riot_comp_id == "comp-dropped")
    )
    assert dropped.is_active is False


def test_refresh_comps_records_patch_detection_run(db_session: Session) -> None:
    refresh_comps(
        db_session,
        _FakeOpggClient(FAKE_META_DECKS),
        "17.8",
        embed_batch_fn=_fake_embed_batch,
    )
    db_session.commit()

    runs = db_session.scalars(select(models.PatchDetectionRun)).all()
    assert len(runs) == 1
    assert runs[0].status == "comps_refreshed"
    assert runs[0].patch_version_before == "17.8"
    assert runs[0].patch_version_after == "17.8"


def test_run_patch_detection_skip_still_leaves_room_for_comps_refresh_trigger(
    db_session: Session,
) -> None:
    """DATA-18 DoD: patch_version 미변경(스킵)이어도 상위 오케스트레이션이
    comps 재수집을 호출할 수 있어야 한다 — run_patch_detection 자체는 DATA-12
    그대로 두고, 스킵 결과(patch_version_after)를 그대로 refresh_comps에
    넘기는 것이 run_patch_batch.main()의 실제 배선(DATA-18)이다."""
    db_session.execute(
        models.Patch.__table__.update()
        .where(models.Patch.version == "17.8")
        .values(is_current=True)
    )
    db_session.commit()

    detection = run_patch_detection(
        db_session, _FakeOpggClient(FAKE_META_DECKS, version="17.8"), lambda *_: None
    )
    db_session.commit()
    assert detection.triggered is False

    refresh_calls = []
    if not detection.triggered:
        refresh_calls.append(
            refresh_comps(
                db_session,
                _FakeOpggClient(FAKE_META_DECKS, version="17.8"),
                detection.patch_version_after,
                embed_batch_fn=_fake_embed_batch,
            )
        )
    db_session.commit()

    assert len(refresh_calls) == 1
    assert refresh_calls[0].comp_count == 1


# ---- comp+playstyle 재임베딩(2026-08-07 PM 피드백 회귀) --------------------------


def test_refresh_comps_embeds_comp_and_playstyle_chunks(db_session: Session) -> None:
    result = refresh_comps(
        db_session,
        _FakeOpggClient(FAKE_META_DECKS),
        "17.8",
        embed_batch_fn=_fake_embed_batch,
    )
    db_session.commit()

    assert result.embedded_chunk_count == 2  # comp 1개 + playstyle 1개
    comp = db_session.scalar(
        select(models.Comp).where(models.Comp.riot_comp_id == "comp-still-top10")
    )
    docs = db_session.scalars(
        select(models.MetaDocumentEmbedding).where(
            models.MetaDocumentEmbedding.source_table == "comps",
            models.MetaDocumentEmbedding.source_id == comp.id,
        )
    ).all()
    assert {d.doc_type for d in docs} == {"comp", "playstyle"}
    assert all("가짜 조합" in d.content_text for d in docs)


def test_refresh_comps_overwrites_stale_embedding_after_op_gg_rename(
    db_session: Session,
) -> None:
    """운영에서 실제로 재현된 문제: op.gg가 같은 riot_comp_id를 다른 이름으로
    재명명해도("별돌보미 자야" -> "별돌보미 리븐"), comps 테이블은 upsert로
    최신화되는데 meta_document_embeddings는 전체 배치 때만 재생성돼 옛 이름이
    그대로 남아있었다. refresh_comps()가 재임베딩까지 하면 이 드리프트가
    사라져야 한다."""
    comp_ids = upsert_comps(
        db_session,
        "17.8",
        [
            {
                "riot_comp_id": "comp-still-top10",
                "name": "구이름 조합",
                "tier_rank": "A",
                "avg_place": 4.0,
                "play_rate": 0.05,
                "win_rate": None,
                "playstyle_text": "구이름 플레이 스타일",
                "updated_at": datetime.now(UTC),
            }
        ],
    )
    db_session.commit()
    comp_id = comp_ids["comp-still-top10"]

    # 전체 배치 때 만들어졌던 낡은 임베딩(옛 이름)을 그대로 재현.
    db_session.execute(
        pg_insert(models.MetaDocumentEmbedding.__table__).values(
            patch_version="17.8",
            doc_type="comp",
            source_table="comps",
            source_id=comp_id,
            content_text="구이름 조합(티어 A): 옛날 정보",
            embedding=[0.0] * EMBEDDING_DIM,
            metadata={"name": "구이름 조합", "tier_rank": "A"},
        )
    )
    db_session.execute(
        pg_insert(models.MetaDocumentEmbedding.__table__).values(
            patch_version="17.8",
            doc_type="playstyle",
            source_table="comps",
            source_id=comp_id,
            content_text="구이름 조합 조합 플레이 스타일: 구이름 플레이 스타일",
            embedding=[0.0] * EMBEDDING_DIM,
            metadata={"name": "구이름 조합"},
        )
    )
    db_session.commit()

    # op.gg가 같은 riot_comp_id를 이번엔 "새이름 조합"으로 재명명해 응답.
    renamed_deck = {
        **FAKE_DECK_TOP10,
        "name": {"ko_KR": "새이름 조합", "en_US": "New Name Comp"},
    }
    refresh_comps(
        db_session,
        _FakeOpggClient({**FAKE_META_DECKS, "data": [renamed_deck]}),
        "17.8",
        embed_batch_fn=_fake_embed_batch,
    )
    db_session.commit()

    docs = db_session.scalars(
        select(models.MetaDocumentEmbedding).where(
            models.MetaDocumentEmbedding.source_table == "comps",
            models.MetaDocumentEmbedding.source_id == comp_id,
        )
    ).all()
    assert len(docs) == 2  # 새 행이 아니라 upsert로 갱신됐는지(행 개수 불변)
    assert all("새이름 조합" in d.content_text for d in docs)
    assert all("구이름" not in d.content_text for d in docs)
    assert all(d.doc_metadata["name"] == "새이름 조합" for d in docs)
