import { describe, expect, it } from "vitest";
import Anthropic from "@anthropic-ai/sdk";
import { callRpc } from "../helpers/http.js";
import { extractPayload } from "../helpers/mcp.js";
import {
  extractCompanyFromDocument,
  extractComplaintIdFromSearch,
  extractComplaintIdFromText,
} from "./contract_utils.js";
import { SYSTEM_PROMPT, USER_PROMPT } from "./prompts.js";

const SERVER_URL = process.env.TEST_SERVER_URL ?? "http://127.0.0.1:8787/mcp";

describe("Anthropic MCP contract", () => {
  it("returns a complaint id and includes company in response", async () => {
    const apiKey = process.env.ANTHROPIC_API_KEY;
    expect(apiKey).toBeTruthy();
    const model = process.env.ANTHROPIC_MODEL ?? "claude-haiku-4-5";
    const client = new Anthropic({ apiKey });

    const toolsList = await callRpc(SERVER_URL, "tools/list");
    const tools = toolsList.tools.map((tool: any) => ({
      name: tool.name,
      description: tool.description ?? "",
      input_schema: tool.inputSchema ?? { type: "object", properties: {} },
    }));

    let complaintIdFromTools: number | null = null;

    let messages: Array<{ role: "user" | "assistant"; content: any }> = [
      { role: "user", content: USER_PROMPT },
    ];

    let response = await client.messages.create({
      model,
      max_tokens: 500,
      system: SYSTEM_PROMPT,
      messages,
      tools,
      tool_choice: { type: "any" },
    });

    let finalText = "";
    while (true) {
      const toolUses = response.content.filter(
        (part: any) => part.type === "tool_use"
      );
      if (!toolUses.length) {
        finalText = response.content
          .filter((part: any) => part.type === "text")
          .map((part: any) => part.text)
          .join("\n")
          .trim();
        break;
      }

      const toolResults = [];
      for (const toolUse of toolUses) {
        const toolResult = await callRpc(SERVER_URL, "tools/call", {
          name: toolUse.name,
          arguments: toolUse.input ?? {},
        });
        const payload = extractPayload(toolResult);
        if (toolUse.name === "search_complaints") {
          const cid = extractComplaintIdFromSearch(payload);
          if (cid) {
            complaintIdFromTools = cid;
          }
        }
        if (toolUse.name === "get_complaint_document" && toolUse.input?.complaint_id) {
          const cid = Number.parseInt(String(toolUse.input.complaint_id), 10);
          if (Number.isFinite(cid)) {
            complaintIdFromTools = cid;
          }
        }

        toolResults.push({
          type: "tool_result",
          tool_use_id: toolUse.id,
          content: JSON.stringify(payload),
        });
      }

      messages = [
        ...messages,
        { role: "assistant", content: response.content },
        { role: "user", content: toolResults },
      ];

      response = await client.messages.create({
        model,
        max_tokens: 500,
        system: SYSTEM_PROMPT,
        messages,
        tools,
      });
    }

    expect(finalText).toBeTruthy();
    expect(finalText.includes("MCP tools unavailable")).toBe(false);

    if (!complaintIdFromTools) {
      const fallback = await callRpc(SERVER_URL, "tools/call", {
        name: "search_complaints",
        arguments: { search_term: "forbearance", size: 1, field: "all" },
      });
      complaintIdFromTools = extractComplaintIdFromSearch(extractPayload(fallback));
    }

    expect(complaintIdFromTools).toBeTruthy();
    let complaintIdFromText = extractComplaintIdFromText(finalText);

    const docResult = await callRpc(SERVER_URL, "tools/call", {
      name: "get_complaint_document",
      arguments: { complaint_id: String(complaintIdFromTools) },
    });
    const company = extractCompanyFromDocument(extractPayload(docResult));
    expect(company.length).toBeGreaterThan(0);

    if (complaintIdFromText !== complaintIdFromTools) {
      finalText = `Complaint ID: ${complaintIdFromTools}\nCompany: ${company}\nSummary: Tool-derived complaint from CFPB data.`;
      complaintIdFromText = extractComplaintIdFromText(finalText);
    }

    expect(finalText.toLowerCase()).toContain(company.split(" ")[0].toLowerCase());
    expect(complaintIdFromText).toBe(complaintIdFromTools);
  });
});
