// 화면설계서 2.1 컴포넌트 표: Badge `patch-badge` {"label":"현재 패치 버전"}
export function PatchBadge({ version }: { version: string | null }) {
  return (
    <span className="rounded-badge bg-primary px-3 py-1 text-label text-text-on-brand">
      {version ? `패치 ${version}` : "패치 정보 불러오는 중"}
    </span>
  );
}
