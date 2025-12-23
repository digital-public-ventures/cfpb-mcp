import { describe, expect, it } from "vitest";
import { callRpc } from "../helpers/http.js";
import { extractPayload } from "../helpers/mcp.js";

const SERVER_URL = process.env.TEST_SERVER_URL ?? "http://127.0.0.1:8787/mcp";

describe("search_complaints", () => {
  it("returns hits and citations", async () => {
    const result = await callRpc(SERVER_URL, "tools/call", {
      name: "search_complaints",
      arguments: {
        search_term: "forbearance",
        field: "complaint_what_happened",
        size: 1,
        from_index: 0,
        sort: "relevance_desc",
        no_highlight: true,
      },
    });
    const payload = extractPayload(result);
    expect(payload.data).toBeTruthy();
    expect(payload.citations).toBeTruthy();
    const hits = payload.data?.hits?.hits ?? [];
    expect(Array.isArray(hits)).toBe(true);
    expect(hits.length).toBeGreaterThan(0);
  });
});
