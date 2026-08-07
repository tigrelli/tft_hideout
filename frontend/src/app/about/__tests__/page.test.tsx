import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import AboutPage from "@/app/about/page";

describe("AboutPage — 소개 페이지", () => {
  it("제목과 소개 본문을 렌더링한다", () => {
    render(<AboutPage />);
    expect(screen.getByRole("heading", { name: "About" })).toBeInTheDocument();
    expect(screen.getAllByText(/op\.gg/).length).toBeGreaterThan(0);
    expect(screen.getByText(/DDragon/)).toBeInTheDocument();
  });

  it("op.gg/tft의 복잡한 UI 때문에 만들었다는 동기를 포함한다", () => {
    render(<AboutPage />);
    expect(screen.getByText(/op\.gg\/tft/)).toBeInTheDocument();
  });

  it("문의 이메일(mailto)과 저작권 표기를 포함한다", () => {
    render(<AboutPage />);
    const mailLink = screen.getByRole("link", { name: "suraholic@gmail.com" });
    expect(mailLink).toHaveAttribute("href", "mailto:suraholic@gmail.com");
    expect(
      screen.getByText(/TFT Hideout\. All rights reserved\./),
    ).toBeInTheDocument();
  });
});
