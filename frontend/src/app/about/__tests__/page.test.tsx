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

  it("개발자 홈페이지(tigrelli.com) 링크를 포함한다", () => {
    render(<AboutPage />);
    const homepageLink = screen.getByRole("link", { name: "tigrelli.com" });
    expect(homepageLink).toHaveAttribute("href", "https://tigrelli.com/");
    expect(homepageLink).toHaveAttribute("target", "_blank");
    expect(homepageLink).toHaveAttribute("rel", "noopener noreferrer");
  });
});
