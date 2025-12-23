import { describe, expect, it } from "vitest";
import { callRpc, resolveServerUrl } from "../helpers/http.js";
import { extractPayload } from "../helpers/mcp.js";

const SERVER_URL = resolveServerUrl();
const DEEPLINK_REGEX =
	/^https:\/\/www\.consumerfinance\.gov\/data-research\/consumer-complaints\/search\/detail\/\d+$/;

const pickComplaintId = (payload: unknown): string | null => {
	const record = payload as { data?: { hits?: { hits?: unknown[] } } };
	const hits = record?.data?.hits?.hits;
	if (!Array.isArray(hits) || !hits.length) {
		return null;
	}
	const hit0 = hits[0] as {
		_id?: unknown;
		_source?: { complaint_id?: unknown };
	};
	const raw = hit0?._source?.complaint_id ?? hit0?._id ?? null;
	return raw ? String(raw) : null;
};

describe("complaint deeplinks", () => {
	it("adds deeplinks to search results and complaint document", async () => {
		const searchResult = await callRpc(SERVER_URL, "tools/call", {
			name: "search_complaints",
			arguments: {
				search_term: "forbearance",
				field: "complaint_what_happened",
				size: 3,
				from_index: 0,
				sort: "relevance_desc",
				no_highlight: true,
			},
		});
		const searchPayload = extractPayload(searchResult);
		const hits = searchPayload.data?.hits?.hits ?? [];
		expect(Array.isArray(hits)).toBe(true);
		expect(hits.length).toBeGreaterThan(0);
		for (const hit of hits) {
			const source = hit?._source ?? hit;
			const deeplink = source?.complaint_deeplink;
			expect(typeof deeplink).toBe("string");
			expect(deeplink).toMatch(DEEPLINK_REGEX);
		}

		const complaintId = pickComplaintId(searchPayload);
		expect(complaintId).toBeTruthy();
		const docResult = await callRpc(SERVER_URL, "tools/call", {
			name: "get_complaint_document",
			arguments: { complaint_id: complaintId },
		});
		const docPayload = extractPayload(docResult);
		const docHits = docPayload.hits?.hits ?? [];
		expect(Array.isArray(docHits)).toBe(true);
		expect(docHits.length).toBeGreaterThan(0);
		const docSource = docHits[0]?._source ?? {};
		expect(docSource.complaint_deeplink).toMatch(DEEPLINK_REGEX);
	});
});
