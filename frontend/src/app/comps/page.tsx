import { Suspense } from "react";
import { CompDetailView } from "@/components/comp-detail/comp-detail-view";

export default function CompDetailPage() {
  return (
    <Suspense
      fallback={
        <p className="text-body text-text-secondary">
          불러오는 중입니다. 무료 호스팅 특성상 처음 접속 시 다소 시간이 걸릴 수
          있습니다.
        </p>
      }
    >
      <CompDetailView />
    </Suspense>
  );
}
