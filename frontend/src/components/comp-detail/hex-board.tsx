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
const HEX_CLIP =
  "polygon(25% 0%, 75% 0%, 100% 50%, 75% 100%, 25% 100%, 0% 50%)";
const GRID_COLUMNS = 7;
const GRID_ROWS = 4;
const CELL_WIDTH_PX = 96; // w-24
const CELL_GAP_PX = 12; // gap-3

function HexIcon({ champion }: { champion: ChampionInComp }) {
  return (
    <div
      style={{ clipPath: HEX_CLIP }}
      className={
        "h-20 w-24 shrink-0 p-1 " +
        (champion.is_carry ? "bg-accent-carry" : "bg-border-default")
      }
    >
      <div
        style={{ clipPath: HEX_CLIP }}
        className="relative h-full w-full overflow-hidden bg-surface-card"
      >
        {champion.square_icon_url ? (
          <Image
            src={champion.square_icon_url}
            alt={champion.name_kr}
            fill
            sizes="96px"
            className="object-cover"
          />
        ) : (
          <span className="absolute inset-0 flex items-center justify-center text-caption text-text-tertiary">
            {champion.name_kr.slice(0, 2)}
          </span>
        )}
      </div>
    </div>
  );
}

// 휴리스틱 폴백 모드: 이름이 길어도 안 잘리게 타일 너비가 이름에 맞춰 늘어난다.
function HeuristicHexTile({ champion }: { champion: ChampionInComp }) {
  return (
    <Link
      href={`/items/builds?champion_id=${champion.champion_id}`}
      className="flex w-max min-w-24 shrink-0 flex-col items-center gap-1"
    >
      <HexIcon champion={champion} />
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
      <div className="flex flex-col gap-4">
        <HexRow rowChampions={backline} offset={false} />
        <HexRow
          rowChampions={frontline}
          offset={frontline.length <= backline.length}
        />
      </div>
    </>
  );
}

// 실제 TFT 보드는 열이 한 칸씩 어긋난 육각형 타일링이다 — 짝수 행을 반 칸
// (타일 폭+간격의 절반)만큼 오른쪽으로 밀어 벌집 모양을 만든다. 배경 빈 칸과
// 챔피언 타일이 같은 규칙으로 어긋나야 격자선이 실제 타일 위치와 맞는다.
function cellPlacementStyle(x: number, y: number): React.CSSProperties {
  return {
    gridColumnStart: x,
    gridRowStart: y,
    transform:
      y % 2 === 0
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
      className="h-20 w-24 shrink-0 self-start bg-border-default/50 p-px"
    >
      <div
        style={{ clipPath: HEX_CLIP }}
        className="h-full w-full bg-surface-page"
      />
    </div>
  );
}

// 실좌표 모드: 열 폭이 실제 보드처럼 고정이라(정렬이 핵심) 긴 이름은 두 줄로
// 감싼다(HeuristicHexTile과 달리 nowrap을 쓰지 않음).
function RealHexTile({ champion }: { champion: ChampionInComp }) {
  return (
    <Link
      href={`/items/builds?champion_id=${champion.champion_id}`}
      className="flex w-24 flex-col items-center gap-1 self-start"
      style={cellPlacementStyle(
        champion.cell_x as number,
        champion.cell_y as number,
      )}
    >
      <HexIcon champion={champion} />
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
  const backgroundCells = [];
  for (let y = 1; y <= GRID_ROWS; y++) {
    for (let x = 1; x <= GRID_COLUMNS; x++) {
      backgroundCells.push({ x, y });
    }
  }

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
        {backgroundCells.map(({ x, y }) => (
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
