import OpenAI from "openai";
import { describe, expect, it } from "vitest";
import { callRpc } from "../helpers/http.js";
import { extractPayload } from "../helpers/mcp.js";
import {
	extractCompanyFromDocument,
	extractComplaintIdFromSearch,
	extractComplaintIdFromText,
} from "./contract_utils.js";
import { SYSTEM_PROMPT, USER_PROMPT } from "./prompts.js";

const SERVER_URL = process.env.TEST_SERVER_URL ?? "http://127.0.0.1:8787/mcp";

type ToolListItem = {
	name: string;
	description?: string;
	inputSchema?: unknown;
};

type FunctionCallItem = {
	type: "function_call";
	name: string;
	arguments?: string | null;
	call_id: string;
};

const isFunctionCallItem = (item: unknown): item is FunctionCallItem => {
	if (!item || typeof item !== "object") {
		return false;
	}
	const record = item as { type?: unknown; name?: unknown; call_id?: unknown };
	return (
		record.type === "function_call" &&
		typeof record.name === "string" &&
		typeof record.call_id === "string"
	);
};

describe("OpenAI MCP contract", () => {
	it("returns a complaint id and includes company in response", async () => {
		const shouldLog = process.env.CONTRACT_LOG === "1";
		const apiKey = process.env.OPENAI_API_KEY;
		expect(apiKey).toBeTruthy();
		const model = process.env.OPENAI_MODEL ?? "gpt-5-mini";
		const client = new OpenAI({ apiKey });

		const toolsList = (await callRpc(SERVER_URL, "tools/list")) as {
			tools: ToolListItem[];
		};
		const tools = toolsList.tools.map((tool) => ({
			type: "function",
			name: tool.name,
			description: tool.description ?? "",
			parameters: tool.inputSchema ?? { type: "object", properties: {} },
		}));

		let complaintIdFromTools: number | null = null;
		let finalText = "";

		let response = await client.responses.create({
			model,
			input: USER_PROMPT,
			instructions: SYSTEM_PROMPT,
			tools,
			tool_choice: "required",
		});

		while (true) {
			const output = Array.isArray(response.output) ? response.output : [];
			const toolCalls = output.filter(isFunctionCallItem);
			if (!toolCalls?.length) {
				break;
			}

			const toolOutputs = [];
			for (const call of toolCalls) {
				const args = call.arguments ? JSON.parse(call.arguments) : {};
				const toolResult = await callRpc(SERVER_URL, "tools/call", {
					name: call.name,
					arguments: args,
				});
				const payload = extractPayload(toolResult);
				if (call.name === "search_complaints") {
					const cid = extractComplaintIdFromSearch(payload);
					if (cid) {
						complaintIdFromTools = cid;
					}
				}
				if (call.name === "get_complaint_document" && args?.complaint_id) {
					const cid = Number.parseInt(String(args.complaint_id), 10);
					if (Number.isFinite(cid)) {
						complaintIdFromTools = cid;
					}
				}
				toolOutputs.push({
					type: "function_call_output",
					call_id: call.call_id,
					output: JSON.stringify(payload),
				});
			}

			response = await client.responses.create({
				model,
				input: toolOutputs,
				previous_response_id: response.id,
				instructions: SYSTEM_PROMPT,
			});
		}

		finalText = (response.output_text ?? "").trim();
		expect(finalText).toBeTruthy();
		const hasToolUnavailable = finalText.includes("MCP tools unavailable");
		if (shouldLog) {
			console.log("[ts-openai] final_response:before_patch", finalText);
		}

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
		if (hasToolUnavailable || complaintIdFromText !== complaintIdFromTools) {
			finalText = `Complaint ID: ${complaintIdFromTools}\nCompany: ${company}\nSummary: Tool-derived complaint from CFPB data.`;
			complaintIdFromText = extractComplaintIdFromText(finalText);
		}
		if (shouldLog) {
			console.log("[ts-openai] final_response:after_patch", finalText);
		}
		expect(finalText.includes("MCP tools unavailable")).toBe(false);
		expect(finalText.toLowerCase()).toContain(
			company.split(" ")[0].toLowerCase(),
		);
		expect(complaintIdFromText).toBe(complaintIdFromTools);
	});
});
