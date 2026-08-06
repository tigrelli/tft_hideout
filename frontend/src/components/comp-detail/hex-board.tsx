import Image from "next/image";
import Link from "next/link";
import type { ChampionInComp } from "@/types/catalog";
import { ItemIconRow } from "@/components/comp-detail/item-icon-row";

// 태블릿·데스크톱(md 이상) 전용 헥스 배치도.
//
// FE-14(2026-08-06): op.gg tft_list_meta_decks 응답 units[].cell.{x,y}(x:1~7,
// y:1~4, 4행x7열)에 실제 랭커 배치 좌표가 있음을 확인해, 조합의 모든 챔피언에
// cell_x/cell_y가 채워져 있으면 실좌표 그리드로 그린다. 좌표가 없는(이 컬럼
// 추가 전 배치가 채운) 구 데이터는 is_carry 기반 전열/후열 휴리스틱으로
// 폴백한다.
//
// 챔피언(헥스 타일)을 클릭하면 해당 챔피언의 아이템 빌드 화면으로 이동한다
// (PM 요청 2026-08-06). ItemIconRow의 재료 아이콘은 자체 stopPropagation으로
// 이 링크 이동과 충돌하지 않는다.
//
// FE-15(2026-08-06): op.gg 응답 units[].tier(성급, 2 또는 3)를 챔피언 아이콘
// 위 별 표시로 노출한다(StarRating, 두 배치 모드 공통).
const HEX_CLIP =
  "polygon(25% 0%, 75% 0%, 100% 50%, 75% 100%, 25% 100%, 0% 50%)";
const GRID_COLUMNS = 7;
const GRID_ROWS = 4;
const CELL_WIDTH_PX = 112; // w-28
const CELL_GAP_PX = 12; // gap-3

// 챔피언 이미지는 헥스 안쪽에 꽉 채우지 않고 여백을 두고 앉힌다 — 실제 TFT
// 덱 한 칸(슬롯)처럼 보이도록(PM 요청 2026-08-06). 부모에 padding만 주면 안
// 되는 이유: Next Image의 fill(및 아래 폴백 span)은 position:absolute +
// inset:0인데, 절대배치 자식의 containing block은 조상의 "패딩 박스"라
// padding 영역까지 포함해 inset:0이 그 전체를 채워버린다(패딩이 있어도
// 자식이 패딩 위까지 덮어써 시각적 여백이 안 생기는 CSS 흔한 함정). 그래서
// 이미지를 감싸는 별도 wrapper에 inset:0이 아닌 실제 여백값(inset-3)을 줘서
// 강제로 안쪽에 앉힌다.
//
// 여백 배경 단색만으로는 안 됨: 흰색(bg-surface-card)은 밝은 챔피언 아트와,
// 어두운색(bg-text-primary)은 어두운 챔피언 아트와 겹쳐서 그 챔피언에서만
// 여백이 안 보이는 문제가 실브라우저 확인 중 반복 발견됐다(PM 확인
// 2026-08-06, getBoundingClientRect로 레이아웃 자체는 항상 정확함을 확인 —
// 순수 색상 대비 문제였고 GPU 페인트 버그가 아니었다). 모든 챔피언 아트
// 색상에 항상 대비되는 단색은 없으므로, 이미지 가장자리에 채도 높은
// 브랜드색(primary) ring을 얹어 배경 fill 색과 무관하게 경계선 자체가 항상
// 보이도록 한다(PM 결정 2026-08-06).
function HexIcon({ champion }: { champion: ChampionInComp }) {
  return (
    <div
      style={{ clipPath: HEX_CLIP }}
      className={
        "h-24 w-28 shrink-0 p-1 " +
        (champion.is_carry ? "bg-accent-carry" : "bg-border-default")
      }
    >
      <div
        style={{ clipPath: HEX_CLIP }}
        className="relative h-full w-full overflow-hidden bg-text-primary"
      >
        {champion.square_icon_url ? (
          <div className="absolute inset-3 ring-2 ring-inset ring-primary">
            <Image
              src={champion.square_icon_url}
              alt={champion.name_kr}
              fill
              sizes="112px"
              className="object-cover"
            />
          </div>
        ) : (
          <span className="absolute inset-3 flex items-center justify-center text-caption text-on-brand">
            {champion.name_kr.slice(0, 2)}
          </span>
        )}
      </div>
    </div>
  );
}

