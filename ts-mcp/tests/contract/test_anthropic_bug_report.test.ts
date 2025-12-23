import { describe, expect, it } from "vitest";
import { callRpc, resolveServerUrl } from "../helpers/http.js";
import { extractPayload } from "../helpers/mcp.js";

const SERVER_URL = resolveServerUrl();

const asRecord = (value: unknown): Record<string, unknown> | null => {
	if (!value || typeof value !== "object") {
		return null;
	}
	return value as Record<string, unknown>;
};

const extractTextContent = (payload: unknown): string => {
	const record = asRecord(payload);
	const content = record?.content;
	if (!Array.isArray(content)) {
		return "";
	}
	return content
		.map((item) => {
			const entry = asRecord(item);
			return typeof entry?.text === "string" ? entry.text : "";
		})
		.filter(Boolean)
		.join("\n")
		.trim();
};

const expectHasData = (payload: unknown) => {
	const record = asRecord(payload);
	expect(record).toBeTruthy();
	expect(record?.data).toBeTruthy();
	expect(record?.citations).toBeTruthy();
};

describe("Anthropic bug report coverage", () => {
	it("returns data for basic search", async () => {
		const result = await callRpc(SERVER_URL, "tools/call", {
			name: "search_complaints",
			arguments: { search_term: "forbearance", size: 10 },
		});
		expectHasData(extractPayload(result));
	});

	it("returns data for search with product filter", async () => {
		const result = await callRpc(SERVER_URL, "tools/call", {
			name: "search_complaints",
			arguments: {
				product: ["Mortgage"],
				search_term: "forbearance",
				size: 10,
			},
		});
		expectHasData(extractPayload(result));
	});

	it("returns data for search with minimal parameters", async () => {
		const result = await callRpc(SERVER_URL, "tools/call", {
			name: "search_complaints",
			arguments: { size: 5 },
		});
		expectHasData(extractPayload(result));
	});

	it("surfaces validation error when missing product focus/sub_lens", async () => {
		const result = await callRpc(SERVER_URL, "tools/call", {
			name: "list_complaint_trends",
			arguments: { lens: "product", trend_depth: 6 },
		});
		const record = asRecord(result);
		const text = extractTextContent(result);
		expect(record?.isError).toBe(true);
		expect(text).toMatch(/Focus or Sub-lens is required|non_field_errors/i);
	});

	it("returns data for trends with sub_lens", async () => {
		const result = await callRpc(SERVER_URL, "tools/call", {
			name: "list_complaint_trends",
			arguments: {
				lens: "product",
				search_term: "forbearance",
				sub_lens: "issue",
				trend_depth: 12,
			},
		});
		expectHasData(extractPayload(result));
	});

	it("returns signals for overall trends", async () => {
		const result = await callRpc(SERVER_URL, "tools/call", {
			name: "get_overall_trend_signals",
			arguments: { search_term: "forbearance", trend_depth: 12 },
		});
		const payload = extractPayload(result);
		const record = asRecord(payload);
		expect(record).toBeTruthy();
		expect(record?.signals).toBeTruthy();
		expect(record?.params).toBeTruthy();
	});

	it("returns autocomplete values", async () => {
		const result = await callRpc(SERVER_URL, "tools/call", {
			name: "suggest_filter_values",
			arguments: { field: "company", text: "wells" },
		});
		const payload = extractPayload(result);
		const record = asRecord(payload);
		const values = record?.values;
		expect(Array.isArray(values)).toBe(true);
		expect((values as unknown[]).length).toBeGreaterThan(0);
	});
});
