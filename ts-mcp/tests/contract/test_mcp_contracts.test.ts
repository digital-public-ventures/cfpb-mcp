import { describe, expect, it } from "vitest";
import { callRpc } from "../helpers/http.js";
import { extractPayload } from "../helpers/mcp.js";
import {
  extractCompanyFromDocument,
  extractComplaintIdFromSearch,
} from "./contract_utils.js";

const SERVER_URL = process.env.TEST_SERVER_URL ?? "http://127.0.0.1:8787/mcp";

describe("MCP contracts", () => {
  it("search tool returns a complaint id and document includes company", async () => {
    const tools = await callRpc(SERVER_URL, "tools/list");
    const toolNames = new Set(tools.tools.map((tool: any) => tool.name));
    expect(toolNames.has("search_complaints")).toBe(true);
    expect(toolNames.has("get_complaint_document")).toBe(true);

    const searchResult = await callRpc(SERVER_URL, "tools/call", {
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
    const searchPayload = extractPayload(searchResult);
    const complaintId = extractComplaintIdFromSearch(searchPayload);
    expect(complaintId).not.toBeNull();

    const docResult = await callRpc(SERVER_URL, "tools/call", {
      name: "get_complaint_document",
      arguments: { complaint_id: String(complaintId) },
    });
    const docPayload = extractPayload(docResult);
    const company = extractCompanyFromDocument(docPayload);
    expect(company.length).toBeGreaterThan(0);
  });
});
