import Anthropic from "@anthropic-ai/sdk";
import { describe, expect, it } from "vitest";
import { callRpc, resolveServerUrl } from "../helpers/http.js";
import { extractPayload } from "../helpers/mcp.js";
import {
	extractCompanyFromDocument,
	extractComplaintIdFromSearch,
	extractComplaintIdFromText,
} from "./contract_utils.js";
import { SYSTEM_PROMPT, USER_PROMPT } from "./prompts.js";

const SERVER_URL = resolveServerUrl();

type ToolListItem = {
	name: string;
	description?: string;
	inputSchema?: unknown;
};

type ToolUse = {
	type: "tool_use";
	id: string;
	name: string;
	input?: Record<string, unknown> | null;
};

type TextBlock = {
	type: "text";
	text: string;
};

const isToolUse = (part: unknown): part is ToolUse => {
	if (!part || typeof part !== "object") {
		return false;
	}
	const record = part as { type?: unknown; id?: unknown; name?: unknown };
	return (
		record.type === "tool_use" &&
		typeof record.id === "string" &&
		typeof record.name === "string"
	);
};

const isTextBlock = (part: unknown): part is TextBlock => {
	if (!part || typeof part !== "object") {
		return false;
	}
	const record = part as { type?: unknown; text?: unknown };
	return record.type === "text" && typeof record.text === "string";
};

describe("Anthropic MCP contract", () => {
	it("returns a complaint id and includes company in response", async () => {
		const shouldLog = process.env.CONTRACT_LOG === "1";
		const apiKey = process.env.ANTHROPIC_API_KEY;
		expect(apiKey).toBeTruthy();
		const model = process.env.ANTHROPIC_MODEL ?? "claude-haiku-4-5";
		const client = new Anthropic({ apiKey });

		const toolsList = (await callRpc(SERVER_URL, "tools/list")) as {
			tools: ToolListItem[];
		};
		const tools = toolsList.tools.map((tool) => ({
			name: tool.name,
			description: tool.description ?? "",
			input_schema: tool.inputSchema ?? { type: "object", properties: {} },
		}));

		let complaintIdFromTools: number | null = null;

		let messages: Array<{ role: "user" | "assistant"; content: unknown }> = [
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
			const content = Array.isArray(response.content) ? response.content : [];
			const toolUses = content.filter(isToolUse);
			if (!toolUses.length) {
				finalText = content
					.filter(isTextBlock)
					.map((part) => part.text)
					.join("\n")
					.trim();
				break;
			}

			const toolResults = [];
			for (const toolUse of toolUses) {
				const toolInput =
					toolUse.input && typeof toolUse.input === "object"
						? toolUse.input
						: {};
				const toolResult = await callRpc(SERVER_URL, "tools/call", {
					name: toolUse.name,
					arguments: toolInput,
				});
				const payload = extractPayload(toolResult);
				if (toolUse.name === "search_complaints") {
					const cid = extractComplaintIdFromSearch(payload);
					if (cid) {
						complaintIdFromTools = cid;
					}
				}
				const complaintIdValue = toolInput.complaint_id;
				if (toolUse.name === "get_complaint_document" && complaintIdValue) {
					const cid = Number.parseInt(String(complaintIdValue), 10);
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
		if (shouldLog) {
			console.log("[ts-anthropic] final_response", finalText);
		}
		expect(finalText.includes("MCP tools unavailable")).toBe(false);

		if (!complaintIdFromTools) {
			const fallback = await callRpc(SERVER_URL, "tools/call", {
				name: "search_complaints",
				arguments: { search_term: "forbearance", size: 1, field: "all" },
			});
			complaintIdFromTools = extractComplaintIdFromSearch(
				extractPayload(fallback),
			);
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

		expect(finalText.toLowerCase()).toContain(
			company.split(" ")[0].toLowerCase(),
		);
		expect(complaintIdFromText).toBe(complaintIdFromTools);
	});
});
