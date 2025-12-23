const BASE_URL =
	"https://www.consumerfinance.gov/data-research/consumer-complaints/search/api/v1/";

const BOOL_LITERALS = new Set(["true", "false"]);

const normalizeScalar = (value: unknown): unknown | null => {
	if (value === null || value === undefined) {
		return null;
	}
	if (typeof value === "boolean") {
		return value ? "true" : "false";
	}
	if (typeof value === "string") {
		const stripped = value.trim();
		if (!stripped) {
			return null;
		}
		const lowered = stripped.toLowerCase();
		if (BOOL_LITERALS.has(lowered)) {
			return lowered;
		}
		return stripped;
	}
	return value;
};

const normalizeList = (values: unknown[]): unknown[] | null => {
	const normalized: unknown[] = [];
	for (const item of values) {
		const cleaned = normalizeScalar(item);
		if (cleaned === null) {
			continue;
		}
		normalized.push(cleaned);
	}
	return normalized.length ? normalized : null;
};

export const pruneParams = (
	params: Record<string, unknown>,
): Record<string, unknown> => {
	const cleaned: Record<string, unknown> = {};
	for (const [key, value] of Object.entries(params)) {
		const normalized = Array.isArray(value)
			? normalizeList(value)
			: normalizeScalar(value);
		if (normalized === null) {
			continue;
		}
		cleaned[key] = normalized;
	}
	return cleaned;
};

export const buildParams = (
	filters: Record<string, unknown>,
): Record<string, unknown> => pruneParams(filters);

const encodeParams = (params: Record<string, unknown>): string => {
	const searchParams = new URLSearchParams();
	for (const [key, value] of Object.entries(params)) {
		if (value === null || value === undefined) {
			continue;
		}
		if (Array.isArray(value)) {
			for (const entry of value) {
				searchParams.append(key, String(entry));
			}
		} else {
			searchParams.append(key, String(value));
		}
	}
	return searchParams.toString();
};

const fetchJson = async (path: string, params: Record<string, unknown>) => {
	const query = encodeParams(params);
	const url = query ? `${path}?${query}` : path;
	const response = await fetch(url, { method: "GET" });
	if (!response.ok) {
		const text = await response.text();
		throw new Error(`${response.status}: ${text}`);
	}
	return response.json();
};

export const searchLogic = async (options: {
	size: number;
	from_index: number;
	sort: string;
	search_after?: string | null;
	no_highlight: boolean;
	filters: Record<string, unknown>;
}) => {
	const params = buildParams(options.filters);
	Object.assign(params, {
		size: options.size,
		frm: options.from_index,
		sort: options.sort,
		search_after: options.search_after ?? null,
		no_highlight: options.no_highlight,
		no_aggs: false,
	});
	return fetchJson(BASE_URL, pruneParams(params));
};

export const trendsLogic = async (options: {
	lens: string;
	trend_interval: string;
	trend_depth: number;
	sub_lens?: string | null;
	sub_lens_depth: number;
	focus?: string | null;
	filters: Record<string, unknown>;
}) => {
	const params = buildParams(options.filters);
	Object.assign(params, {
		lens: options.lens,
		trend_interval: options.trend_interval,
		trend_depth: options.trend_depth,
		sub_lens: options.sub_lens ?? null,
		sub_lens_depth: options.sub_lens ? options.sub_lens_depth : null,
		focus: options.focus ?? null,
	});
	return fetchJson(`${BASE_URL}trends`, pruneParams(params));
};

export const geoLogic = async (filters: Record<string, unknown>) => {
	const params = buildParams(filters);
	return fetchJson(`${BASE_URL}geo/states`, params);
};

export const suggestLogic = async (
	field: "company" | "zip_code",
	text: string,
	size: number,
) => {
	const params = { text, size };
	const endpoint = field === "company" ? "_suggest_company" : "_suggest_zip";
	const data = await fetchJson(`${BASE_URL}${endpoint}`, params);
	if (Array.isArray(data)) {
		return data.slice(0, size);
	}
	return data;
};

export const documentLogic = async (complaint_id: string) =>
	fetchJson(`${BASE_URL}${complaint_id}`, {});
