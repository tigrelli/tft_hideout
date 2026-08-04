import { Suspense } from "react";
import { CompDetailView } from "@/components/comp-detail/comp-detail-view";

export default function CompDetailPage() {
  return (
    <Suspense
      fallback={<p className="text-body text-text-secondary">불러오는 중...</p>}
    >
      <CompDetailView />
    </Suspense>
  );
}
