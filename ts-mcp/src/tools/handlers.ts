import {
	documentLogic,
	geoLogic,
	searchLogic,
	suggestLogic,
	trendsLogic,
} from "../utils/api.js";
import { buildDeeplinkUrl } from "../utils/deeplink.js";
import {
	companyBucketsFromSearch,
	computeSimpleSignals,
	dropCurrentMonth,
	extractGroupSeries,
	extractOverallPoints,
} from "../utils/math.js";
import { type ToolName, toolDefinitions } from "./definitions.js";

type Citation = { type: string; url: string; description: string };

const buildCfpbUiUrl = (params: Record<string, unknown>): string => {
	const apiParams: Record<string, unknown> = {
		search_term: params.search_term,
		date_received_min: params.date_received_min,
		date_received_max: params.date_received_max,
		company: params.company,
		product: params.product,
		issue: params.issue,
		state: params.state,
		has_narrative: params.has_narrative,
		company_response: params.company_response,
		company_public_response: params.company_public_response,
		consumer_disputed: params.consumer_disputed,
		tags: params.tags,
		submitted_via: params.submitted_via,
		timely: params.timely,
		zip_code: params.zip_code,
	};

	if (params.lens) {
		apiParams.lens = params.lens;
	}
	if (params.sub_lens) {
		apiParams.sub_lens = params.sub_lens;
	}
	if (params.chart_type) {
		apiParams.chartType = params.chart_type;
	}
	if (params.date_interval) {
		apiParams.trend_interval = String(params.date_interval).toLowerCase();
	}

	return buildDeeplinkUrl(apiParams, params.tab as string | undefined);
};

const extractFilterParams = (params: Record<string, unknown>) => {
	const allowed = new Set([
		"search_term",
		"date_received_min",
		"date_received_max",
		"company",
		"product",
		"issue",
		"state",
		"has_narrative",
		"company_response",
		"company_public_response",
		"consumer_disputed",
		"tags",
		"submitted_via",
		"timely",
		"zip_code",
	]);
	const out: Record<string, unknown> = {};
	for (const [key, value] of Object.entries(params)) {
		if (!allowed.has(key)) {
			continue;
		}
		out[key] = value;
	}
	return out;
};

const generateCitations = (options: {
	context_type: "search" | "trends" | "geo" | "suggest" | "document";
	total_hits?: number | null;
	complaint_id?: string | null;
	lens?: string | null;
	params: Record<string, unknown>;
}): Citation[] => {
	const citations: Citation[] = [];
	const filterParams = extractFilterParams(options.params);

	if (options.context_type === "search") {
		const url = buildDeeplinkUrl(filterParams, "List");
		let description = "View these matching complaint(s) on CFPB.gov";
		if (typeof options.total_hits === "number") {
			description = `View all ${options.total_hits.toLocaleString()} matching complaint(s) on CFPB.gov`;
		}
		citations.push({ type: "search_results", url, description });
	} else if (options.context_type === "trends") {
		const trendParams = {
			...filterParams,
			lens: options.lens ?? "Overview",
			chartType: "line",
			trend_interval: "month",
		};
		const url = buildDeeplinkUrl(trendParams, "Trends");
		citations.push({
			type: "trends_chart",
			url,
			description: "Interactive trends chart on CFPB.gov",
		});
	} else if (options.context_type === "geo") {
		const url = buildDeeplinkUrl(filterParams, "Map");
		citations.push({
			type: "geographic_map",
			url,
			description: "Interactive geographic map on CFPB.gov",
		});
	} else if (options.context_type === "document" && options.complaint_id) {
		const baseUrl =
			"https://www.consumerfinance.gov/data-research/consumer-complaints/search/";
		citations.push({
			type: "complaint_detail",
			url: `${baseUrl}?tab=List`,
			description: `Search for complaint ${options.complaint_id} on CFPB.gov`,
		});
	}

	if (
		(options.context_type === "trends" || options.context_type === "geo") &&
		Object.keys(filterParams).length
	) {
		const listUrl = buildDeeplinkUrl(filterParams, "List");
		citations.push({
			type: "search_results",
			url: listUrl,
			description: "Browse matching complaints on CFPB.gov",
		});
	}

	return citations;
};

type HandlerArgs = Record<string, unknown>;
type HandlerResult = Promise<unknown>;

const getTotalHits = (data: unknown): number | null => {
	if (!data || typeof data !== "object") {
		return null;
	}
	const hits = (data as { hits?: { total?: number | { value?: unknown } } })
		.hits;
	const total = hits?.total;
	if (typeof total === "number") {
		return total;
	}
	if (total && typeof total === "object") {
		const value = (total as { value?: unknown }).value;
		return typeof value === "number" ? value : null;
	}
	return null;
};

const getZScore = (value: unknown): number | null => {
	if (!value || typeof value !== "object") {
		return null;
	}
	const signals = (value as { signals?: unknown }).signals;
	if (!signals || typeof signals !== "object") {
		return null;
	}
	const lastVsBaseline = (signals as { last_vs_baseline?: unknown })
		.last_vs_baseline;
	if (!lastVsBaseline || typeof lastVsBaseline !== "object") {
		return null;
	}
	const z = (lastVsBaseline as { z?: unknown }).z;
	return typeof z === "number" ? z : null;
};

