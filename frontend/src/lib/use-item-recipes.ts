"use client";

import { useEffect, useState } from "react";
import { fetchJson } from "@/lib/api-client";
import type { ItemsResponse, ItemSummary } from "@/types/catalog";

// 한 페이지에 ItemIconRow가 여러 개 떠도 GET /catalog/items는 한 번만
// 호출되도록 모듈 스코프에 fetch 결과를 캐시한다(재료/아이콘은 패치당 고정값).
let cachedPromise: Promise<Map<string, ItemSummary>> | null = null;

function loadRecipes(): Promise<Map<string, ItemSummary>> {
  if (!cachedPromise) {
    cachedPromise = fetchJson<ItemsResponse>("/api/v1/catalog/items")
      .then(
        (data) => new Map(data.items.map((item) => [item.riot_item_id, item])),
      )
      .catch((error: unknown) => {
        cachedPromise = null; // 실패 시 다음 마운트에서 재시도할 수 있게 캐시 해제
        throw error;
      });
  }
  return cachedPromise;
}

// 아이템 레시피(조합 재료) 조회 훅. 실패해도 조용히 빈 맵을 유지한다 — 이
// 기능은 호버/탭 시 재료를 보여주는 부가 기능이라, 실패했다고 아이템 아이콘
// 표시 자체(기존 기능)까지 막으면 안 된다.
export function useItemRecipes(): Map<string, ItemSummary> {
  const [recipes, setRecipes] = useState<Map<string, ItemSummary>>(new Map());

  useEffect(() => {
    let cancelled = false;
    loadRecipes()
      .then((map) => {
        if (!cancelled) {
          setRecipes(map);
        }
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  return recipes;
}
