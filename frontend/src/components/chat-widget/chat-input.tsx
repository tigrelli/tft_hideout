"use client";

import { useState, type FormEvent } from "react";

export function ChatInput({
  isSending,
  onSend,
}: {
  isSending: boolean;
  onSend: (text: string) => void;
}) {
  const [value, setValue] = useState("");

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!value.trim() || isSending) {
      return;
    }
    onSend(value);
    setValue("");
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="flex items-center gap-2 border-t border-border-default p-3"
    >
      <input
        type="text"
        aria-label="챗봇 메시지 입력"
        placeholder="TFT에 모든 것을 AI에게 물어보세요"
        value={value}
        disabled={isSending}
        onChange={(event) => setValue(event.target.value)}
        className="flex-1 rounded-control border border-border-input px-3 py-2 text-body text-text-primary disabled:opacity-60"
      />
      <button
        type="submit"
        aria-label="메시지 전송"
        disabled={isSending || !value.trim()}
        className="cursor-pointer rounded-control bg-primary px-4 py-2 text-body text-text-on-brand disabled:cursor-not-allowed disabled:opacity-50"
      >
        {isSending ? "전송 중" : "전송"}
      </button>
    </form>
  );
}
