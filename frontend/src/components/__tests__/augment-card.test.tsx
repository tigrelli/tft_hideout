import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { AugmentCard } from "@/components/augments/augment-card";
import type { AugmentSummary } from "@/types/catalog";

const baseAugment: AugmentSummary = {
  id: 1,
  name_kr: "일급 재사공",
  name_en: "First Class Rerolls",
  tier: "gold",
  description: "재사공 확률 대폭 증가",
  is_legend_related: false,
  win_rate: 0.48,
  related_comp_ids: [],
  image_url: "https://x.invalid/augment.png",
};

// WBS FE-06 필수·정책 테스트: is_legend_related=true 카드는 "승률 표시 안함"
// 텍스트만 렌더링되고, 승률 숫자가 DOM 어디에도 없어야 한다(policies.md 1번,
// PRD 10-1·12장).
describe("AugmentCard — Legend 승률 비노출 정책", () => {
  it("is_legend_related=true면 '승률 표시 안함'만 보이고 승률 숫자는 DOM에 없다", () => {
    const legendAugment: AugmentSummary = {
      ...baseAugment,
      id: 2,
      name_kr: "전설: 용의 시대",
      is_legend_related: true,
      win_rate: 0.55, // 백엔드가 null로 강제하지만, 프론트가 실수로 노출하지
      // 않는지 방어적으로 값이 있는 상태로도 검증한다.
      related_comp_ids: [],
    };
    render(<AugmentCard augment={legendAugment} />);

    expect(screen.getByText(/승률 표시 안함/)).toBeInTheDocument();
    expect(screen.queryByText(/55%/)).not.toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/\d+%/);
  });

  it("is_legend_related=false면 승률을 정상 표시한다", () => {
    render(<AugmentCard augment={baseAugment} />);
    expect(screen.getByText(/승률 48%/)).toBeInTheDocument();
    expect(screen.queryByText(/승률 표시 안함/)).not.toBeInTheDocument();
  });

  it("win_rate가 null(Legend 아님)이면 '승률 정보 없음'을 표시한다", () => {
    render(<AugmentCard augment={{ ...baseAugment, win_rate: null }} />);
    expect(screen.getByText(/승률 정보 없음/)).toBeInTheDocument();
  });

  it("이름·티어·설명을 렌더링한다", () => {
    render(<AugmentCard augment={baseAugment} />);
    expect(screen.getByText("일급 재사공")).toBeInTheDocument();
    expect(screen.getByText("골드")).toBeInTheDocument();
    expect(screen.getByText("재사공 확률 대폭 증가")).toBeInTheDocument();
  });

  it("image_url이 있으면 대표 이미지를 렌더링한다", () => {
    render(<AugmentCard augment={baseAugment} />);
    const image = screen.getByAltText("일급 재사공");
    // next/image는 next.config.ts images.unoptimized(정적 export 설정)를
    // 개발 빌드에서만 적용하므로 Vitest(jsdom)에서는 /_next/image?url=...
    // 프록시 형태로 렌더링될 수 있다 — 원본 URL 포함 여부만 확인한다.
    expect(decodeURIComponent(image.getAttribute("src") ?? "")).toContain(
      "augment.png",
    );
  });

  it("image_url이 없으면 이름 첫 글자 폴백을 렌더링한다", () => {
    render(<AugmentCard augment={{ ...baseAugment, image_url: null }} />);
    expect(screen.queryByAltText("일급 재사공")).not.toBeInTheDocument();
    expect(screen.getByText("일")).toBeInTheDocument();
  });

  it("related_comp_ids가 있으면 관련 조합 링크를 렌더링한다", () => {
    render(
      <AugmentCard augment={{ ...baseAugment, related_comp_ids: [7, 9] }} />,
    );
    const links = screen.getAllByRole("link", { name: /관련 조합 보기/ });
    expect(links).toHaveLength(2);
    expect(links[0]).toHaveAttribute("href", "/comps?id=7");
    expect(links[1]).toHaveAttribute("href", "/comps?id=9");
  });

  it("related_comp_ids가 비어있으면 관련 조합 링크를 렌더링하지 않는다", () => {
    render(<AugmentCard augment={baseAugment} />);
    expect(
      screen.queryByRole("link", { name: /관련 조합 보기/ }),
    ).not.toBeInTheDocument();
  });

  // DATA-16: 배치가 <br>를 실제 개행(\n)으로 정리해서 내려주므로, 프론트는
  // 그 개행을 whitespace-pre-line으로 그대로 렌더링만 하면 된다.
  it("설명에 개행이 있으면 whitespace-pre-line으로 렌더링한다", () => {
    render(
      <AugmentCard
        augment={{ ...baseAugment, description: "첫 줄\n\n둘째 줄" }}
      />,
    );
    const description = screen.getByText(
      (_, element) => element?.textContent === "첫 줄\n\n둘째 줄",
    );
    expect(description.className).toContain("whitespace-pre-line");
  });
});
