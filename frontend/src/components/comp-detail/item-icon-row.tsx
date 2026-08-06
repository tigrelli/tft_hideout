"use client";

import { useRef, useState } from "react";
import Image from "next/image";
import { useItemRecipes } from "@/lib/use-item-recipes";

// 챔피언 밑에 추천 아이템을 텍스트 대신 이미지로 보여준다(PM 요청 2026-08-06).
// 아이콘이 없는 아이템(square_icon_url null)은 이름 첫 글자 폴백 타일로 대체한다.
// 완성 아이템(재료 2개 이상)은 데스크톱 hover·모바일 tap 시 조합 재료를
// 이미지+이름으로 보여주는 팝오버가 뜬다(PM 요청 2026-08-06).
export function ItemIconRow({
  names,
  icons,
  itemIds = [],
  className = "",
  size = 24,
}: {
  names: string[];
  icons: (string | null)[];
  itemIds?: string[];
  className?: string;
  size?: number;
}) {
  const recipes = useItemRecipes();
  // 데스크톱 hover와 모바일 tap(클릭)을 별도 상태로 추적한다 — 클릭이 hover가
  // 이미 열어둔 것과 같은 상태를 다시 토글해 즉시 닫혀버리는 문제를 피하기
  // 위함(마우스 클릭 시 브라우저가 클릭 직전에 mouseenter도 함께 쏘기 때문).
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);
  const [pinnedIndex, setPinnedIndex] = useState<number | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  if (names.length === 0) {
    return null;
  }

  return (
    <div
      ref={containerRef}
      className={`mt-1 flex flex-wrap gap-1 ${className}`}
      aria-label={`추천 아이템 ${names.join(", ")}`}
    >
      {names.map((name, index) => {
        const recipe = itemIds[index] ? recipes.get(itemIds[index]) : undefined;
        const components = recipe?.components ?? [];
        const hasRecipe = components.length > 0;
        const isActive = hoveredIndex === index || pinnedIndex === index;

        return (
          <div key={`${name}-${index}`} className="relative">
            {/* item-combo-list.tsx의 행 자체가 <button>이라(빌드 선택) HTML은
                버튼을 중첩할 수 없다 — role="button"으로 대체하고 클릭 이벤트는
                stopPropagation으로 부모 버튼(빌드 선택)까지 안 번지게 막는다. */}
            <span
              role="button"
              tabIndex={hasRecipe ? 0 : -1}
              onMouseEnter={() => hasRecipe && setHoveredIndex(index)}
              onMouseLeave={() =>
                setHoveredIndex((i) => (i === index ? null : i))
              }
              onClick={(event) => {
                if (!hasRecipe) return;
                event.stopPropagation();
                setPinnedIndex((i) => (i === index ? null : index));
              }}
              onKeyDown={(event) => {
                if (!hasRecipe) return;
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  event.stopPropagation();
                  setPinnedIndex((i) => (i === index ? null : index));
                }
              }}
              onBlur={(event) => {
                if (
                  !event.currentTarget.contains(event.relatedTarget as Node)
                ) {
                  setPinnedIndex((i) => (i === index ? null : i));
                }
              }}
              className={
                "inline-block " +
                (hasRecipe ? "cursor-pointer" : "cursor-default")
              }
            >
              {icons[index] ? (
                <Image
                  src={icons[index] as string}
                  alt={name}
                  width={size}
                  height={size}
                  className="rounded-sm border border-border-default object-cover"
                />
              ) : (
                <span
                  title={name}
                  style={{ width: size, height: size }}
                  className="flex items-center justify-center rounded-sm border border-border-default bg-surface-page text-caption text-text-tertiary"
                >
                  {name.slice(0, 1)}
                </span>
              )}
            </span>

            {isActive && hasRecipe && (
              <div
                role="tooltip"
                className="absolute bottom-full left-1/2 z-20 mb-2 w-max max-w-72 -translate-x-1/2 rounded-control border border-border-default bg-surface-card p-3 shadow-md"
              >
                <div className="flex gap-2">
                  {components.map((component, componentIndex) => (
                    <span
                      key={`${component.riot_item_id}-${componentIndex}`}
                      title={component.name_kr}
                    >
                      {component.square_icon_url ? (
                        <Image
                          src={component.square_icon_url}
                          alt={component.name_kr}
                          width={32}
                          height={32}
                          className="rounded-sm border border-border-default object-cover"
                        />
                      ) : (
                        <span className="flex h-8 w-8 items-center justify-center rounded-sm border border-border-default bg-surface-page text-caption text-text-tertiary">
                          {component.name_kr.slice(0, 1)}
                        </span>
                      )}
                    </span>
                  ))}
                </div>
                <p className="mt-1.5 whitespace-nowrap text-body text-text-secondary">
                  {components.map((c) => c.name_kr).join(" + ")}
                </p>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
