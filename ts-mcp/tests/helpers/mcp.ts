type TextContentItem = {
  type: "text";
  text: string;
};

type ToolResultLike = {
  structuredContent?: unknown;
  content?: unknown;
};

const isTextContentItem = (item: unknown): item is TextContentItem => {
  if (!item || typeof item !== "object") {
    return false;
  }
  const record = item as { type?: unknown; text?: unknown };
  return record.type === "text" && typeof record.text === "string";
};

export const extractPayload = (result: unknown): unknown => {
  if (result && typeof result === "object") {
    const typed = result as ToolResultLike;
    if (typed.structuredContent) {
      return typed.structuredContent;
    }
    if (Array.isArray(typed.content)) {
      const text = typed.content
        .filter(isTextContentItem)
        .map((item) => item.text)
        .join("\n")
        .trim();
      if (!text) {
        return result;
      }
      try {
        return JSON.parse(text);
      } catch {
        return text;
      }
    }
  }
  return result;
};
