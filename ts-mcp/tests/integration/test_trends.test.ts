import { describe, expect, it } from "vitest";
import { callRpc } from "../helpers/http.js";
import { extractPayload } from "../helpers/mcp.js";

const SERVER_URL = process.env.TEST_SERVER_URL ?? "http://127.0.0.1:8787/mcp";

describe("list_complaint_trends", () => {
	it("returns trend data and citations", async () => {
		const result = await callRpc(SERVER_URL, "tools/call", {
			name: "list_complaint_trends",
			arguments: {
				lens: "overview",
				trend_interval: "month",
				trend_depth: 6,
				search_term: "forbearance",
				field: "complaint_what_happened",
				size: 1,
			},
		});
		const payload = extractPayload(result);
		expect(payload.data).toBeTruthy();
		expect(payload.citations).toBeTruthy();
	});
});
