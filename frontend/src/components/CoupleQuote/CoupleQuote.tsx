import { motion } from "framer-motion";
import { Heart } from "lucide-react";

interface CoupleQuoteProps {
  text: string;
  label?: string;
}

/**
 * 情侣共情文案气泡，使用手写字体并以淡入动画呈现。
 */
export function CoupleQuote({ text, label = "今日寄语" }: CoupleQuoteProps) {
  return (
    <motion.figure
      className="relative rounded-lg border border-blush-100 bg-blush-50 px-5 py-4 shadow-soft"
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.55, ease: "easeOut" }}
    >
      <figcaption className="mb-2 flex items-center gap-1.5 text-xs font-medium text-blush-500">
        <Heart className="h-3.5 w-3.5 fill-current" />
        {label}
      </figcaption>
      <blockquote className="font-hand text-lg leading-8 text-ink-700">
        {text}
      </blockquote>
    </motion.figure>
  );
}
