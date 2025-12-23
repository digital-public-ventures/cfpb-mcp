import { describe, expect, it } from "vitest";
import { callRpc } from "../helpers/http.js";

const SERVER_URL = process.env.TEST_SERVER_URL ?? "http://127.0.0.1:8787/mcp";

describe("suggest_filter_values", () => {
	it("returns suggestions for company", async () => {
		const result = await callRpc(SERVER_URL, "tools/call", {
			name: "suggest_filter_values",
			arguments: {
				field: "company",
				text: "Nav",
				size: 3,
			},
		});
		expect(Array.isArray(result.values)).toBe(true);
	});
});
