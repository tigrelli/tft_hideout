"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import { NAV_ITEMS } from "@/lib/nav-items";

// 디자인가이드 6.1: 데스크톱/태블릿은 가로 메뉴, 모바일(<768px)은 로고+햄버거만
// 노출하고 탭 시 전체화면 드로어로 전환한다. 태블릿과 데스크톱은 동일한 구조를
// 공유하므로 Tailwind 기본 브레이크포인트(md:768) 하나로 3단계 반응형을 표현한다.
export function Gnb() {
  const pathname = usePathname();
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);

  return (
    <header className="border-b border-border-default bg-surface-card">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4 md:px-10">
        <Link href="/" className="text-h1 text-primary">
          TFT Hideout
        </Link>

        <nav
          aria-label="주요 메뉴"
          className="hidden items-center gap-6 text-body md:flex"
        >
          {NAV_ITEMS.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              aria-current={pathname === item.href ? "page" : undefined}
              className={
                pathname === item.href
                  ? "font-bold text-text-primary"
                  : "text-text-secondary"
              }
            >
              {item.label}
            </Link>
          ))}
        </nav>

        <button
          type="button"
          className="md:hidden"
          aria-label="메뉴 열기"
          aria-expanded={isDrawerOpen}
          aria-controls="mobile-nav-drawer"
          onClick={() => setIsDrawerOpen(true)}
        >
          ☰
        </button>
      </div>

      {isDrawerOpen && (
        <div
          id="mobile-nav-drawer"
          role="dialog"
          aria-modal="true"
          aria-label="모바일 메뉴"
          className="fixed inset-0 z-50 bg-surface-card md:hidden"
        >
          <div className="flex h-14 items-center justify-between px-4">
            <span className="text-h1 text-primary">TFT Hideout</span>
            <button
              type="button"
              aria-label="메뉴 닫기"
              onClick={() => setIsDrawerOpen(false)}
            >
              ✕
            </button>
          </div>
          <nav
            aria-label="모바일 주요 메뉴"
            className="flex flex-col gap-2 px-4 py-2"
          >
            {NAV_ITEMS.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                aria-current={pathname === item.href ? "page" : undefined}
                onClick={() => setIsDrawerOpen(false)}
                className={
                  "py-3 text-body " +
                  (pathname === item.href
                    ? "font-bold text-text-primary"
                    : "text-text-secondary")
                }
              >
                {item.label}
              </Link>
            ))}
          </nav>
        </div>
      )}
    </header>
  );
}
