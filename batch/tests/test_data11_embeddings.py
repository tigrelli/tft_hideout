"""DATA-11 pytest: chunk 생성과 검색 문서 upsert 동작.

CHAT-36(2026-10-18): HF 임베딩을 없애 벡터 없이 텍스트만 적재하므로, HF
클라이언트·임베딩 차원 검증 테스트를 제거하고 upsert_documents 테스트로 옮겼다.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from db_session import models
from embeddings import (
    augment_chunk_text,
    champion_chunk_text,
    collect_chunks,
    is_charge_variant_item,
    is_real_champion,
    comp_chunk_text,
    item_build_chunk_text,
    item_chunk_text,
    playstyle_chunk_text,
    upsert_documents,
)

# ---- 순수 텍스트 생성 함수(가벼운 fake 객체로 속성만 흉내) -----------------------


@dataclass
class _FakeComp:
    name: str
    tier_rank: str
    avg_place: float
    win_rate: float | None
    play_rate: float
    playstyle_text: str
    is_active: bool = True


@dataclass
class _FakeAugment:
    name_kr: str
    tier: str
    description: str


@dataclass
class _FakeBuild:
    item_combination: list[str]
    win_rate: float
    play_rate: float
    avg_place: float


@dataclass
class _FakeChampion:
    name_kr: str
    cost: int


@dataclass
class _FakeItem:
    name_kr: str
    description: str
    stats: dict[str, object] | None = None


def test_comp_chunk_text_includes_core_fields_and_carry_marker() -> None:
    comp = _FakeComp(
        name="가짜 조합",
        tier_rank="OP",
        avg_place=3.1,
        win_rate=0.19,
        play_rate=0.02,
        playstyle_text="리롤 성향 강함",
    )
    text = comp_chunk_text(comp, [("아칼리", True), ("징크스", False)])

    assert "가짜 조합" in text
    assert "OP" in text
    assert "아칼리(캐리)" in text
    assert "징크스" in text and "징크스(캐리)" not in text
    assert "19.0%" in text
    assert "리롤 성향 강함" in text


def test_comp_chunk_text_handles_missing_win_rate() -> None:
    comp = _FakeComp(
        name="승률없음",
        tier_rank="A",
        avg_place=4.0,
        win_rate=None,
        play_rate=0.01,
        playstyle_text="설명",
    )
    text = comp_chunk_text(comp, [])

    assert "정보 없음" in text


def test_playstyle_chunk_text() -> None:
    comp = _FakeComp(
        name="가짜 조합",
        tier_rank="S",
        avg_place=3.5,
        win_rate=0.2,
        play_rate=0.03,
        playstyle_text="AP 캐리 조합",
    )
    assert playstyle_chunk_text(comp) == "가짜 조합 조합 플레이 스타일: AP 캐리 조합"


# ---- CHAT-18(PM 제보 2026-08-12): is_active=false 조합 상태 표시 -----------------


def test_comp_chunk_text_does_not_add_notice_for_active_comp() -> None:
    comp = _FakeComp(
        name="활성 조합",
        tier_rank="S",
        avg_place=3.0,
        win_rate=0.2,
        play_rate=0.02,
        playstyle_text="설명",
        is_active=True,
    )
    text = comp_chunk_text(comp, [])
    assert "상위 10위 밖" not in text


def test_comp_chunk_text_adds_notice_for_inactive_comp() -> None:
    comp = _FakeComp(
        name="비활성 조합",
        tier_rank="S",
        avg_place=3.4,
        win_rate=None,
        play_rate=0.005,
        playstyle_text="설명",
        is_active=False,
    )
    text = comp_chunk_text(comp, [])
    assert "상위 10위 밖" in text


def test_playstyle_chunk_text_adds_notice_for_inactive_comp() -> None:
    comp = _FakeComp(
        name="비활성 조합",
        tier_rank="S",
        avg_place=3.4,
        win_rate=None,
        play_rate=0.005,
        playstyle_text="설명",
        is_active=False,
    )
    text = playstyle_chunk_text(comp)
    assert "상위 10위 밖" in text


def test_augment_chunk_text_does_not_include_win_rate() -> None:
    augment = _FakeAugment(name_kr="가짜 증강체", tier="gold", description="가짜 설명")
    text = augment_chunk_text(augment)

    assert "가짜 증강체" in text
    assert "gold" in text
    assert "가짜 설명" in text
    assert "%" not in text  # augments 테이블엔 win_rate 자체가 없음(DATA-10 결정)


def test_item_build_chunk_text() -> None:
    build = _FakeBuild(
        item_combination=["TFT_Item_A", "TFT_Item_B"],
        win_rate=0.2,
        play_rate=0.25,
        avg_place=3.5,
    )
    text = item_build_chunk_text(build, "가짜챔프", ["검", "갑옷"])

    assert "가짜챔프" in text
    assert "검, 갑옷" in text
    assert "TFT_Item_A" not in text
    assert "20.0%" in text
    assert "25.0%" in text


def test_item_build_chunk_text_no_op_when_item_names_empty() -> None:
    build = _FakeBuild(item_combination=[], win_rate=0.2, play_rate=0.25, avg_place=3.5)
    text = item_build_chunk_text(build, "가짜챔프", [])
    assert "정보 없음" in text


def test_champion_chunk_text_includes_cost_and_traits() -> None:
    champion = _FakeChampion(name_kr="가짜챔프", cost=3)
    text = champion_chunk_text(champion, ["학살자", "N.O.V.A."])

    assert "가짜챔프" in text
    assert "3코스트" in text
    assert "학살자, N.O.V.A." in text


def test_champion_chunk_text_no_op_when_traits_empty() -> None:
    champion = _FakeChampion(name_kr="가짜챔프", cost=1)
    text = champion_chunk_text(champion, [])
    assert "정보 없음" in text


def test_item_chunk_text_includes_name_and_description() -> None:
    item = _FakeItem(name_kr="보석 건틀릿", description="치명타 확률이 증가합니다.")
    text = item_chunk_text(item)
    assert text == "보석 건틀릿: 치명타 확률이 증가합니다."


def test_item_chunk_text_appends_whitelisted_stats_when_present() -> None:
    """DATA-20(CHAT-14 PM 검증 중 발견, 2026-08-09): description만으로는
    "치명타 확률이 얼마나 증가하나요?" 같은 수치 질문에 답할 근거가 없어
    화이트리스트 핵심 스탯을 덧붙인다."""
    item = _FakeItem(
        name_kr="보석 건틀릿",
        description="치명타 확률이 증가합니다.",
        stats={"AP": 35, "CritChance": 35, "CritDamageToGive": None},
    )
    text = item_chunk_text(item)
    assert text == (
        "보석 건틀릿: 치명타 확률이 증가합니다. (스탯: 주문력 +35, 치명타 확률 +35%)"
    )


def test_item_chunk_text_no_op_when_no_whitelisted_stats() -> None:
    item = _FakeItem(
        name_kr="공허 건틀릿",
        description="전투 시작: 최대 체력을 저장합니다.",
        stats={"HexRadius": 4, "{cd951938}": 0.1},
    )
    text = item_chunk_text(item)
    assert text == "공허 건틀릿: 전투 시작: 최대 체력을 저장합니다."


# ---- is_real_champion(): PVE/플레이스홀더 유닛 필터(2026-08-07 PM 피드백) -------


def test_is_real_champion_true_for_current_set_prefix() -> None:
    assert is_real_champion("TFT17_Akali", 17) is True


def test_is_real_champion_false_for_no_set_prefix() -> None:
    # 골렘: "TFT_BlueGolem"(세트 번호 없음, 실측 2026-08-07)
    assert is_real_champion("TFT_BlueGolem", 17) is False


def test_is_real_champion_false_for_other_set_prefix() -> None:
    # 협곡 바위 게: "TFT9_SLIME_Crab"(다른 세트 번호가 그대로 남아있음)
    assert is_real_champion("TFT9_SLIME_Crab", 17) is False


def test_is_real_champion_false_for_fake_unit_suffix() -> None:
    # 소형 블랙홀: "TFT17_DarkStar_FakeUnit"(현재 세트 접두어지만 FakeUnit 표시)
    assert is_real_champion("TFT17_DarkStar_FakeUnit", 17) is False


def test_is_real_champion_false_for_enemy_boss_unit() -> None:
    # 태고족 우두머리: "TFT17_Enemy_Aatrox"(현재 세트 접두어지만 아트록스 스킬을
    # 재사용하는 별도 보스 유닛 — 5코스트로 구매 가능한 챔피언이 아님, PM 피드백)
    assert is_real_champion("TFT17_Enemy_Aatrox", 17) is False


# ---- is_charge_variant_item(): 소모품 잔여 사용 횟수 변형 필터(2026-08-09 PM 제보) --


def test_is_charge_variant_item_true_for_uses_left_variant() -> None:
    assert is_charge_variant_item("재조합기 <rules>(8회 사용 가능!)</rules>") is True


def test_is_charge_variant_item_false_for_plain_name() -> None:
    assert is_charge_variant_item("재조합기") is False
    assert is_charge_variant_item("보석 건틀릿") is False


# ---- collect_chunks / upsert_documents(실제 마이그레이션 DB) -------------------


@pytest.fixture
def seeded_session(migrated_engine: Engine) -> Session:
    with Session(migrated_engine) as session:
        session.add(
            models.Patch(
                version="17.8",
                set_number=17,
                released_at=datetime(2026, 1, 1, tzinfo=UTC),
                is_current=False,
                detected_at=datetime(2026, 1, 1, tzinfo=UTC),
            )
        )
        session.flush()

        champion = models.Champion(
            patch_version="17.8",
            riot_champion_id="TFT17_X",
            name_kr="엑스",
            name_en="X",
            cost=1,
        )
        session.add(champion)
        session.flush()

        comp = models.Comp(
            patch_version="17.8",
            riot_comp_id="comp-1",
            name="가짜조합",
            tier_rank="S",
            avg_place=3.0,
            play_rate=0.1,
            win_rate=0.2,
            playstyle_text="설명",
            updated_at=datetime.now(UTC),
        )
        session.add(comp)
        session.flush()

        session.add(
            models.CompChampion(
                comp_id=comp.id,
                champion_id=champion.id,
                is_carry=True,
                recommended_items=[],
            )
        )
        session.add(
            models.Augment(
                patch_version="17.8",
                riot_augment_id="aug-1",
                name_kr="가짜증강",
                name_en="FakeAug",
                tier="gold",
                description="설명",
                is_legend_related=False,
            )
        )
        session.add(
            models.ChampionItemBuild(
                champion_id=champion.id,
                patch_version="17.8",
                item_combination=["A"],
                play_rate=0.1,
                avg_place=3.0,
                win_rate=0.2,
            )
        )
        # CHAT-14: description이 있는 아이템만 "item" doc_type으로 임베딩되는지
        # 확인하기 위해 있음/없음 두 케이스를 함께 시딩(item_combination의 "A"와
        # 겹치지 않는 별도 riot_item_id 사용 — CHAT-13 테스트의 "items == ['A']"
        # 스냅샷에 영향 없게 함).
        session.add(
            models.Item(
                patch_version="17.8",
                riot_item_id="TFT_Item_B",
                name_kr="가짜아이템",
                name_en="FakeItem",
                item_type="core",
                components=[],
                stats={},
                description="가짜 아이템 효과 설명",
            )
        )
        session.add(
            models.Item(
                patch_version="17.8",
                riot_item_id="TFT_Item_NoDesc",
                name_kr="설명없는아이템",
                name_en="NoDescItem",
                item_type="core",
                components=[],
                stats={},
                description=None,
            )
        )
        # 2026-08-09 PM 제보: op.gg 원본이 소모품(재조합기 등)을 "N회 사용 가능"
        # 잔여 횟수별 별도 아이템 행으로 중복 제공해(name_kr에 <rules> 태그 그대로
        # 포함), 이걸 그대로 임베딩하면 LLM이 같은 패치 안에 공존하는 변형들을
        # 서로 다른 시점으로 착각해 허구의 "패치 변경" 답변을 만든 실제 사례가
        # 있었다 — description은 있지만 제외돼야 하는 케이스를 함께 시딩.
        session.add(
            models.Item(
                patch_version="17.8",
                riot_item_id="TFT_Consumable_ItemReroller_UsesLeft8",
                name_kr="재조합기 <rules>(8회 사용 가능!)</rules>",
                name_en="Item Reroller",
                item_type="consumable",
                components=[],
                stats={},
                description="챔피언이 장착한 모든 아이템을 해제하고 변경합니다.",
            )
        )
        session.commit()
        yield session


def test_collect_chunks_builds_all_doc_types(seeded_session: Session) -> None:
    chunks = collect_chunks(seeded_session, "17.8")
    doc_types = {c["doc_type"] for c in chunks}

    assert doc_types == {
        "comp",
        "playstyle",
        "augment",
        "item_build",
        "champion",
        "item",
    }
    comp_chunk = next(c for c in chunks if c["doc_type"] == "comp")
    assert "엑스(캐리)" in comp_chunk["content_text"]


# CHAT-18(PM 제보 2026-08-12): comp/playstyle 메타데이터에 조합 이름만 있고
# 구성 챔피언 개별 이름이 없어, 챗봇 백엔드의 verify_grounding()이 정상 인용된
# 챔피언 이름도 항상 근거검증 경고를 유발했다(CHAT-13이 item_build에 이미
# 고친 것과 동일한 구조적 문제) — "champions" 키로 보강.
def test_collect_chunks_comp_and_playstyle_metadata_includes_champion_names(
    seeded_session: Session,
) -> None:
    chunks = collect_chunks(seeded_session, "17.8")
    comp_chunk = next(c for c in chunks if c["doc_type"] == "comp")
    playstyle_chunk = next(c for c in chunks if c["doc_type"] == "playstyle")

    assert comp_chunk["metadata"]["champions"] == ["엑스"]
    assert playstyle_chunk["metadata"]["champions"] == ["엑스"]


# CHAT-14: description이 있는 아이템만 "item" doc_type으로 임베딩되는지 확인.
def test_collect_chunks_item_doc_type_only_for_items_with_description(
    seeded_session: Session,
) -> None:
    chunks = collect_chunks(seeded_session, "17.8")
    item_chunks = [c for c in chunks if c["doc_type"] == "item"]

    assert len(item_chunks) == 1
    assert item_chunks[0]["metadata"] == {"name": "가짜아이템"}
    assert item_chunks[0]["content_text"] == "가짜아이템: 가짜 아이템 효과 설명"
    assert item_chunks[0]["source_table"] == "items"


def test_collect_chunks_excludes_charge_variant_items(seeded_session: Session) -> None:
    """2026-08-09 PM 제보: "재조합기 <rules>(8회 사용 가능!)</rules>"처럼 잔여
    사용 횟수 변형은 description이 있어도 "item" doc_type에서 빠져야 한다(허구의
    패치 변경 답변을 유발한 실제 원인, is_charge_variant_item 참고)."""
    chunks = collect_chunks(seeded_session, "17.8")
    item_names = {c["metadata"]["name"] for c in chunks if c["doc_type"] == "item"}

    assert "재조합기 <rules>(8회 사용 가능!)</rules>" not in item_names


# CHAT-13: item_build 문서 metadata에 아이템 이름 목록이 있어야 챗봇 백엔드의
# verify_grounding()이 인용된 아이템 이름을 "알려진 이름"으로 인식할 수 있다
# (전엔 champion 키만 있어 아이템 인용이 항상 근거검증 경고를 유발했음, PM 제보
# 2026-08-08). champion_id는 CHAT-13 후속 수정으로 추가 — 없으면 챗봇이 만드는
# 챔피언 링크가 필터 없는 `/items/builds`로만 가서 클릭해도 챔피언이 선택되지
# 않는 문제가 있었다(PM 제보).
def test_collect_chunks_item_build_metadata_includes_item_names(
    seeded_session: Session,
) -> None:
    chunks = collect_chunks(seeded_session, "17.8")
    item_build_chunk = next(c for c in chunks if c["doc_type"] == "item_build")
    champion = seeded_session.scalars(
        select(models.Champion).where(models.Champion.name_kr == "엑스")
    ).one()

    assert item_build_chunk["metadata"]["champion"] == "엑스"
    assert item_build_chunk["metadata"]["champion_id"] == champion.id
    assert item_build_chunk["metadata"]["items"] == ["A"]


def test_collect_chunks_champion_includes_cost_and_traits(
    seeded_session: Session,
) -> None:
    chunks = collect_chunks(seeded_session, "17.8")
    champion_chunk = next(c for c in chunks if c["doc_type"] == "champion")

    assert "엑스" in champion_chunk["content_text"]
    assert "1코스트" in champion_chunk["content_text"]
    assert champion_chunk["metadata"] == {"name": "엑스", "cost": 1}


def test_collect_chunks_excludes_champions_outside_1_to_5_cost(
    seeded_session: Session,
) -> None:
    seeded_session.add(
        models.Champion(
            patch_version="17.8",
            riot_champion_id="TFT17_Anvil",
            name_kr="아이템 모루",
            name_en="ItemAnvil",
            cost=8,
        )
    )
    seeded_session.commit()

    chunks = collect_chunks(seeded_session, "17.8")
    champion_names = {
        c["metadata"]["name"] for c in chunks if c["doc_type"] == "champion"
    }

    assert "아이템 모루" not in champion_names


def test_collect_chunks_excludes_pve_units_with_1_to_5_cost(
    seeded_session: Session,
) -> None:
    """PVE 유닛(골렘 등)은 코스트가 1~5 범위 안에 들어와 위 코스트 필터만으로는
    안 걸러진다 — apiName 패턴(is_real_champion)까지 함께 확인해야 한다."""
    seeded_session.add(
        models.Champion(
            patch_version="17.8",
            riot_champion_id="TFT_BlueGolem",
            name_kr="골렘",
            name_en="Golem",
            cost=1,
        )
    )
    seeded_session.commit()

    chunks = collect_chunks(seeded_session, "17.8")
    champion_names = {
        c["metadata"]["name"] for c in chunks if c["doc_type"] == "champion"
    }

    assert "골렘" not in champion_names


def test_collect_chunks_caps_item_build_at_top_n_by_play_rate_per_champion(
    seeded_session: Session,
) -> None:
    """2026-08-07 운영에서 확인된 문제: champion_item_builds가 챔피언당 수백~천
    단위라 전부 문서화하면 안 됨(당시엔 HuggingFace 무료 티어 소진 + 실제로는
    0건만 임베딩돼 챗봇이 "아이템 빌드는 확인 안 됨"으로만 답하던 원인, CHAT-36
    이후엔 검색 품질 때문에 유지). champion_id별
    play_rate 상위 TOP_BUILDS_PER_CHAMPION개만 남는지 검증한다."""
    from embeddings import TOP_BUILDS_PER_CHAMPION

    champion = seeded_session.scalars(
        select(models.Champion).where(models.Champion.riot_champion_id == "TFT17_X")
    ).one()
    for i in range(TOP_BUILDS_PER_CHAMPION + 5):
        seeded_session.add(
            models.ChampionItemBuild(
                champion_id=champion.id,
                patch_version="17.8",
                item_combination=[f"Item{i}"],
                play_rate=0.5 - i * 0.01,  # 내림차순 — 낮은 i일수록 상위권
                avg_place=3.0,
                win_rate=0.2,
            )
        )
    seeded_session.commit()

    chunks = collect_chunks(seeded_session, "17.8")
    item_build_chunks = [c for c in chunks if c["doc_type"] == "item_build"]

    # 기존 seeded_session fixture의 1건 + 이번에 추가한 TOP_BUILDS_PER_CHAMPION+5건
    # 중 play_rate 상위 TOP_BUILDS_PER_CHAMPION개만 남아야 함(기존 1건은
    # play_rate=0.1로 가장 낮아 컷오프됨).
    assert len(item_build_chunks) == TOP_BUILDS_PER_CHAMPION
    assert all("Item" in c["content_text"] for c in item_build_chunks)


def test_upsert_documents_stores_text_without_vectors(
    seeded_session: Session,
) -> None:
    """CHAT-36: 벡터 없이(embedding NULL) 텍스트·메타데이터만 적재된다."""
    chunks = collect_chunks(seeded_session, "17.8")
    upsert_documents(seeded_session, "17.8", chunks)
    seeded_session.commit()

    rows = seeded_session.scalars(
        select(models.MetaDocumentEmbedding).where(
            models.MetaDocumentEmbedding.patch_version == "17.8"
        )
    ).all()
    assert len(rows) == len(chunks)
    assert all(r.embedding is None for r in rows)
    assert {r.content_text for r in rows} == {c["content_text"] for c in chunks}


def test_upsert_documents_same_patch_updates_not_duplicates(
    seeded_session: Session,
) -> None:
    chunks = collect_chunks(seeded_session, "17.8")

    upsert_documents(seeded_session, "17.8", chunks)
    seeded_session.commit()
    upsert_documents(seeded_session, "17.8", chunks)
    seeded_session.commit()

    rows = seeded_session.scalars(
        select(models.MetaDocumentEmbedding).where(
            models.MetaDocumentEmbedding.patch_version == "17.8"
        )
    ).all()
    assert len(rows) == len(chunks)


def test_upsert_documents_clears_stale_vector_on_update(
    seeded_session: Session,
) -> None:
    """CHAT-36 이전 배치가 남긴 벡터 행을 다시 적재하면, 바뀐 텍스트와 어긋난
    옛 벡터가 남지 않도록 embedding이 NULL로 비워지고 텍스트는 갱신된다."""
    chunk = {
        "doc_type": "augment",
        "source_table": "augments",
        "source_id": 1,
        "content_text": "새 텍스트",
        "metadata": {"name": "가짜 증강"},
    }
    seeded_session.add(
        models.MetaDocumentEmbedding(
            patch_version="17.8",
            doc_type="augment",
            source_table="augments",
            source_id=1,
            content_text="옛 텍스트",
            embedding=[0.1] * 1024,
            doc_metadata={"name": "가짜 증강"},
        )
    )
    seeded_session.commit()

    upsert_documents(seeded_session, "17.8", [chunk])
    seeded_session.commit()
    seeded_session.expire_all()

    row = seeded_session.scalars(
        select(models.MetaDocumentEmbedding).where(
            models.MetaDocumentEmbedding.source_table == "augments",
            models.MetaDocumentEmbedding.source_id == 1,
        )
    ).one()
    assert row.content_text == "새 텍스트"
    assert row.embedding is None


def test_upsert_documents_empty_input_is_noop(seeded_session: Session) -> None:
    upsert_documents(seeded_session, "17.8", [])
    seeded_session.commit()
    assert seeded_session.scalars(select(models.MetaDocumentEmbedding)).first() is None
