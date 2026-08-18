import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { Footer } from "../footer";

describe("Footer", () => {
  it("About 페이지 링크를 노출한다(GNB 대신 푸터에 노출하기로 한 2026-08-07 PM 결정)", () => {
    render(<Footer />);
    const link = screen.getByRole("link", { name: "About" });
    expect(link).toHaveAttribute("href", "/about");
  });

  it("Homepage 링크를 About 앞에 노출한다", () => {
    render(<Footer />);
    const homepageLink = screen.getByRole("link", { name: "Homepage" });
    expect(homepageLink).toHaveAttribute("href", "https://tigrelli.com/");
    expect(homepageLink).toHaveAttribute("target", "_blank");
    expect(homepageLink).toHaveAttribute("rel", "noopener noreferrer");

    const links = screen.getAllByRole("link");
    const homepageIndex = links.indexOf(homepageLink);
    const aboutIndex = links.indexOf(
      screen.getByRole("link", { name: "About" }),
    );
    expect(homepageIndex).toBeLessThan(aboutIndex);
  });

  it("문의 이메일(mailto)과 저작권 표기를 노출한다", () => {
    render(<Footer />);
    const mailLink = screen.getByRole("link", { name: "suraholic@gmail.com" });
    expect(mailLink).toHaveAttribute("href", "mailto:suraholic@gmail.com");
    expect(
      screen.getByText(/TFT Hideout\. All rights reserved\./),
    ).toBeInTheDocument();
  });

  it("모바일 하단 고정 챗봇 바에 가리지 않도록 모바일 전용 하단 여백을 둔다(pb-20 md:pb-0)", () => {
    render(<Footer />);
    const footer = screen.getByRole("contentinfo");
    expect(footer.className).toContain("pb-20");
    expect(footer.className).toContain("md:pb-0");
  });
});
