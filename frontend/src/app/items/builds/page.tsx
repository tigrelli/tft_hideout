import { Suspense } from "react";
import { ItemBuildsView } from "@/components/item-builds/item-builds-view";

export default function ItemBuildsPage() {
  return (
    <Suspense
      fallback={<p className="text-body text-text-secondary">불러오는 중...</p>}
    >
      <ItemBuildsView />
    </Suspense>
  );
}
