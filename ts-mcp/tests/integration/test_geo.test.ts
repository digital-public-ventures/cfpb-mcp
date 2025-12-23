import { describe, expect, it } from "vitest";
import { callRpc, resolveServerUrl } from "../helpers/http.js";
import { extractPayload } from "../helpers/mcp.js";

const SERVER_URL = resolveServerUrl();

describe("get_state_aggregations", () => {
	it("returns aggregation data", async () => {
		const result = await callRpc(SERVER_URL, "tools/call", {
			name: "get_state_aggregations",
			arguments: {
				search_term: "forbearance",
				field: "complaint_what_happened",
			},
		});
		const payload = extractPayload(result);
		expect(payload.data).toBeTruthy();
		expect(payload.citations).toBeTruthy();
	});
});
