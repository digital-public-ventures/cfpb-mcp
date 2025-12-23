import { describe, expect, it } from "vitest";
import { callRpc, resolveServerUrl } from "../helpers/http.js";

const SERVER_URL = resolveServerUrl();

describe("trend signal tools", () => {
	it("computes overall trend signals", async () => {
		const result = await callRpc(SERVER_URL, "tools/call", {
			name: "get_overall_trend_signals",
			arguments: {
				search_term: "forbearance",
				trend_interval: "month",
				trend_depth: 6,
				baseline_window: 3,
			},
		});
		expect(result.signals?.overall).toBeTruthy();
	});

	it("ranks group spikes", async () => {
		const result = await callRpc(SERVER_URL, "tools/call", {
			name: "rank_group_spikes",
			arguments: {
				group: "product",
				trend_interval: "month",
				trend_depth: 6,
				sub_lens_depth: 5,
				top_n: 3,
				baseline_window: 3,
				search_term: "forbearance",
			},
		});
		expect(Array.isArray(result.results)).toBe(true);
	});

	it("ranks company spikes", async () => {
		const result = await callRpc(SERVER_URL, "tools/call", {
			name: "rank_company_spikes",
			arguments: {
				trend_interval: "month",
				trend_depth: 6,
				top_n: 3,
				baseline_window: 3,
				search_term: "forbearance",
			},
		});
		expect(Array.isArray(result.results)).toBe(true);
	});
});
