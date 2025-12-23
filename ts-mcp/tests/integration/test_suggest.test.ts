import { describe, expect, it } from "vitest";
import { callRpc, resolveServerUrl } from "../helpers/http.js";

const SERVER_URL = resolveServerUrl();

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
