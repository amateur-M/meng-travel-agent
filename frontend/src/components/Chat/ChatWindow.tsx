import { useEffect, useRef } from "react";
import { motion } from "framer-motion";
import { HeartHandshake } from "lucide-react";
import type { ChatMessage } from "../../types/chat";

interface ChatWindowProps {
  messages: ChatMessage[];
  sending: boolean;
}

export function ChatWindow({ messages, sending }: ChatWindowProps) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages]);

  return (
    <div className="flex-1 overflow-y-auto px-4 py-4 sm:px-6">
      <div className="mx-auto flex max-w-2xl flex-col gap-3">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center pt-12 text-center">
            <div className="flex h-14 w-14 items-center justify-center rounded-full bg-blush-50 text-blush-500">
              <HeartHandshake className="h-7 w-7" />
            </div>
            <p className="mt-4 text-sm text-ink-400">
              开始和旅行助手聊天吧
            </p>
          </div>
        )}

        {messages.map((msg, index) => (
          <motion.div
            key={index}
            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.25 }}
          >
            {msg.role === "assistant" && (
              <div className="mr-2 mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-blush-500 text-white">
                <HeartHandshake className="h-4 w-4" />
              </div>
            )}
            <div
              className={`max-w-[78%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
                msg.role === "user"
                  ? "bg-blush-500 text-white"
                  : "bg-white text-ink-900 shadow-soft border border-cream-100"
              }`}
            >
              {msg.content}
            </div>
          </motion.div>
        ))}

        {sending && (
          <div className="flex justify-start">
            <div className="mr-2 mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-blush-500 text-white">
              <HeartHandshake className="h-4 w-4" />
            </div>
            <div className="flex items-center gap-1 rounded-2xl bg-white px-4 py-3 shadow-soft border border-cream-100">
              <span className="h-2 w-2 animate-bounce rounded-full bg-blush-300" />
              <span
                className="h-2 w-2 animate-bounce rounded-full bg-blush-300"
                style={{ animationDelay: "0.15s" }}
              />
              <span
                className="h-2 w-2 animate-bounce rounded-full bg-blush-300"
                style={{ animationDelay: "0.3s" }}
              />
            </div>
          </div>
        )}

        <div ref={endRef} />
      </div>
    </div>
  );
}
