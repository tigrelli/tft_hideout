"use client";

import { useCallback, useState } from "react";
import { streamChatMessage } from "@/lib/chat-stream";

export interface ChatMessage {
  id: string;
  role: "user" | "bot";
  text: string;
  // CHAT-11: 이 봇 메시지에 딸린 맥락 기반 후속 질문(SSE `event: followups`).
  // 아직 안 왔거나(스트리밍 중) 백엔드가 생성하지 않은 턴은 undefined.
  followups?: string[];
}

const STREAM_ERROR_MESSAGE =
  "죄송합니다, 일시적인 오류로 답변을 생성하지 못했습니다. 잠시 후 다시 시도해주세요.";

// 화면설계서 2.7 데이터 바인딩: session_id는 클라이언트가 crypto.randomUUID()로
// 발급해 이후 요청에 계속 실어 보낸다(api-spec.md, 회원 식별자 아님).
export function useChatConversation() {
  const [sessionId, setSessionId] = useState(() => crypto.randomUUID());
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isSending, setIsSending] = useState(false);

  const sendMessage = useCallback(
    async (rawText: string) => {
      const text = rawText.trim();
      if (!text || isSending) {
        return;
      }

      const botMessageId = crypto.randomUUID();
      setMessages((prev) => [
        ...prev,
        { id: crypto.randomUUID(), role: "user", text },
        { id: botMessageId, role: "bot", text: "" },
      ]);
      setIsSending(true);

      const tokens: string[] = [];
      try {
        await streamChatMessage(
          sessionId,
          text,
          (token) => {
            tokens.push(token);
            const nextText = tokens.join(" ");
            setMessages((prev) =>
              prev.map((message) =>
                message.id === botMessageId
                  ? { ...message, text: nextText }
                  : message,
              ),
            );
          },
          (questions) => {
            setMessages((prev) =>
              prev.map((message) =>
                message.id === botMessageId
                  ? { ...message, followups: questions }
                  : message,
              ),
            );
          },
        );
      } catch {
        setMessages((prev) =>
          prev.map((message) =>
            message.id === botMessageId
              ? { ...message, text: STREAM_ERROR_MESSAGE }
              : message,
          ),
        );
      } finally {
        setIsSending(false);
      }
    },
    [isSending, sessionId],
  );

  const resetConversation = useCallback(() => {
    setMessages([]);
    setSessionId(crypto.randomUUID());
  }, []);

  return { sessionId, messages, isSending, sendMessage, resetConversation };
}
