"use client";

import { useState, type FormEvent } from "react";

// FE-12: policies.md 13번 — 회원가입/로그인이 아닌 단일 공유 비밀번호 게이트.
export function KpiPasswordGate({
  onSubmit,
  errorMessage,
  isSubmitting,
}: {
  onSubmit: (password: string) => void;
  errorMessage: string | null;
  isSubmitting: boolean;
}) {
  const [password, setPassword] = useState("");

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSubmit(password);
  }

  return (
    <div className="mx-auto flex max-w-sm flex-col gap-4">
      <h1 className="text-display text-text-primary">KPI 대시보드</h1>
      <form onSubmit={handleSubmit} className="flex flex-col gap-3">
        <label
          htmlFor="kpi-password"
          className="text-body text-text-secondary"
        >
          비밀번호
        </label>
        <input
          id="kpi-password"
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          className="rounded-control border border-border-input px-3 py-2 text-body text-text-primary"
          autoFocus
        />
        {errorMessage && (
          <p role="alert" className="text-body text-text-secondary">
            {errorMessage}
          </p>
        )}
        <button
          type="submit"
          disabled={isSubmitting}
          className="rounded-control bg-primary px-5 py-3 text-body text-text-on-brand disabled:opacity-60"
        >
          {isSubmitting ? "확인 중..." : "확인"}
        </button>
      </form>
    </div>
  );
}
