"""CHAT-02 pytest(WBS 테스트 요구사항: 의도별 SQL 필터 조건 반영 여부,
top-k 결과 병합 확인).

CHAT-36(2026-10-18): 검색이 pgvector 코사인 거리에서 pg_trgm 텍스트 유사도로
바뀌어(HF 무료 크레딧 폐지), 기존 벡터 기반 테스트를 같은 의도의 텍스트 기반
테스트로 옮겼다 — "질의 벡터와 가까움/멂"은 "질의에 문서 이름이 있음/없음"으로
표현한다. 시드 문서는 실제 배치처럼 embedding 없이(NULL) 넣는다."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import insert
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from db.models import Champion, MetaDocumentEmbedding, Patch
from services.hybrid_search import (
    ITEM_BUILD_PER_CHAMPION_LIMIT,
    filter_by_name_overlap,
    hybrid_search,
    lookup_item_builds_by_champion_ids,
)
from services.intent_classification import (
    INTENT_AUGMENT_RECOMMENDATION,
    INTENT_COMP_RECOMMENDATION,
    INTENT_GENERAL_STRATEGY,
    INTENT_ITEM_RECOMMENDATION,
)


def _add_doc(
    session: Session,
    doc_type: str,
    source_id: int,
    content_text: str,
    metadata: dict[str, Any],
    patch_version: str = "17.8",
) -> None:
    session.execute(
        insert(MetaDocumentEmbedding).values(
            patch_version=patch_version,
            doc_type=doc_type,
            source_table=f"{doc_type}s",
            source_id=source_id,
            content_text=content_text,
            doc_metadata=metadata,
        )
    )


def _search(engine: Engine, intent: str, query: str, **kwargs: Any) -> list:
    with Session(engine) as session:
        return hybrid_search(session, intent, "17.8", query, **kwargs)


# ---- hybrid_search: 의도별 SQL 필터 + 관련도 top-k -------------------------------


@pytest.fixture
def seeded_docs(migrated_engine: Engine) -> Engine:
    with Session(migrated_engine) as session:
        session.execute(
            insert(Patch).values(
                version="17.8",
                set_number=17,
                released_at=datetime(2026, 1, 1, tzinfo=UTC),
                is_current=True,
                detected_at=datetime(2026, 1, 1, tzinfo=UTC),
            )
        )
        session.execute(
            insert(Patch).values(
                version="17.7",
                set_number=17,
                released_at=datetime(2025, 12, 1, tzinfo=UTC),
                is_current=False,
                detected_at=datetime(2025, 12, 1, tzinfo=UTC),
            )
        )
        session.commit()

        # doc_type별 1개씩 + item_build은 챔피언이 다른 2개(정렬 검증용).
        # source_id는 doc_type 내에서만 의미 있는 값이라 겹쳐도 무방(실제 스키마의
        # UNIQUE 제약은 (patch_version, doc_type, source_table, source_id)).
        _add_doc(
            session,
            "comp",
            1,
            "리롤 요네 조합(티어 A): 평균 등수 4.10. 구성: 요네(캐리), 신짜오.",
            {
                "name": "리롤 요네",
                "tier_rank": "A",
                "is_active": True,
                "champions": ["요네", "신짜오"],
            },
        )
        _add_doc(
            session,
            "playstyle",
            1,
            "리롤 요네 조합 플레이 스타일: 8레벨 리롤",
            {"name": "리롤 요네", "is_active": True, "champions": ["요네", "신짜오"]},
        )
        _add_doc(
            session,
            "augment",
            1,
            "힘의 마법공학(gold 등급) 증강체: 공격력이 증가합니다.",
            {"name": "힘의 마법공학", "tier": "gold"},
        )
        _add_doc(
            session,
            "item_build",
            1,
            "요네 아이템 빌드: 무한의 대검, 피바라기. 승률 20.0%",
            {
                "champion": "요네",
                "champion_id": 1,
                "items": ["무한의 대검", "피바라기"],
            },
        )
        _add_doc(
            session,
            "item_build",
            2,
            "신짜오 아이템 빌드: 가시 갑옷, 워모그의 갑옷. 승률 15.0%",
            {
                "champion": "신짜오",
                "champion_id": 2,
                "items": ["가시 갑옷", "워모그의 갑옷"],
            },
        )
        # 이전 패치 문서 — patch_version 필터로 제외돼야 함
        _add_doc(
            session,
            "item_build",
            3,
            "요네 아이템 빌드: 무한의 대검. 승률 30.0%",
            {"champion": "요네", "champion_id": 3, "items": ["무한의 대검"]},
            patch_version="17.7",
        )
        session.commit()
    return migrated_engine


def test_comp_recommendation_only_searches_comp_and_playstyle(
    seeded_docs: Engine,
) -> None:
    results = _search(seeded_docs, INTENT_COMP_RECOMMENDATION, "요즘 조합 추천해줘")
    assert {r.doc_type for r in results} == {"comp", "playstyle"}


def test_item_recommendation_only_searches_item_build(seeded_docs: Engine) -> None:
    results = _search(seeded_docs, INTENT_ITEM_RECOMMENDATION, "요네 아이템 뭐 가요?")
    assert {r.doc_type for r in results} == {"item_build"}
    # patch_version 필터: 17.7의 item_build(source_id=3)는 제외돼야 함
    assert all(r.patch_version == "17.8" for r in results)


def test_search_works_without_any_embedding_vectors(seeded_docs: Engine) -> None:
    """CHAT-36 핵심: 시드 문서 전부 embedding이 NULL인데도(배치가 더 이상 벡터를
    만들지 않음) 검색이 정상 동작해야 한다."""
    with Session(seeded_docs) as session:
        assert all(
            doc.embedding is None for doc in session.query(MetaDocumentEmbedding).all()
        )
    results = _search(seeded_docs, INTENT_AUGMENT_RECOMMENDATION, "힘의 마법공학 어때?")
    assert [r.doc_metadata["name"] for r in results] == ["힘의 마법공학"]


def test_item_recommendation_caps_builds_per_champion_for_breadth(
    seeded_docs: Engine,
) -> None:
    """2026-08-07 PM 피드백: 여러 챔피언의 아이템 빌드를 한꺼번에 물어보는
    후속질문("이 챔피언들을 조합에 넣을 때...")에서, 순수 관련도순 top-k만
    쓰면 한 챔피언의 빌드만 여러 개 뽑히고 나머지 챔피언은 아예 안 뽑히는
    문제가 실제로 확인됨(5코스트 9명 중 1명만 답변에 등장). 챔피언별로 캡을
    걸어 여러 챔피언이 함께 뽑히는지 검증한다."""
    with Session(seeded_docs) as session:
        # 가렌: 빌드 5개 — 캡이 없으면 id 순으로 먼저 다 뽑힘.
        for i in range(5):
            _add_doc(
                session,
                "item_build",
                100 + i,
                f"가렌 아이템 빌드 {i}",
                {"champion": "가렌", "items": []},
            )
        for i, name in enumerate(["럭스", "애쉬", "티모"]):
            _add_doc(
                session,
                "item_build",
                200 + i,
                f"{name} 아이템 빌드",
                {"champion": name, "items": []},
            )
        session.commit()

    results = _search(
        seeded_docs, INTENT_ITEM_RECOMMENDATION, "가렌 럭스 애쉬 티모 아이템 추천"
    )
    champions = [r.doc_metadata.get("champion") for r in results]
    assert champions.count("가렌") == ITEM_BUILD_PER_CHAMPION_LIMIT
    assert {"럭스", "애쉬", "티모"}.issubset(set(champions))


# CHAT-14: 아이템 효과 자체를 묻는 질문("보석 건틀릿 아이템 효과 알려줘")에
# 답할 수 있도록 item_recommendation이 item_build와 함께 item(DATA-19 description
# 기반) 문서도 검색하는지 확인.
def test_item_recommendation_also_searches_item_doc_type(seeded_docs: Engine) -> None:
    with Session(seeded_docs) as session:
        _add_doc(
            session,
            "item",
            1,
            "보석 건틀릿: 치명타 확률이 증가합니다.",
            {"name": "보석 건틀릿"},
        )
        session.commit()

    results = _search(
        seeded_docs, INTENT_ITEM_RECOMMENDATION, "보석 건틀릿 아이템 효과 알려줘"
    )
    assert "item" in {r.doc_type for r in results}
    assert "item_build" in {r.doc_type for r in results}


def test_augment_recommendation_only_searches_augment(seeded_docs: Engine) -> None:
    results = _search(
        seeded_docs, INTENT_AUGMENT_RECOMMENDATION, "힘의 마법공학 증강 어때?"
    )
    assert {r.doc_type for r in results} == {"augment"}


def test_general_strategy_searches_all_doc_types(seeded_docs: Engine) -> None:
    results = _search(
        seeded_docs, INTENT_GENERAL_STRATEGY, "힘의 마법공학 들고 요네 메타 운영법"
    )
    assert {r.doc_type for r in results} == {
        "comp",
        "playstyle",
        "augment",
        "item_build",
    }


def test_general_strategy_includes_champion_doc_type(seeded_docs: Engine) -> None:
    """2026-08-07 PM 피드백: "3코스트 챔피언은?" 질의가 champion 문서를
    찾을 수 있어야 한다(신규 doc_type)."""
    with Session(seeded_docs) as session:
        _add_doc(
            session,
            "champion",
            1,
            "가짜챔프(3코스트) 챔피언. 특성: 학살자.",
            {"name": "가짜챔프", "cost": 3},
        )
        session.commit()

    results = _search(seeded_docs, INTENT_GENERAL_STRATEGY, "3코스트 챔피언은?")
    assert "champion" in {r.doc_type for r in results}


def test_general_strategy_cost_query_prefers_matching_cost_champions(
    seeded_docs: Engine,
) -> None:
    """CHAT-36: 이름 없이 속성을 묻는 질의("3코스트 챔피언은?")는 본문 점수로
    정렬된다 — champion 슬롯(GENERAL_STRATEGY_CHAMPION_TOP_K=20)보다 문서가
    많아도 3코스트 챔피언이 먼저 채워져야 한다."""
    with Session(seeded_docs) as session:
        for i in range(25):
            _add_doc(
                session,
                "champion",
                i,
                f"이코챔{i}(2코스트) 챔피언. 특성: 수호자.",
                {"name": f"이코챔{i}", "cost": 2},
            )
        for i in range(4):
            _add_doc(
                session,
                "champion",
                100 + i,
                f"삼코챔{i}(3코스트) 챔피언. 특성: 학살자.",
                {"name": f"삼코챔{i}", "cost": 3},
            )
        session.commit()

    results = _search(seeded_docs, INTENT_GENERAL_STRATEGY, "3코스트 챔피언은?")
    champion_costs = [
        r.doc_metadata["cost"] for r in results if r.doc_type == "champion"
    ]
    assert champion_costs[:4] == [3, 3, 3, 3]


# CHAT-14: "보석 건틀릿 효과가 뭐야?"처럼 "아이템" 키워드 없이 묻는 질문은
# item_recommendation이 아니라 general_strategy로 분류되므로(intent_
# classification.py의 키워드 정규식 기준) 여기서도 item 문서를 찾을 수 있어야 함.
def test_general_strategy_includes_item_doc_type(seeded_docs: Engine) -> None:
    with Session(seeded_docs) as session:
        _add_doc(
            session,
            "item",
            1,
            "보석 건틀릿: 치명타 확률이 증가합니다.",
            {"name": "보석 건틀릿"},
        )
        session.commit()

    results = _search(seeded_docs, INTENT_GENERAL_STRATEGY, "보석 건틀릿 효과가 뭐야?")
    assert "item" in {r.doc_type for r in results}


# ---- CHAT-15(→CHAT-36): 검색 결과 최소 관련도 임계값 ------------------------------
# "죽무 효과는?"처럼 사전에 없는 줄임말이 전혀 다른 아이템('절멸자')으로
# 오검색된 사례(2026-08-09 PM 제보) — item/augment doc_type은 질의가 이름으로
# 지목하지 않으면(관련도 < NAME_HIT_MIN_SCORE) 애초에 후보에서 빠져야 한다.
# champion/comp는 목록형·일반 추천 질의가 정상이라 의도적으로 임계값을 적용하지
# 않는다 — 회귀 확인용 테스트도 함께 둔다.


def _add_unrelated_item(session: Session) -> None:
    # 본문에 질의와 같은 흔한 단어("효과")가 있어도 이름이 안 겹치면 빠져야 한다
    # (2026-10-18 실측: "광폭검 효과는?"이 본문 점수만 0.50).
    _add_doc(
        session,
        "item",
        99,
        "포악한 절단검: 이 효과는 공격력을 올립니다.",
        {"name": "포악한 절단검"},
    )


def test_item_recommendation_excludes_item_doc_not_named_in_query(
    seeded_docs: Engine,
) -> None:
    with Session(seeded_docs) as session:
        _add_unrelated_item(session)
        session.commit()

    results = _search(seeded_docs, INTENT_ITEM_RECOMMENDATION, "광폭검 효과는?")
    assert "item" not in {r.doc_type for r in results}
    assert results  # item_build 결과는 남아있음(임계값 미적용 doc_type)


def test_general_strategy_excludes_item_doc_not_named_in_query(
    seeded_docs: Engine,
) -> None:
    with Session(seeded_docs) as session:
        _add_unrelated_item(session)
        session.commit()

    results = _search(seeded_docs, INTENT_GENERAL_STRATEGY, "광폭검 효과는?")
    assert "item" not in {r.doc_type for r in results}


def test_item_search_rejects_partially_overlapping_other_item_name(
    seeded_docs: Engine,
) -> None:
    """CHAT-36: 글자 일부만 겹치는 다른 아이템("공허 건틀릿", 2026-10-18 실측
    0.57)은 정답("보석 건틀릿")과 함께 끌려오지 않아야 한다."""
    with Session(seeded_docs) as session:
        _add_doc(session, "item", 1, "보석 건틀릿: 정밀 획득", {"name": "보석 건틀릿"})
        _add_doc(
            session, "item", 2, "공허 건틀릿: 최대 체력 저장", {"name": "공허 건틀릿"}
        )
        session.commit()

    results = _search(seeded_docs, INTENT_ITEM_RECOMMENDATION, "보석 건틀릿 효과는?")
    assert [r.doc_metadata["name"] for r in results if r.doc_type == "item"] == [
        "보석 건틀릿"
    ]


def test_augment_recommendation_excludes_augment_doc_not_named_in_query(
    seeded_docs: Engine,
) -> None:
    """base seeded_docs의 '힘의 마법공학'은 질의에 이름이 있어 포함, 여기서
    추가하는 문서는 이름이 없어 제외 — 같은 doc_type 안에서 실제로 갈리는지
    확인한다."""
    with Session(seeded_docs) as session:
        _add_doc(
            session,
            "augment",
            99,
            "동물특공대 지휘관(silver 등급) 증강체: 공격력이 증가합니다.",
            {"name": "동물특공대 지휘관"},
        )
        session.commit()

    results = _search(seeded_docs, INTENT_AUGMENT_RECOMMENDATION, "힘의 마법공학 어때?")
    assert [r.doc_metadata["name"] for r in results] == ["힘의 마법공학"]


def test_general_strategy_still_includes_unnamed_champion_doc(
    seeded_docs: Engine,
) -> None:
    """champion doc_type은 임계값을 의도적으로 적용하지 않는다 — 질의와 무관한
    champion 문서도 그대로 남아야 회귀가 아니다."""
    with Session(seeded_docs) as session:
        _add_doc(
            session,
            "champion",
            1,
            "먼챔프(3코스트) 챔피언. 특성: 학살자.",
            {"name": "먼챔프", "cost": 3},
        )
        session.commit()

    results = _search(seeded_docs, INTENT_GENERAL_STRATEGY, "요즘 메타 어때?")
    assert "먼챔프" in {
        r.doc_metadata.get("name") for r in results if r.doc_type == "champion"
    }


def test_comp_recommendation_still_includes_unnamed_comp_doc(
    seeded_docs: Engine,
) -> None:
    """comp doc_type도 임계값을 의도적으로 적용하지 않는다(특정 조합명이 아닌
    일반 "메타 추천" 질의가 정상)."""
    with Session(seeded_docs) as session:
        _add_doc(session, "comp", 99, "먼 조합 문서", {"name": "먼조합"})
        session.commit()

    results = _search(seeded_docs, INTENT_COMP_RECOMMENDATION, "요즘 메타 조합 추천")
    assert "먼조합" in {
        r.doc_metadata.get("name") for r in results if r.doc_type == "comp"
    }


# ---- CHAT-36: 이름 지목 우선(이름 점수) ------------------------------------------


def _add_tiered_comps(session: Session) -> None:
    _add_doc(
        session,
        "comp",
        501,
        "처형자 아지르 조합(티어 OP). 구성: 아지르(캐리), 베이가.",
        {
            "name": "처형자 아지르",
            "tier_rank": "OP",
            "is_active": True,
            "champions": ["아지르", "베이가"],
        },
    )
    _add_doc(
        session,
        "comp",
        502,
        "달빛 세주아니 조합(티어 C). 구성: 세주아니(캐리), 아리.",
        {
            "name": "달빛 세주아니",
            "tier_rank": "C",
            "is_active": True,
            "champions": ["세주아니", "아리"],
        },
    )


def test_comp_named_in_query_ranks_before_higher_tier_comp(seeded_docs: Engine) -> None:
    """질의가 조합 이름을 지목하면 티어가 낮아도 그 조합이 먼저 나와야 한다(벡터
    검색 시절엔 티어가 거리보다 앞서, top_k 밖의 낮은 티어 조합을 물으면 아예
    안 나올 수 있었음)."""
    with Session(seeded_docs) as session:
        _add_tiered_comps(session)
        session.commit()

    results = _search(
        seeded_docs, INTENT_COMP_RECOMMENDATION, "달빛 세주아니 조합 알려줘", top_k=1
    )
    assert [r.source_id for r in results] == [502]


def test_comp_containing_named_champion_ranks_first(seeded_docs: Engine) -> None:
    """조합 이름이 아니라 구성 챔피언 이름("아리")으로 물어도 그 챔피언이 들어간
    조합이 먼저 나와야 한다(metadata champions 목록 매칭)."""
    with Session(seeded_docs) as session:
        _add_tiered_comps(session)
        session.commit()

    results = _search(
        seeded_docs, INTENT_COMP_RECOMMENDATION, "아리 들어가는 조합 추천", top_k=1
    )
    assert [r.source_id for r in results] == [502]


def test_name_with_korean_particle_still_counts_as_named(seeded_docs: Engine) -> None:
    """조사가 붙은 이름("아리를")도 이름 지목으로 인정돼야 한다(실측 약 0.67)."""
    with Session(seeded_docs) as session:
        _add_tiered_comps(session)
        session.commit()

    results = _search(
        seeded_docs, INTENT_COMP_RECOMMENDATION, "아리를 쓰는 조합 추천", top_k=1
    )
    assert [r.source_id for r in results] == [502]


def test_item_build_matched_by_item_name_in_query(seeded_docs: Engine) -> None:
    """ "가시 갑옷 누가 써?"처럼 아이템 이름으로 물으면 그 아이템이 들어간 빌드가
    먼저 나와야 한다(metadata items 목록 매칭)."""
    results = _search(seeded_docs, INTENT_ITEM_RECOMMENDATION, "가시 갑옷 누가 써?")
    assert results[0].doc_metadata["champion"] == "신짜오"


def test_top_k_orders_by_relevance(seeded_docs: Engine) -> None:
    results = _search(
        seeded_docs, INTENT_ITEM_RECOMMENDATION, "신짜오 아이템 추천", top_k=5
    )
    # 질의가 지목한 신짜오(source_id=2) 빌드가 요네(source_id=1)보다 먼저
    assert [r.source_id for r in results] == [2, 1]


def test_top_k_limit_is_respected(seeded_docs: Engine) -> None:
    results = _search(seeded_docs, INTENT_GENERAL_STRATEGY, "요즘 메타", top_k=2)
    assert len(results) == 2


# ---- CHAT-15 2차 보정: filter_by_name_overlap() (2026-08-09 PM 검증 중 발견) ------
# 거리 임계값 회색지대(0.45~0.55)를 문자 겹침 비율로 추가 방어. 실측 사례
# 재현: "광폭검 효과는?"(존재하지 않는 아이템)이 '포악한 절단검'과 거리 0.49로
# 임계값(0.5)은 통과했지만 이름 글자는 '검' 1개만 겹침(6개 중 1개, 비율 0.167).


class _FakeDoc:
    def __init__(self, doc_type: str, name: str) -> None:
        self.doc_type = doc_type
        self.doc_metadata = {"name": name}


def test_filter_by_name_overlap_keeps_item_when_name_fully_present_in_query() -> None:
    docs = [_FakeDoc("item", "보석 건틀릿")]
    assert filter_by_name_overlap(docs, "보석 건틀릿 효과는?") == docs


def test_filter_by_name_overlap_drops_item_when_name_barely_overlaps_query() -> None:
    """실측 재현: '포악한 절단검'과 "광폭검 효과는?"은 '검' 1글자만 겹침(비율
    0.167, 기준 0.5 미달)."""
    docs = [_FakeDoc("item", "포악한 절단검")]
    assert filter_by_name_overlap(docs, "광폭검 효과는?") == []


def test_filter_by_name_overlap_ignores_doc_types_outside_item_and_augment() -> None:
    docs = [_FakeDoc("comp", "전혀 안 겹치는 조합명"), _FakeDoc("champion", "무관챔프")]
    assert filter_by_name_overlap(docs, "지금 메타 조합 추천해줘") == docs


def test_filter_by_name_overlap_applies_to_augment_too() -> None:
    docs = [_FakeDoc("augment", "동물특공대 지휘관")]
    assert filter_by_name_overlap(docs, "동물특공대 지휘관 효과는?") == docs
    assert filter_by_name_overlap(docs, "전혀 무관한 질문") == []


def test_general_strategy_champion_allocation_ignores_top_k(
    seeded_docs: Engine,
) -> None:
    """2026-08-07 PM 피드백: "3코스트 챔피언은?"에 챔피언 1명만 나오던 문제 —
    champion은 top_k를 다른 doc_type과 나누지 않고 GENERAL_STRATEGY_CHAMPION_TOP_K
    만큼 고정으로 가져와야 한다(코스트 하나에 최대 18명까지 있어 균등 배분이면
    1명만 뽑힘). top_k=1로 호출해도 15명이 전부 반환되는지 확인한다."""
    with Session(seeded_docs) as session:
        for i in range(15):
            _add_doc(
                session,
                "champion",
                i,
                f"챔프{i}(3코스트) 챔피언. 특성: 학살자.",
                {"name": f"챔프{i}", "cost": 3},
            )
        session.commit()

    results = _search(
        seeded_docs, INTENT_GENERAL_STRATEGY, "3코스트 챔피언은?", top_k=1
    )
    champion_results = [r for r in results if r.doc_type == "champion"]
    assert len(champion_results) == 15


def test_comp_recommendation_does_not_search_champion_doc_type(
    seeded_docs: Engine,
) -> None:
    with Session(seeded_docs) as session:
        _add_doc(
            session,
            "champion",
            1,
            "가짜챔프(3코스트) 챔피언. 특성: 학살자.",
            {"name": "가짜챔프", "cost": 3},
        )
        session.commit()

    results = _search(seeded_docs, INTENT_COMP_RECOMMENDATION, "가짜챔프 조합 추천")
    assert "champion" not in {r.doc_type for r in results}


# ---- general_strategy doc_type 균형 배분(2026-08-07 운영 관측 버그 회귀) ---------


def test_general_strategy_guarantees_comp_representation_even_when_augments_match(
    seeded_docs: Engine,
) -> None:
    """운영에서 재현된 문제: "메타" 같은 추상 질의에서 augment 청크가 comp보다
    관련도가 높게 나와, 순수 top-k만 쓰면 comp가 결과에서 아예 빠졌다(실측:
    상위 8개 전부 augment). doc_type별 최소 배분으로 comp가 항상 포함되는지
    검증한다 — augment 4개를 전부 질의가 지목해 comp보다 관련도가 높은
    상황을 만든다."""
    with Session(seeded_docs) as session:
        for i, name in enumerate(["강철 심장", "강철 의지", "강철 주먹", "강철 방패"]):
            _add_doc(
                session,
                "augment",
                100 + i,
                f"{name}(silver 등급) 증강체: 방어력이 증가합니다.",
                {"name": name},
            )
        session.commit()

    results = _search(
        seeded_docs,
        INTENT_GENERAL_STRATEGY,
        "강철 심장 강철 의지 강철 주먹 강철 방패 메타",
    )
    assert "comp" in {r.doc_type for r in results}


def test_general_strategy_allocates_remainder_to_earlier_doc_types_first(
    seeded_docs: Engine,
) -> None:
    """top_k가 champion 제외 doc_type 개수(CHAT-14로 5: comp/playstyle/augment/
    item_build/item)로 나누어떨어지지 않으면, 나머지는 INTENT_DOC_TYPES 순서상
    앞쪽 타입(comp)부터 1개씩 더 배정된다."""
    with Session(seeded_docs) as session:
        _add_doc(session, "comp", 2, "두번째 조합 문서", {"name": "두번째 조합"})
        session.commit()

    results = _search(seeded_docs, INTENT_GENERAL_STRATEGY, "요즘 메타", top_k=6)
    comp_count = sum(1 for r in results if r.doc_type == "comp")
    playstyle_count = sum(1 for r in results if r.doc_type == "playstyle")
    # comp는 2개(1+나머지 1) 배정, playstyle은 1개 배정
    assert comp_count == 2
    assert playstyle_count == 1


# ---- tier_rank 우선순위 정렬(2026-08-07 PM 피드백 회귀) --------------------------


def test_comp_recommendation_orders_higher_tier_before_more_relevant_lower_tier(
    seeded_docs: Engine,
) -> None:
    """이름을 지목하지 않는 일반 질의에서는 티어가 관련도보다 앞선 정렬 기준이어야
    한다 — 본문이 질의와 더 많이 겹치는 A티어보다 OP가 먼저 나와야 한다
    (2026-08-07 PM 피드백: "메타" 질의에 A티어만 나오고 OP/S티어 조합이 검색조차
    안 됨)."""
    with Session(seeded_docs) as session:
        _add_doc(
            session,
            "comp",
            201,
            "요즘 메타 추천 A티어 조합",
            {"name": "가나다", "tier_rank": "A"},
        )
        _add_doc(
            session, "comp", 202, "OP티어 조합", {"name": "라마바", "tier_rank": "OP"}
        )
        session.commit()

    results = _search(
        seeded_docs, INTENT_COMP_RECOMMENDATION, "요즘 메타 추천", top_k=1
    )
    assert [r.source_id for r in results] == [202]


# CHAT-18(PM 제보 2026-08-12): DATA-17 소프트 삭제(is_active=false)된 조합은
# op.gg 상위 10위에서 밀려난 이후 tier_rank가 갱신 없이 얼어붙는다 — 활성
# 조합보다 항상 뒤로 밀려야 한다(얼어붙은 옛 "S"가 지금 활성인 "A"를 이기면 안 됨).
def test_comp_recommendation_ranks_active_comp_before_inactive_even_if_lower_tier(
    seeded_docs: Engine,
) -> None:
    with Session(seeded_docs) as session:
        _add_doc(
            session,
            "comp",
            401,
            "비활성 S티어 조합",
            {"name": "옛조합", "tier_rank": "S", "is_active": False},
        )
        _add_doc(
            session,
            "comp",
            402,
            "활성 A티어 조합",
            {"name": "새조합", "tier_rank": "A", "is_active": True},
        )
        session.commit()

    # 질의가 비활성 조합을 이름으로 지목해도 활성 여부가 먼저다.
    results = _search(seeded_docs, INTENT_COMP_RECOMMENDATION, "옛조합 알려줘", top_k=1)
    assert [r.source_id for r in results] == [402]


def test_general_strategy_balanced_search_orders_comp_allocation_by_tier(
    seeded_docs: Engine,
) -> None:
    """doc_type 균형 배분(comp 슬롯) 안에서도 티어 우선순위가 적용돼야 한다."""
    with Session(seeded_docs) as session:
        _add_doc(
            session,
            "comp",
            301,
            "요즘 메타 B티어 조합",
            {"name": "가", "tier_rank": "B"},
        )
        _add_doc(session, "comp", 302, "S티어 조합", {"name": "나", "tier_rank": "S"})
        session.commit()

    results = _search(seeded_docs, INTENT_GENERAL_STRATEGY, "요즘 메타", top_k=4)
    comp_results = [r for r in results if r.doc_type == "comp"]
    assert comp_results[0].source_id == 302


# ---- lookup_item_builds_by_champion_ids: 구조화 조회(2026-08-07 PM 요청) --------


def test_lookup_item_builds_by_champion_ids_returns_only_requested_champions(
    seeded_docs: Engine,
) -> None:
    """의미 검색을 완전히 우회해 정확히 요청한 champion_id들의 빌드만
    반환해야 한다 — "이 챔피언들" 후속질문에 무관한 챔피언이 섞이던 문제의
    근본 해결책."""
    with Session(seeded_docs) as session:
        session.execute(
            insert(Champion).values(
                id=1001,
                patch_version="17.8",
                riot_champion_id="TFT17_Bard",
                name_kr="바드",
                name_en="Bard",
                cost=5,
            )
        )
        session.execute(
            insert(Champion).values(
                id=1002,
                patch_version="17.8",
                riot_champion_id="TFT17_Shen",
                name_kr="쉔",
                name_en="Shen",
                cost=5,
            )
        )
        # 요청하지 않을 챔피언(아리) — 결과에 섞이면 안 됨
        session.execute(
            insert(Champion).values(
                id=1003,
                patch_version="17.8",
                riot_champion_id="TFT17_Ahri",
                name_kr="아리",
                name_en="Ahri",
                cost=4,
            )
        )
        for name, source_id in [("바드", 500), ("쉔", 501), ("아리", 502)]:
            session.execute(
                insert(MetaDocumentEmbedding).values(
                    patch_version="17.8",
                    doc_type="item_build",
                    source_table="champion_item_builds",
                    source_id=source_id,
                    content_text=f"{name} 아이템 빌드",
                    doc_metadata={"champion": name},
                )
            )
        session.commit()

        results = lookup_item_builds_by_champion_ids(session, "17.8", [1001, 1002])

    champion_names = {r.doc_metadata["champion"] for r in results}
    assert champion_names == {"바드", "쉔"}


def test_lookup_item_builds_by_champion_ids_caps_per_champion(
    seeded_docs: Engine,
) -> None:
    with Session(seeded_docs) as session:
        session.execute(
            insert(Champion).values(
                id=1001,
                patch_version="17.8",
                riot_champion_id="TFT17_Bard",
                name_kr="바드",
                name_en="Bard",
                cost=5,
            )
        )
        for i in range(5):
            session.execute(
                insert(MetaDocumentEmbedding).values(
                    patch_version="17.8",
                    doc_type="item_build",
                    source_table="champion_item_builds",
                    source_id=600 + i,
                    content_text=f"바드 아이템 빌드 {i}",
                    doc_metadata={"champion": "바드"},
                )
            )
        session.commit()

        results = lookup_item_builds_by_champion_ids(session, "17.8", [1001])

    assert len(results) == 2


def test_lookup_item_builds_by_champion_ids_returns_empty_for_empty_input(
    seeded_docs: Engine,
) -> None:
    with Session(seeded_docs) as session:
        assert lookup_item_builds_by_champion_ids(session, "17.8", []) == []


def test_lookup_item_builds_by_champion_ids_returns_empty_for_unknown_ids(
    seeded_docs: Engine,
) -> None:
    with Session(seeded_docs) as session:
        assert lookup_item_builds_by_champion_ids(session, "17.8", [999999]) == []
