import type { Metadata } from "next";
import type { ReactNode } from "react";

// policies.md 13번: GNB·드로어에 노출하지 않는 내부 전용 화면 — 검색엔진 색인도
// 막아 URL을 아는 사람만 접근하는 전제를 지킨다.
export const metadata: Metadata = {
  title: "KPI 대시보드 | TFT Hideout",
  robots: { index: false, follow: false },
};

export default function KpiLayout({ children }: { children: ReactNode }) {
  return <>{children}</>;
}
