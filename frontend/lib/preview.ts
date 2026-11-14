/** Public, non-secret build flag. Rebuild when switching modes. Off by default. */
export const DEMO_MODE = process.env.NEXT_PUBLIC_LEGAL_BRAIN_DEMO === "true";

export const DEMO_PROMPT = "مثال خيالي للعرض: ترغب شركة المدار التجريبية وشركة الأفق التجريبية في توثيق تعاون افتراضي. لا توجد أطراف أو معاملات حقيقية.";
export const DEMO_QUESTION = "اعرض مثالاً خيالياً لطريقة عرض الإجابة، دون إبداء رأي قانوني.";
