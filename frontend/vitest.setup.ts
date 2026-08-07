import "@testing-library/jest-dom/vitest";

// jsdom은 scrollIntoView를 구현하지 않아(알려진 한계) 호출하는 컴포넌트가
// 있으면 "not a function"으로 테스트가 깨진다 — 채팅 자동 스크롤(2026-08-07)
// 테스트를 위한 최소 폴리필.
if (!window.HTMLElement.prototype.scrollIntoView) {
  window.HTMLElement.prototype.scrollIntoView = () => {};
}
