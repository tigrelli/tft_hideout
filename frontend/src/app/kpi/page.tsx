"use client";

import { useEffect, useState } from "react";
import { ApiError, fetchJson } from "@/lib/api-client";
import type { KpiAuthResponse, KpiSummaryResponse } from "@/types/kpi";
import { KpiPasswordGate } from "@/components/kpi/kpi-password-gate";
import { KpiSummaryGrid } from "@/components/kpi/kpi-summary-grid";

// FE-12: policies.md 13번 — GNB·모바일 드로어에 노출하지 않고 URL을 아는 사람만
// 접근하는 내부 전용 화면. 로그인/회원 시스템이 아니라 발급된 토큰을 컴포넌트
// 상태로만 들고 있고 별도로 영속화하지 않는다(새로고침하면 다시 게이트 통과).
export default function KpiDashboardPage() {
  const [token, setToken] = useState<string | null>(null);
  const [authError, setAuthError] = useState<string | null>(null);
  const [isAuthenticating, setIsAuthenticating] = useState(false);
  const [summary, setSummary] = useState<KpiSummaryResponse | null>(null);
  const [summaryError, setSummaryError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    fetchJson<KpiSummaryResponse>("/api/v1/kpi/summary", {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then((data) => {
        if (cancelled) return;
        setSummary(data);
        setSummaryError(null);
      })
      .catch((error) => {
        if (cancelled) return;
        if (error instanceof ApiError && error.status === 401) {
          setToken(null);
          setSummary(null);
          return;
        }
        setSummaryError("지표를 불러오지 못했습니다.");
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  async function handlePasswordSubmit(password: string) {
    setIsAuthenticating(true);
    setAuthError(null);
    try {
      const { token: issuedToken } = await fetchJson<KpiAuthResponse>(
        "/api/v1/kpi/auth",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ password }),
        },
      );
      setToken(issuedToken);
    } catch (error) {
      setAuthError(
        error instanceof ApiError && error.status === 401
          ? "비밀번호가 올바르지 않습니다."
          : "인증 요청에 실패했습니다.",
      );
    } finally {
      setIsAuthenticating(false);
    }
  }

  if (!token) {
    return (
      <KpiPasswordGate
        onSubmit={handlePasswordSubmit}
        errorMessage={authError}
        isSubmitting={isAuthenticating}
      />
    );
  }

  return (
    <div>
      <h1 className="text-display text-text-primary">KPI 대시보드</h1>
      {summaryError && (
        <p className="mt-4 text-body text-text-secondary">{summaryError}</p>
      )}
      {!summaryError && !summary && (
        <p className="mt-4 text-body text-text-secondary">불러오는 중...</p>
      )}
      {!summaryError && summary && (
        <div className="mt-6">
          <KpiSummaryGrid summary={summary} />
        </div>
      )}
    </div>
  );
}
