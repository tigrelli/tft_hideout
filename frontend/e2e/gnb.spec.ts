import { test, expect } from "@playwright/test";

// WBS FE-02 테스트 요구사항: Playwright 스모크(클릭 시 드로어 오픈)
test("모바일에서 햄버거 버튼을 누르면 전체화면 드로어가 열린다", async ({
  page,
}) => {
  await page.goto("/");

  await expect(
    page.getByRole("dialog", { name: "모바일 메뉴" }),
  ).not.toBeVisible();

  await page.getByRole("button", { name: "메뉴 열기" }).click();

  const drawer = page.getByRole("dialog", { name: "모바일 메뉴" });
  await expect(drawer).toBeVisible();
  await expect(drawer.getByRole("link", { name: "아이템 빌드" })).toBeVisible();

  await page.getByRole("button", { name: "메뉴 닫기" }).click();
  await expect(drawer).not.toBeVisible();
});
