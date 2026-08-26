"""TEST-05: 배치 파이프라인 통합 테스트 — 패치감지(DATA-12)→수집(DATA-08/09)→
정규화(DATA-10)→임베딩(DATA-11)→원자적전환(DATA-13) end-to-end, DoD "정상/중간실패
시나리오 모두 검증".

DATA-08~15는 각자 자기 단계만 단위 테스트한다. `run_patch_batch.py`가 이 단계들을
실제로 잇긴 하지만, `step_collect`/`step_embed` 내부에서 진짜 op.gg MCP·Community
Dragon·HuggingFace 클라이언트를 직접 생성해 호출하므로 자동화 테스트에서 그대로
쓸 수 없다(policies.md 10.2 — 외부 API 실호출 금지). 이 파일은 `run_patch_batch.py`의
`_build_steps()`와 같은 모양으로, 외부 I/O 경계(op.gg/cdragon 수집 결과, HuggingFace
임베딩 벡터)만 고정 fixture/fake로 바꾸고 나머지(정규화·임베딩 DB 반영·원자적 전환)는
전부 실제 구현을 그대로 실행한다.

DATA-13 자신의 테스트(test_data13_patch_transition.py)가 이미 BatchStep 오케스트레이션
자체(성공/중간실패)는 촘촘히 검증하지만 손으로 만든 fake 스텝(`lambda: None`,
가짜 Champion 1개 직접 add)만 쓴다 — 여기서는 실제 normalize.py/embeddings.py 함수를
그대로 호출해 "실제 정규화·임베딩 결과물"이 원자적 전환과 맞물려도 똑같이 동작하는지
확인한다.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from db_session import models
from embeddings import EMBEDDING_DIM, collect_chunks, upsert_embeddings
from id_name_mapping import build_name_maps
from normalize import (
    augment_rows,
    champion_rows,
    comp_champion_rows,
    comp_rows,
    ensure_patch,
    item_rows,
    trait_rows,
    upsert_augments,
    upsert_champions,
    upsert_comp_champions,
    upsert_comps,
    upsert_items,
    upsert_traits,
)
from patch_transition import BatchStep, run_batch_with_atomic_promotion

# ---- 합성 fixture(test_data10_normalize.py와 동일 구조, 값은 전부 가짜) ----------

CDRAGON_KO = {
    "items": [
        {
            "apiName": "TFT_Item_FakeSword",
            "icon": "ASSETS/Maps/TFT/Icons/Items/Hexcore/TFT_Item_FakeSword.tex",
        }
    ],
    "setData": [
        {
            "number": 17,
            "mutator": "TFTSet17",
            "champions": [
                {
                    "apiName": "TFT17_FakeAkali",
                    "name": "가짜 아칼리",
                    "cost": 4,
                    "squareIcon": "ASSETS/Characters/TFT17_FakeAkali/Icon.tex",
                    "traits": ["가짜 특성"],
                }
            ],
            "traits": [
                {
                    "apiName": "TFT17_FakeTrait",
                    "name": "가짜 특성",
                    "effects": [{"minUnits": 1, "maxUnits": 3, "style": 1}],
                }
            ],
        }
    ],
}
CDRAGON_EN = {
    "setData": [
        {
            "number": 17,
            "mutator": "TFTSet17",
            "champions": [
                {"apiName": "TFT17_FakeAkali", "name": "FakeAkali", "cost": 4}
            ],
            "traits": [
                {"apiName": "TFT17_FakeTrait", "name": "FakeTrait", "effects": []}
            ],
        }
    ]
}
ITEMS_KO = {
    "data": [
        {
            "apiName": "TFT_Item_FakeSword",
            "name": "가짜 검",
            "category": "core",
            "composition": [],
            "effects": {"AP": 10},
            "desc": "공격력이 증가합니다.",
        }
    ]
}
ITEMS_EN = {"data": [{"apiName": "TFT_Item_FakeSword", "name": "Fake Sword"}]}
AUGMENTS_KO = {
    "headers": ["apiName", "desc", "name", "tier", "imageUrl"],
    "rows": [
        ["TFT17_Augment_Fake", "가짜 설명", "가짜 증강체", "gold", "https://x.invalid"]
    ],
}
AUGMENTS_EN = {
    "headers": ["apiName", "desc", "name", "tier", "imageUrl"],
    "rows": [
        ["TFT17_Augment_Fake", "fake desc", "Fake Augment", "gold", "https://x.invalid"]
    ],
}
FAKE_DECK = {
    "id": "fake-origin-hash-1",
    "name": {"ko_KR": "가짜 조합", "en_US": "Fake Comp"},
    "units": [
        {
            "key": "TFT17_FakeAkali",
            "isCore": True,
            "items": ["TFT_Item_FakeSword"],
            "cell": {"x": 4, "y": 1},
            "tier": 3,
        }
    ],
    "badge": [{"key": "difficulty", "value": 2}],
    "stat": {
        "opTier": "S",
        "deck": {"avgPlacement": 3.1, "pickRate": 0.02, "winRate": 0.19},
    },
}
FAKE_META_DECKS = {
    "data": [FAKE_DECK],
    "metadata": {"gameStatDateTime": "2026-08-01T00:00:00.000Z"},
}

SET_NUMBER = 17
NEW_PATCH = "17.9"
OLD_PATCH = "17.8"


def _real_normalize_step(session: Session, patch_version: str) -> None:
    """run_patch_batch.py의 step_normalize와 동일한 순서로 실제 upsert 함수를
    호출한다(collect 단계는 고정 fixture로 이미 "수집됐다"고 가정)."""
    champion_ids = upsert_champions(
        session, patch_version, champion_rows(CDRAGON_KO, CDRAGON_EN, SET_NUMBER)
    )
    upsert_traits(
        session, patch_version, trait_rows(CDRAGON_KO, CDRAGON_EN, SET_NUMBER)
    )
    upsert_items(session, patch_version, item_rows(ITEMS_KO, ITEMS_EN, CDRAGON_KO))
    upsert_augments(session, patch_version, augment_rows(AUGMENTS_KO, AUGMENTS_EN))

    name_maps = build_name_maps(CDRAGON_KO, SET_NUMBER)
    comp_ids = upsert_comps(
        session, patch_version, comp_rows(FAKE_META_DECKS, name_maps.champions)
    )
    session.flush()
    for deck in FAKE_META_DECKS["data"]:
        comp_id = comp_ids.get(deck["id"])
        if comp_id is not None:
            upsert_comp_champions(
                session, comp_id, comp_champion_rows(deck), champion_ids
            )


def _real_embed_step(
    session: Session, patch_version: str, *, should_fail: bool
) -> None:
    """run_patch_batch.py의 step_embed와 동일하게 collect_chunks(실제 DB 조회) +
    upsert_embeddings(실제 upsert)를 쓰되, HuggingFace 호출 자리만 고정 벡터로
    대체한다. should_fail=True면 임베딩 API 실패(예: 무료 티어 한도 초과)를
    흉내내 중간실패 시나리오를 재현한다."""
    if should_fail:
        raise RuntimeError("HuggingFace 임베딩 API 실패(mock)")
    chunks = collect_chunks(session, patch_version)
    if not chunks:
        return
    vectors = [[0.1] * EMBEDDING_DIM for _ in chunks]
    upsert_embeddings(session, patch_version, chunks, vectors)


@pytest.fixture
def db_session(migrated_engine: Engine) -> Session:
    with Session(migrated_engine) as session:
        session.add(
            models.Patch(
                version=OLD_PATCH,
                set_number=SET_NUMBER,
                released_at=datetime(2026, 1, 1, tzinfo=UTC),
                is_current=True,
                detected_at=datetime(2026, 1, 1, tzinfo=UTC),
            )
        )
        session.commit()
        yield session


def _current_version(session: Session) -> str | None:
    return session.scalar(
        select(models.Patch.version).where(models.Patch.is_current.is_(True))
    )


# ---- 정상 시나리오: 패치감지→수집→정규화→임베딩→원자적전환 전체 성공 -----------------


def test_normal_scenario_full_chain_promotes_patch_with_real_data(
    db_session: Session,
) -> None:
    ensure_patch(db_session, NEW_PATCH, SET_NUMBER)
    db_session.commit()

    steps = [
        BatchStep("normalize", lambda: _real_normalize_step(db_session, NEW_PATCH)),
        BatchStep(
            "embed",
            lambda: _real_embed_step(db_session, NEW_PATCH, should_fail=False),
        ),
    ]
    result = run_batch_with_atomic_promotion(db_session, NEW_PATCH, steps)
    db_session.commit()

    assert result.success is True
    assert _current_version(db_session) == NEW_PATCH

    champion = db_session.scalar(
        select(models.Champion).where(
            models.Champion.riot_champion_id == "TFT17_FakeAkali",
            models.Champion.patch_version == NEW_PATCH,
        )
    )
    assert champion is not None and champion.name_kr == "가짜 아칼리"

    comp = db_session.scalar(
        select(models.Comp).where(models.Comp.patch_version == NEW_PATCH)
    )
    assert comp is not None and comp.name == "가짜 조합"

    embeddings = db_session.scalars(
        select(models.MetaDocumentEmbedding).where(
            models.MetaDocumentEmbedding.patch_version == NEW_PATCH
        )
    ).all()
    assert len(embeddings) > 0
    assert {e.doc_type for e in embeddings} >= {"comp", "playstyle"}


# ---- 중간실패 시나리오: 정규화까지는 실제로 커밋되지만 임베딩 실패 -----------------


def test_mid_failure_scenario_normalize_persists_but_patch_stays_old(
    db_session: Session,
) -> None:
    ensure_patch(db_session, NEW_PATCH, SET_NUMBER)
    db_session.commit()

    steps = [
        BatchStep("normalize", lambda: _real_normalize_step(db_session, NEW_PATCH)),
        BatchStep(
            "embed",
            lambda: _real_embed_step(db_session, NEW_PATCH, should_fail=True),
        ),
    ]
    result = run_batch_with_atomic_promotion(db_session, NEW_PATCH, steps)
    db_session.commit()

    assert result.success is False
    assert result.failed_step == "embed"
    # 원자적 전환(DATA-13)이 실패해 이전 패치가 그대로 유지된다.
    assert _current_version(db_session) == OLD_PATCH

    # 정규화(DATA-10) 단계는 임베딩 실패 이전에 이미 실행·커밋됐으므로, 새
    # patch_version으로 태깅된 실제 데이터는 DB에 남아있다(patch_transition.py
    # docstring에 명시된 의도된 동작 — "이건 정상이다").
    comp = db_session.scalar(
        select(models.Comp).where(models.Comp.patch_version == NEW_PATCH)
    )
    assert comp is not None

    # 반면 임베딩(DATA-11)은 실행되지 못했으므로 새 패치용 문서는 전혀 없다 —
    # is_current가 여전히 이전 패치를 가리키므로 챗봇(CHAT-02)이 반쯤 완성된
    # 새 패치 데이터를 검색해 답하는 사고는 일어나지 않는다.
    new_patch_embeddings = db_session.scalars(
        select(models.MetaDocumentEmbedding).where(
            models.MetaDocumentEmbedding.patch_version == NEW_PATCH
        )
    ).all()
    assert new_patch_embeddings == []

    run_log = db_session.scalar(
        select(models.PatchDetectionRun).where(
            models.PatchDetectionRun.patch_version_after == NEW_PATCH
        )
    )
    assert run_log is not None
    assert run_log.status == "failed"
