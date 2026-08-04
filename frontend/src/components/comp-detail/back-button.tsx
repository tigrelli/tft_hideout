import Link from "next/link";
import { PatchBadge } from "@/components/tierlist/patch-badge";

// 화면설계서 2.2: BackButton `back-btn`, 뒤로가기 -> 티어리스트로 복귀.
export function BackButton({ patchVersion }: { patchVersion: string | null }) {
  return (
    <div className="mb-4 flex items-center justify-between">
      <Link
        href="/"
        className="text-body text-text-secondary hover:text-primary"
      >
        ← 뒤로
      </Link>
      <PatchBadge version={patchVersion} />
    </div>
  );
}
