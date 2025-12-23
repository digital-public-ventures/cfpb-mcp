export const extractPayload = (result: any): any => {
  if (result?.structuredContent) {
    return result.structuredContent;
  }
  if (!Array.isArray(result?.content)) {
    return result;
  }
  const text = result.content
    .filter((item: any) => item?.type === "text")
    .map((item: any) => item.text)
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
};