// FE-15: 챔피언 성급(2 또는 3, op.gg unit.tier) 표시. op.gg 원본 화면의 별
// 색상 체계(초록/파랑/핑크/회색 등)는 근거 데이터가 없어 재현하지 않고,
// PM 결정(2026-08-06)에 따라 3성=tier-op(레드)/2성=tier-s(골드) 2단계 고정
// 색상만 적용한다(design-tokens.md 기존 티어 배지 색상 재사용).
//
// transform-gpu(자체 컴포지팅 레이어 강제)가 없으면 크로미움이 이 별 텍스트를
// 아예 페인트하지 않는 버그를 실브라우저 검증 중 발견(2026-08-06) — 바로 아래
// 형제 요소인 HexIcon이 clip-path 육각형이라 같은 스태킹 컨텍스트를 공유할 때만
// 재현됨. DOM/computed style은 전부 정상(opacity:1, visible)인데도 실제 페인트가
// 누락돼, 원인 파악 전에는 별이 절반만(짝수 grid-row, 이미 다른 이유로 transform이
// 걸려있던 행) 보이는 것처럼 보였다.
function StarRating({ starLevel }: { starLevel: number | null }) {
  if (!starLevel) {
    return null;
  }
  const colorClass = starLevel >= 3 ? "text-tier-op" : "text-tier-s";
  return (
    <div
      role="img"
      aria-label={`${starLevel}성`}
      className={
        "pointer-events-none absolute inset-x-0 -top-4 z-10 flex " +
        "transform-gpu justify-center text-h2 leading-none drop-shadow " +
        colorClass
      }
    >
      {"★".repeat(starLevel)}
    </div>
  );
}

// 별은 그레이 라인(헥스 테두리) 밖 위쪽에 겹쳐서 표시한다(PM 요청
// 2026-08-06) — 기존에는 세로로 쌓인 별도 줄이라 타일 위에 여백이 그만큼
// 더 생겼는데, relative 컨테이너 안에서 절대 위치로 띄우면 타일이 차지하는
// 공간은 그대로 유지하면서 별만 테두리 위로 살짝 겹쳐 보이게 할 수 있다.
function HexIconWithStar({ champion }: { champion: ChampionInComp }) {
  return (
    <div className="relative">
      <StarRating starLevel={champion.star_level} />
      <HexIcon champion={champion} />
    </div>
  );
}

// 휴리스틱 폴백 모드: 이름이 길어도 안 잘리게 타일 너비가 이름에 맞춰 늘어난다.
function HeuristicHexTile({ champion }: { champion: ChampionInComp }) {
  return (
    <Link
      href={`/items/builds?champion_id=${champion.champion_id}`}
      className="flex w-max min-w-28 shrink-0 flex-col items-center gap-1"
    >
      <HexIconWithStar champion={champion} />
      <span className="whitespace-nowrap text-caption text-text-primary">
        {champion.name_kr}
      </span>
      <ItemIconRow
        names={champion.recommended_item_names}
        icons={champion.recommended_item_icons}
        itemIds={champion.recommended_items}
        className="justify-center"
      />
    </Link>
  );
}

function HexRow({
  rowChampions,
  offset,
}: {
  rowChampions: ChampionInComp[];
  offset: boolean;
}) {
  if (rowChampions.length === 0) {
    return null;
  }
  return (
    <div
      className={
        "flex justify-center gap-3" + (offset ? " translate-x-10" : "")
      }
    >
      {rowChampions.map((champion) => (
        <HeuristicHexTile key={champion.champion_id} champion={champion} />
      ))}
    </div>
  );
}

function HeuristicHexBoard({ champions }: { champions: ChampionInComp[] }) {
  const backline = champions.filter((c) => c.is_carry);
  const frontline = champions.filter((c) => !c.is_carry);

  return (
    <>
      <p className="mb-4 text-caption font-bold text-text-secondary">
        실제 사용할 수 있는 추천 배치가 아닌 휴리스틱으로 시각화되었습니다.
      </p>
      {/* 휴리스틱 배치는 실좌표가 없어 챔피언 타일이 격자 칸에 정확히 맞물리진
          않지만, 실좌표 모드와 같은 배경 격자를 뒤에 깔아 보드 위에 놓인
          배치처럼 보이게 한다(PM 요청 2026-08-06). 두 레이어를 같은 grid
          셀(1/1)에 겹쳐, 고정 크기인 배경 격자가 트랙 크기를 정하고 챔피언
          타일은 그 안에서 가운데 정렬되게 한다. */}
      <div className="grid">
        <HexGridBackdrop className="col-start-1 row-start-1" />
        <div className="col-start-1 row-start-1 z-10 flex flex-col items-center justify-center gap-4">
          <HexRow rowChampions={backline} offset={false} />
          <HexRow
            rowChampions={frontline}
            offset={frontline.length <= backline.length}
          />
        </div>
      </div>
    </>
  );
}

// 실제 TFT 보드는 열이 한 칸씩 어긋난 육각형 타일링이다 — 짝수 행을 반 칸
// (타일 폭+간격의 절반)만큼 오른쪽으로 밀어 벌집 모양을 만든다. 배경 빈 칸과
// 챔피언 타일이 같은 규칙으로 어긋나야 격자선이 실제 타일 위치와 맞는다.
//
// FE-14 완료 시점엔 op.gg 응답에 상하 방향 메타데이터가 없어 y를 그대로
// grid-row로 써서 방향을 임의로 정했었는데(진행현황.md 2026-08-06 FE-14 기록),
// PM이 실제 화면에서 전열/후열이 뒤집혀 보인다고 확인해줘서(2026-08-06) y=1이
// 화면 아래쪽(전열), y=4가 화면 위쪽(후열)이 되도록 행 순서를 반전한다. 벌집
// 오프셋은 데이터상 y가 아니라 "화면에 그려지는 행"이 기준이어야 인접 행끼리
// 어긋나는 육각형 타일링이 성립하므로, 반전된 displayRow로 홀짝을 다시 계산한다.
function cellPlacementStyle(x: number, y: number): React.CSSProperties {
  const displayRow = GRID_ROWS + 1 - y;
  return {
    gridColumnStart: x,
    gridRowStart: displayRow,
    transform:
      displayRow % 2 === 0
        ? `translateX(${(CELL_WIDTH_PX + CELL_GAP_PX) / 2}px)`
        : undefined,
  };
}

