"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Image from "next/image";

export interface ChampionOption {
  championId: number;
  nameKr: string;
  squareIconUrl: string | null;
}

// 화면설계서 2.3: Dropdown `filter-champion` {"label":"챔피언 선택"} -> PM 요청
// (2026-08-06)으로 드롭다운 대신 텍스트 입력 자동완성(콤보박스)으로 변경. 값
// 타입(숫자 id)과 onChange 시그니처는 기존과 동일하게 유지해 item-builds-view.tsx
// 쪽 통합 비용을 최소화한다.
export function ChampionSelect({
  champions,
  value,
  onChange,
}: {
  champions: ChampionOption[];
  value: number | null;
  onChange: (championId: number) => void;
}) {
  const selected = useMemo(
    () => champions.find((c) => c.championId === value) ?? null,
    [champions, value],
  );

  const [query, setQuery] = useState(selected?.nameKr ?? "");
  const [isOpen, setIsOpen] = useState(false);
  const [highlightedIndex, setHighlightedIndex] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);

  // 외부에서 선택값이 바뀌면(URL의 champion_id 초기값 등) 입력창 텍스트도
  // 동기화한다. 렌더링 도중 이전 value를 비교해 조정하는 React 공식 권장
  // 패턴(https://react.dev/learn/you-might-not-need-an-effect)을 써서 매
  // 렌더마다 추가 커밋을 만드는 useEffect를 피한다.
  const [prevValue, setPrevValue] = useState(value);
  if (value !== prevValue) {
    setPrevValue(value);
    setQuery(selected?.nameKr ?? "");
  }

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (!containerRef.current?.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // 입력창을 비우거나 다른 텍스트로 고치면(아직 새 챔피언을 선택하지 않은
  // 상태) 이전에 선택했던 챔피언의 아이콘이 그대로 남아있으면 안 된다 —
  // 입력값이 선택된 챔피언 이름과 정확히 일치할 때만 아이콘을 보여준다.
  const showSelectedIcon = selected !== null && query === selected.nameKr;

  const suggestions = useMemo(() => {
    const trimmed = query.trim();
    if (trimmed === "") {
      return champions;
    }
    return champions.filter((c) => c.nameKr.includes(trimmed));
  }, [champions, query]);

  function selectChampion(champion: ChampionOption) {
    onChange(champion.championId);
    setQuery(champion.nameKr);
    setIsOpen(false);
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setIsOpen(true);
      setHighlightedIndex((i) => Math.min(i + 1, suggestions.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setHighlightedIndex((i) => Math.max(i - 1, 0));
    } else if (event.key === "Enter") {
      const champion = suggestions[highlightedIndex];
      if (isOpen && champion) {
        event.preventDefault();
        selectChampion(champion);
      }
    } else if (event.key === "Escape") {
      setIsOpen(false);
    }
  }

  return (
    <div ref={containerRef} className="relative">
      <label className="flex items-center gap-2 text-body text-text-primary">
        챔피언 선택
        <span className="relative flex items-center">
          {showSelectedIcon && (
            <span
              aria-hidden="true"
              className="pointer-events-none absolute left-2 flex h-6 w-6 items-center justify-center overflow-hidden rounded-sm"
            >
              {selected.squareIconUrl ? (
                <Image
                  src={selected.squareIconUrl}
                  alt=""
                  width={24}
                  height={24}
                  className="object-cover"
                />
              ) : (
                <span className="text-caption text-text-tertiary">
                  {selected.nameKr.slice(0, 1)}
                </span>
              )}
            </span>
          )}
          <input
            role="combobox"
            aria-expanded={isOpen}
            aria-controls="champion-autocomplete-listbox"
            aria-autocomplete="list"
            type="text"
            value={query}
            placeholder="챔피언 이름을 입력하세요"
            onChange={(event) => {
              setQuery(event.target.value);
              setIsOpen(true);
              setHighlightedIndex(0);
            }}
            onFocus={() => setIsOpen(true)}
            onKeyDown={handleKeyDown}
            className={
              "rounded-control border border-border-input py-1.5 pr-2 " +
              (showSelectedIcon ? "pl-9" : "pl-2")
            }
          />
        </span>
      </label>

      {isOpen && suggestions.length > 0 && (
        <ul
          id="champion-autocomplete-listbox"
          role="listbox"
          className="absolute z-10 mt-1 max-h-64 w-56 overflow-y-auto rounded-control border border-border-default bg-surface-card shadow-md"
        >
          {suggestions.map((champion, index) => (
            <li
              key={champion.championId}
              role="option"
              aria-selected={index === highlightedIndex}
            >
              <button
                type="button"
                onClick={() => selectChampion(champion)}
                onMouseEnter={() => setHighlightedIndex(index)}
                className={
                  "flex w-full items-center gap-2 px-3 py-2 text-left text-body text-text-primary " +
                  (index === highlightedIndex ? "bg-surface-page" : "")
                }
              >
                <span
                  aria-hidden="true"
                  className="flex h-6 w-6 items-center justify-center overflow-hidden rounded-sm bg-surface-page"
                >
                  {champion.squareIconUrl ? (
                    <Image
                      src={champion.squareIconUrl}
                      alt=""
                      width={24}
                      height={24}
                      className="object-cover"
                    />
                  ) : (
                    <span className="text-caption text-text-tertiary">
                      {champion.nameKr.slice(0, 1)}
                    </span>
                  )}
                </span>
                {champion.nameKr}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