export const handlers: Record<ToolName, (args: HandlerArgs) => HandlerResult> =
	{
		search_complaints: async (args) => {
			const data = await searchLogic({
				size: args.size,
				from_index: args.from_index,
				sort: args.sort,
				search_after: args.search_after,
				no_highlight: args.no_highlight,
				filters: args,
			});

			const totalHits = getTotalHits(data);
			const citations = generateCitations({
				context_type: "search",
				total_hits: totalHits,
				params: args,
			});

			return { data, citations };
		},

		list_complaint_trends: async (args) => {
			const data = await trendsLogic({
				lens: args.lens,
				trend_interval: args.trend_interval,
				trend_depth: args.trend_depth,
				sub_lens: args.sub_lens,
				sub_lens_depth: args.sub_lens_depth,
				focus: args.focus,
				filters: args,
			});

			const citations = generateCitations({
				context_type: "trends",
				lens: args.lens,
				params: args,
			});

			return { data, citations };
		},

		get_state_aggregations: async (args) => {
			const data = await geoLogic(args);
			const citations = generateCitations({
				context_type: "geo",
				params: args,
			});
			return { data, citations };
		},

		get_complaint_document: async (args) => documentLogic(args.complaint_id),

		suggest_filter_values: async (args) => ({
			values: await suggestLogic(args.field, args.text, args.size),
		}),

		generate_cfpb_dashboard_url: async (args) => ({
			url: buildCfpbUiUrl(args),
		}),

		get_overall_trend_signals: async (args) => {
			const payload = await trendsLogic({
				lens: args.lens,
				trend_interval: args.trend_interval,
				trend_depth: args.trend_depth,
				sub_lens: null,
				sub_lens_depth: 0,
				focus: null,
				filters: args,
			});
			const points = dropCurrentMonth(extractOverallPoints(payload));
			return {
				params: {
					lens: args.lens,
					trend_interval: args.trend_interval,
					trend_depth: args.trend_depth,
					date_received_min: args.date_received_min,
					date_received_max: args.date_received_max,
				},
				signals: {
					overall: computeSimpleSignals(
						points,
						args.baseline_window,
						args.min_baseline_mean,
					),
				},
			};
		},

		rank_group_spikes: async (args) => {
			const payload = await trendsLogic({
				lens: args.lens,
				trend_interval: args.trend_interval,
				trend_depth: args.trend_depth,
				sub_lens: args.group,
				sub_lens_depth: args.sub_lens_depth,
				focus: null,
				filters: args,
			});
			const series = extractGroupSeries(payload, args.group);
			const scored = series
				.map((entry) => {
					const points = dropCurrentMonth(entry.points);
					const signals = computeSimpleSignals(
						points,
						args.baseline_window,
						args.min_baseline_mean,
					);
					if ("error" in signals) {
						return null;
					}
					return {
						group: entry.group,
						doc_count: entry.doc_count,
						...signals,
					};
				})
				.filter(Boolean) as Array<Record<string, unknown>>;

			scored.sort((a, b) => {
				const aZ = getZScore(a.signals);
				const bZ = getZScore(b.signals);
				if (aZ === undefined || aZ === null) {
					return 1;
				}
				if (bZ === undefined || bZ === null) {
					return -1;
				}
				return bZ - aZ;
			});

			return {
				params: {
					group: args.group,
					lens: args.lens,
					trend_interval: args.trend_interval,
					trend_depth: args.trend_depth,
					sub_lens_depth: args.sub_lens_depth,
					top_n: args.top_n,
					date_received_min: args.date_received_min,
					date_received_max: args.date_received_max,
				},
				results: scored.slice(0, args.top_n),
			};
		},

		rank_company_spikes: async (args) => {
			const searchPayload = await searchLogic({
				size: 0,
				from_index: 0,
				sort: "created_date_desc",
				search_after: null,
				no_highlight: true,
				filters: args,
			});

			const topCompanies = companyBucketsFromSearch(searchPayload).slice(
				0,
				args.top_n,
			);
			const results: Array<Record<string, unknown>> = [];

			for (const [company, companyDocCount] of topCompanies) {
				const trendsPayload = await trendsLogic({
					lens: args.lens,
					trend_interval: args.trend_interval,
					trend_depth: args.trend_depth,
					sub_lens: null,
					sub_lens_depth: 0,
					focus: null,
					filters: { ...args, company: [company] },
				});
				const points = dropCurrentMonth(extractOverallPoints(trendsPayload));
				const signals = computeSimpleSignals(
					points,
					args.baseline_window,
					args.min_baseline_mean,
				);
				results.push({
					company,
					company_doc_count: companyDocCount,
					computed: signals,
				});
			}

			results.sort((a, b) => {
				const aZ = getZScore(a.computed);
				const bZ = getZScore(b.computed);
				if (aZ === undefined || aZ === null) {
					return 1;
				}
				if (bZ === undefined || bZ === null) {
					return -1;
				}
				return (bZ as number) - (aZ as number);
			});

			return {
				date_filters: {
					date_received_min: args.date_received_min,
					date_received_max: args.date_received_max,
				},
				ranking: "last bucket vs baseline z-score",
				results,
			};
		},
	};

export const toolSpecs = Object.entries(toolDefinitions).map(
	([name, definition]) => ({
		name,
		description: definition.description,
		inputSchema: definition.schema,
	}),
);