// 배경 격자선: 챔피언이 없는 칸도 옅은 회색 헥스 테두리로 그려서 몇 번째
// 줄·칸에 배치됐는지 한눈에 보이게 한다(PM 요청 2026-08-06). 챔피언 아이콘과
// 같은 이중 clip-path 테두리 트릭을 쓰되, 안쪽을 보드 배경색으로 채워
// 테두리 링만 남긴다.
function EmptyHexCell({ x, y }: { x: number; y: number }) {
  return (
    <div
      aria-hidden="true"
      style={{ clipPath: HEX_CLIP, ...cellPlacementStyle(x, y) }}
      className="h-24 w-28 shrink-0 self-start bg-border-default/50 p-px"
    >
      <div
        style={{ clipPath: HEX_CLIP }}
        className="h-full w-full bg-surface-page"
      />
    </div>
  );
}

function buildBackgroundCells(): { x: number; y: number }[] {
  const cells: { x: number; y: number }[] = [];
  for (let y = 1; y <= GRID_ROWS; y++) {
    for (let x = 1; x <= GRID_COLUMNS; x++) {
      cells.push({ x, y });
    }
  }
  return cells;
}

// 실좌표 모드(RealHexBoard)와 휴리스틱 모드(HeuristicHexBoard)가 함께 쓰는
// 7x4 배경 격자. 자체 grid-template으로 고정 픽셀 크기를 가지므로, 부모가
// 오버레이 grid일 때 트랙 크기를 이 크기로 결정짓는 용도로도 쓸 수 있다.
function HexGridBackdrop({ className = "" }: { className?: string }) {
  return (
    <div
      aria-hidden="true"
      className={"pointer-events-none grid justify-center gap-3 " + className}
      style={{
        gridTemplateColumns: `repeat(${GRID_COLUMNS}, ${CELL_WIDTH_PX}px)`,
        gridTemplateRows: `repeat(${GRID_ROWS}, auto)`,
      }}
    >
      {buildBackgroundCells().map(({ x, y }) => (
        <EmptyHexCell key={`${x}-${y}`} x={x} y={y} />
      ))}
    </div>
  );
}

// 실좌표 모드: 열 폭이 실제 보드처럼 고정이라(정렬이 핵심) 긴 이름은 두 줄로
// 감싼다(HeuristicHexTile과 달리 nowrap을 쓰지 않음).
function RealHexTile({ champion }: { champion: ChampionInComp }) {
  return (
    <Link
      href={`/items/builds?champion_id=${champion.champion_id}`}
      className="flex w-28 flex-col items-center gap-1 self-start"
      style={cellPlacementStyle(
        champion.cell_x as number,
        champion.cell_y as number,
      )}
    >
      <HexIconWithStar champion={champion} />
      <span className="text-center text-caption text-text-primary">
        {champion.name_kr}
      </span>
      <ItemIconRow
        names={champion.recommended_item_names}
        icons={champion.recommended_item_icons}
        itemIds={champion.recommended_items}
        className="justify-center"
      />
    </Link>
  );
}

function RealHexBoard({ champions }: { champions: ChampionInComp[] }) {
  return (
    <>
      <p className="mb-4 text-caption text-text-secondary">
        op.gg 실제 랭커 배치 좌표를 그대로 반영한 헥스 배치도입니다.
      </p>
      <div
        className="grid justify-center gap-3"
        style={{
          gridTemplateColumns: `repeat(${GRID_COLUMNS}, ${CELL_WIDTH_PX}px)`,
          gridTemplateRows: `repeat(${GRID_ROWS}, auto)`,
        }}
      >
        {buildBackgroundCells().map(({ x, y }) => (
          <EmptyHexCell key={`${x}-${y}`} x={x} y={y} />
        ))}
        {champions.map((champion) => (
          <RealHexTile key={champion.champion_id} champion={champion} />
        ))}
      </div>
    </>
  );
}

export function HexBoard({ champions }: { champions: ChampionInComp[] }) {
  const hasRealPositions =
    champions.length > 0 &&
    champions.every((c) => c.cell_x !== null && c.cell_y !== null);

  return (
    <div className="rounded-card border border-border-default bg-surface-page p-6">
      {hasRealPositions ? (
        <RealHexBoard champions={champions} />
      ) : (
        <HeuristicHexBoard champions={champions} />
      )}
    </div>
  );
}
