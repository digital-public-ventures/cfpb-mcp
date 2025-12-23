import { describe, expect, it } from "vitest";
import { callRpc, resolveServerUrl } from "../helpers/http.js";

const SERVER_URL = resolveServerUrl();

describe("generate_cfpb_dashboard_url", () => {
	it("returns a CFPB dashboard URL", async () => {
		const result = await callRpc(SERVER_URL, "tools/call", {
			name: "generate_cfpb_dashboard_url",
			arguments: {
				search_term: "forbearance",
				product: ["Student loan"],
				state: ["CA"],
			},
		});
		expect(typeof result?.url).toBe("string");
		expect(result.url).toContain(
			"consumerfinance.gov/data-research/consumer-complaints/search",
		);
	});
});
