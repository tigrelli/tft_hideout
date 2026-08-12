import Link from "next/link";

// 소개(About) 페이지 진입 링크 노출 위치를 GNB(IA v1.2 고정 4개 진입점)가
// 아닌 푸터로 결정(2026-08-07 PM 결정, GNB 문서 구조는 그대로 유지). 모바일은
// 챗봇 위젯이 화면 하단에 항상 fixed로 떠 있어(chat-widget.tsx) 일반 흐름
// 콘텐츠인 푸터를 그대로 두면 스크롤을 끝까지 내려도 챗봇 바에 가려지므로,
// 그 바 높이만큼 모바일 전용 하단 여백을 둔다(md 이상은 챗봇이 우하단
// 원형 버튼으로 바뀌어 전체 폭을 가리지 않으므로 불필요).
export function Footer() {
  return (
    <footer className="border-t border-border-default bg-surface-card pb-20 md:pb-0">
      <div className="mx-auto flex max-w-6xl flex-col gap-2 px-4 py-6 text-caption text-text-secondary md:px-10">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1">
          <a
            href="https://tigrelli.com/"
            target="_blank"
            rel="noopener noreferrer"
            className="hover:text-text-primary"
          >
            Homepage
          </a>
          <span aria-hidden="true">·</span>
          <Link href="/about" className="hover:text-text-primary">
            About
          </Link>
          <span aria-hidden="true">·</span>
          <span>
            문의:{" "}
            <a
              href="mailto:suraholic@gmail.com"
              className="hover:text-text-primary"
            >
              suraholic@gmail.com
            </a>
          </span>
        </div>
        <p>&copy; 2026 TFT Hideout. All rights reserved.</p>
      </div>
    </footer>
  );
}
