import { afterEach, describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { FallbackImage } from "@/components/common/fallback-image";

// FE-19: 외부 이미지(Community Dragon) 로드 실패 시 폴백으로 대체해 레이아웃이
// 깨지지 않는지 검증한다(2026-11-13 CDragon 원본 522 장애 때 alt 텍스트가
// 24px 상자 안에서 세로로 쌓이던 문제).
const fallback = <span data-testid="fallback">무</span>;

describe("FallbackImage", () => {
  afterEach(() => {
    // "이미 실패한 이미지" 테스트에서 덮어쓴 속성을 원래대로 되돌린다.
    delete (HTMLImageElement.prototype as { complete?: boolean }).complete;
    delete (HTMLImageElement.prototype as { naturalWidth?: number })
      .naturalWidth;
  });

  it("주소가 있으면 이미지를 렌더링한다", () => {
    render(
      <FallbackImage
        src="https://x.invalid/ie.png"
        alt="무한의 대검"
        width={24}
        height={24}
        fallback={fallback}
      />,
    );

    expect(screen.getByAltText("무한의 대검")).toBeInTheDocument();
    expect(screen.queryByTestId("fallback")).not.toBeInTheDocument();
  });

  it("주소가 없으면 폴백을 렌더링한다", () => {
    render(
      <FallbackImage
        src={null}
        alt="무한의 대검"
        width={24}
        height={24}
        fallback={fallback}
      />,
    );

    expect(screen.queryByAltText("무한의 대검")).not.toBeInTheDocument();
    expect(screen.getByTestId("fallback")).toBeInTheDocument();
  });

  it("이미지 로드에 실패하면 폴백으로 바뀐다", () => {
    render(
      <FallbackImage
        src="https://x.invalid/ie.png"
        alt="무한의 대검"
        width={24}
        height={24}
        fallback={fallback}
      />,
    );

    fireEvent.error(screen.getByAltText("무한의 대검"));

    expect(screen.queryByAltText("무한의 대검")).not.toBeInTheDocument();
    expect(screen.getByTestId("fallback")).toBeInTheDocument();
  });

  it("실패 후 주소가 바뀌면 다시 이미지를 시도한다", () => {
    const { rerender } = render(
      <FallbackImage
        src="https://x.invalid/a.png"
        alt="아이템"
        width={24}
        height={24}
        fallback={fallback}
      />,
    );
    fireEvent.error(screen.getByAltText("아이템"));
    expect(screen.getByTestId("fallback")).toBeInTheDocument();

    rerender(
      <FallbackImage
        src="https://x.invalid/b.png"
        alt="아이템"
        width={24}
        height={24}
        fallback={fallback}
      />,
    );

    expect(screen.getByAltText("아이템")).toBeInTheDocument();
    expect(screen.queryByTestId("fallback")).not.toBeInTheDocument();
  });

  it("하이드레이션 전에 이미 실패한 이미지도 폴백으로 바꾼다", () => {
    // 서버 렌더링된 <img>가 React 이벤트 연결 전에 실패하면 onError가 다시
    // 불리지 않는다 — 마운트 시점에 complete && naturalWidth === 0이면 실패로 본다.
    Object.defineProperty(HTMLImageElement.prototype, "complete", {
      configurable: true,
      get: () => true,
    });
    Object.defineProperty(HTMLImageElement.prototype, "naturalWidth", {
      configurable: true,
      get: () => 0,
    });

    render(
      <FallbackImage
        src="https://x.invalid/ie.png"
        alt="무한의 대검"
        width={24}
        height={24}
        fallback={fallback}
      />,
    );

    expect(screen.getByTestId("fallback")).toBeInTheDocument();
  });
});
