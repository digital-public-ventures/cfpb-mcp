import { describe, expect, it } from "vitest";
import { callRpc } from "../helpers/http.js";

const SERVER_URL = process.env.TEST_SERVER_URL ?? "http://127.0.0.1:8787/mcp";

describe("tools/list", () => {
	it("includes core tools", async () => {
		const result = (await callRpc(SERVER_URL, "tools/list")) as {
			tools: { name: string }[];
		};
		const names = new Set(result.tools.map((tool) => tool.name));
		const expected = [
			"search_complaints",
			"list_complaint_trends",
			"get_state_aggregations",
			"get_complaint_document",
			"suggest_filter_values",
		];
		for (const name of expected) {
			expect(names.has(name)).toBe(true);
		}
	});
});
