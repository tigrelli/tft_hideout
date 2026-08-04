// 임시 레이아웃 셸. 실제 GNB(드롭다운/드로어 인터랙션 등)는 FE-02에서 구현한다.
// 여기서는 FE-01 스캐폴딩 DoD("기본 레이아웃 렌더링 확인")를 위해
// Tailwind 브레이크포인트 배선과 디자인 토큰 클래스 연결만 확인한다.
export function HeaderShell() {
  return (
    <header className="border-b border-border-default bg-surface-card">
      <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4 md:px-10">
        <span className="text-h1 text-primary">TFT Hideout</span>
        <nav className="hidden items-center gap-6 text-body text-text-secondary md:flex">
          <span>티어리스트</span>
          <span>아이템 빌드</span>
          <span>증강체 정보</span>
        </nav>
        <button type="button" className="md:hidden" aria-label="메뉴 열기">
          ☰
        </button>
      </div>
    </header>
  );
}
