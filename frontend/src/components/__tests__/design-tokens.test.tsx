import { describe, expect, it, vi } from "vitest";
import { readFileSync } from "node:fs";
import path from "node:path";
import { render, screen } from "@testing-library/react";
import { Gnb } from "../gnb";

vi.mock("next/navigation", () => ({
  usePathname: () => "/",
  useRouter: () => ({
    push: vi.fn(),
    replace: vi.fn(),
    prefetch: vi.fn(),
  }),
}));

// WBS FE-01 테스트 요구사항: 디자인 토큰 색상값 매칭 확인
// 근거: /docs/reference/design-tokens.md 컬러 표

const globalsCss = readFileSync(
  path.resolve(__dirname, "../../app/globals.css"),
  "utf-8",
);

const EXPECTED_COLOR_TOKENS: Record<string, string> = {
  "--color-primary": "#4059d9",
  "--color-accent-carry": "#e59933",
  "--color-text-primary": "#1a1a1a",
  "--color-text-secondary": "#666666",
  "--color-text-tertiary": "#8c8c8c",
  "--color-surface-card": "#ffffff",
  "--color-surface-page": "#f7f7f7",
  "--color-surface-user-bubble": "#e5e8ff",
  "--color-border-default": "#d9d9d9",
  "--color-border-input": "#cccccc",
};

describe("디자인 토큰(design-tokens.md) 색상값 매칭", () => {
  it.each(Object.entries(EXPECTED_COLOR_TOKENS))(
    "%s 토큰이 디자인가이드 HEX 값과 일치한다",
    (token, expectedHex) => {
      const pattern = new RegExp(`${token}:\\s*${expectedHex}\\s*;`, "i");
      expect(globalsCss).toMatch(pattern);
    },
  );

  it("Gnb는 토큰 기반 클래스(text-primary, bg-surface-card, border-border-default)를 사용한다", () => {
    render(<Gnb />);
    const logo = screen.getByRole("link", { name: "TFT Hideout" });
    const header = logo.closest("header");
    expect(header?.className).toContain("bg-surface-card");
    expect(header?.className).toContain("border-border-default");
    expect(logo.className).toContain("text-primary");
  });
});
