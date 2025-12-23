import { format, startOfMonth, subDays } from "date-fns";

export const UI_BASE_URL =
  "https://www.consumerfinance.gov/data-research/consumer-complaints/search/";
export const DEFAULT_START_DATE = "2011-12-01";

const API_TO_URL_PARAM: Record<string, string> = {
  search_term: "searchText",
  field: "searchField",
  sub_lens: "subLens",
  trend_interval: "dateInterval",
};

const URL_TO_API_PARAM: Record<string, string> = {
  searchText: "search_term",
  searchField: "field",
  subLens: "sub_lens",
  dateInterval: "trend_interval",
  page: "frm",
};

export const SEARCH_ENDPOINT_KEYS = new Set([
  "search_term",
  "field",
  "frm",
  "size",
  "sort",
  "format",
  "no_aggs",
  "no_highlight",
  "company",
  "company_public_response",
  "company_received_max",
  "company_received_min",
  "company_response",
  "consumer_consent_provided",
  "consumer_disputed",
  "date_received_max",
  "date_received_min",
  "has_narrative",
  "issue",
  "product",
  "search_after",
  "state",
  "submitted_via",
  "tags",
  "timely",
  "zip_code",
]);

export const GEO_ENDPOINT_KEYS = new Set([
  "search_term",
  "field",
  "company",
  "company_public_response",
  "company_received_max",
  "company_received_min",
  "company_response",
  "consumer_consent_provided",
  "consumer_disputed",
  "date_received_max",
  "date_received_min",
  "has_narrative",
  "issue",
  "product",
  "state",
  "submitted_via",
  "tags",
  "timely",
  "zip_code",
]);

export const TRENDS_ENDPOINT_KEYS = new Set([
  "search_term",
  "field",
  "company",
  "company_public_response",
  "company_received_max",
  "company_received_min",
  "company_response",
  "consumer_consent_provided",
  "consumer_disputed",
  "date_received_max",
  "date_received_min",
  "focus",
  "has_narrative",
  "issue",
  "lens",
  "product",
  "state",
  "submitted_via",
  "sub_lens",
  "sub_lens_depth",
  "tags",
  "timely",
  "trend_depth",
  "trend_interval",
  "zip_code",
]);

const TREND_KEYS = new Set([
  "lens",
  "sub_lens",
  "trend_interval",
  "trend_depth",
  "sub_lens_depth",
  "focus",
  "chartType",
]);

export type ValidationResult = {
  unknown_keys: string[];
  allowed_keys: string[];
};

const BOOL_LITERALS = new Set(["true", "false"]);

const cleanValue = (value: unknown): unknown | null => {
  if (value === null || value === undefined) {
    return null;
  }
  if (typeof value === "boolean") {
    return value ? "true" : "false";
  }
  if (typeof value === "string") {
    const cleaned = value.trim();
    if (!cleaned) {
      return null;
    }
    const lowered = cleaned.toLowerCase();
    if (BOOL_LITERALS.has(lowered)) {
      return lowered;
    }
    return cleaned;
  }
  if (Array.isArray(value)) {
    const cleanedItems = value
      .map((item) => cleanValue(item))
      .filter((item) => item !== null);
    return cleanedItems.length ? cleanedItems : null;
  }
  return value;
};

const parseIntMaybe = (value: unknown): number | null => {
  if (typeof value === "number" && Number.isInteger(value)) {
    return value;
  }
  if (typeof value === "string" && value.trim().match(/^\d+$/)) {
    return Number.parseInt(value.trim(), 10);
  }
  return null;
};

const formatTrendInterval = (value: string): string => {
  const cleaned = value.trim();
  if (!cleaned) {
    return value;
  }
  return cleaned
    .split(/[\s_-]+/)
    .filter(Boolean)
    .map((token) => token[0].toUpperCase() + token.slice(1))
    .join(" ");
};

const formatLens = (value: string): string => {
  const cleaned = value.trim();
  if (!cleaned) {
    return value;
  }
  return cleaned.replace(/[\s-]+/g, "_").toLowerCase();
};

export const normalizeApiParams = (
  apiParams: Record<string, unknown>
): Record<string, unknown> => {
  const normalized: Record<string, unknown> = {};
  for (const [key, rawValue] of Object.entries(apiParams)) {
    const cleanedValue = cleanValue(rawValue);
    if (cleanedValue === null) {
      continue;
    }
    if (key === "trend_interval" && typeof cleanedValue === "string") {
      normalized[key] = cleanedValue.toLowerCase();
      continue;
    }
    if ((key === "lens" || key === "sub_lens") && typeof cleanedValue === "string") {
      normalized[key] = formatLens(cleanedValue);
      continue;
    }
    normalized[key] = cleanedValue;
  }
  return normalized;
};

const defaultEndDate = (today?: Date): string => {
  const anchor = today ?? new Date();
  const cutoff = subDays(anchor, 30);
  const endDate = subDays(startOfMonth(cutoff), 1);
  return format(endDate, "yyyy-MM-dd");
};

export const applyDefaultDates = (
  apiParams: Record<string, unknown>,
  today?: Date
): Record<string, unknown> => {
  const params = { ...apiParams };
  if (params.date_received_min === undefined || params.date_received_min === null) {
    params.date_received_min = DEFAULT_START_DATE;
  }
  if (params.date_received_max === undefined || params.date_received_max === null) {
    params.date_received_max = defaultEndDate(today);
  }
  return params;
};

export const validateApiParams = (
  apiParams: Record<string, unknown>,
  allowedKeys: Iterable<string>
): ValidationResult => {
  const allowed = new Set(allowedKeys);
  const unknown = Object.keys(apiParams).filter((key) => !allowed.has(key));
  return {
    unknown_keys: unknown.sort(),
    allowed_keys: Array.from(allowed).sort(),
  };
};

const applyPagination = (
  apiParams: Record<string, unknown>,
  urlParams: Record<string, unknown>
) => {
  const frm = parseIntMaybe(apiParams.frm);
  const size = parseIntMaybe(apiParams.size);
  if (frm === null || size === null || size === 0) {
    return;
  }
  urlParams.page = Math.floor(frm / size) + 1;
};

export const apiParamsToUrlParams = (
  apiParams: Record<string, unknown>
): Record<string, unknown> => {
  const urlParams: Record<string, unknown> = {};
  const normalized = normalizeApiParams(apiParams);

  for (const [key, value] of Object.entries(normalized)) {
    if (key === "frm") {
      continue;
    }
    const mappedKey = API_TO_URL_PARAM[key] ?? key;
    let mappedValue = value;
    if (key === "trend_interval" && typeof mappedValue === "string") {
      mappedValue = formatTrendInterval(mappedValue);
    }
    if ((key === "lens" || key === "sub_lens") && typeof mappedValue === "string") {
      mappedValue = formatLens(mappedValue);
    }
    urlParams[mappedKey] = mappedValue;
  }

  applyPagination(normalized, urlParams);
  return urlParams;
};

const encodeQuery = (params: Record<string, unknown>): string => {
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

export const buildDeeplinkUrl = (
  apiParams: Record<string, unknown>,
  tab?: string,
  today?: Date
): string => {
  const paramsWithDates = applyDefaultDates(apiParams, today);
  const urlParams = apiParamsToUrlParams(paramsWithDates);

  if (!tab && Object.keys(apiParams).some((key) => TREND_KEYS.has(key))) {
    tab = "Trends";
  }
  if (tab) {
    urlParams.tab = tab;
  }
  if (!Object.keys(urlParams).length) {
    return UI_BASE_URL;
  }
  return `${UI_BASE_URL}?${encodeQuery(urlParams)}`;
};

export const urlParamsToApiParams = (
  urlParams: Record<string, unknown>
): Record<string, unknown> => {
  const apiParams: Record<string, unknown> = {};
  for (const [key, rawValue] of Object.entries(urlParams)) {
    const apiKey = URL_TO_API_PARAM[key] ?? key;
    const cleanedValue = cleanValue(rawValue);
    if (cleanedValue === null) {
      continue;
    }
    let finalValue = cleanedValue;
    if (apiKey === "trend_interval" && typeof cleanedValue === "string") {
      finalValue = cleanedValue.toLowerCase();
    }
    if ((apiKey === "lens" || apiKey === "sub_lens") && typeof cleanedValue === "string") {
      finalValue = formatLens(cleanedValue);
    }
    apiParams[apiKey] = finalValue;
  }

  if (apiParams.frm !== undefined) {
    const page = parseIntMaybe(apiParams.frm);
    const size = parseIntMaybe(apiParams.size);
    if (page !== null && size) {
      apiParams.frm = (page - 1) * size;
    } else {
      delete apiParams.frm;
    }
  }

  return apiParams;
};

export const urlToApiParams = (url: string): Record<string, unknown> => {
  const parsed = new URL(url);
  const query: Record<string, unknown> = {};
  parsed.searchParams.forEach((value, key) => {
    if (query[key] === undefined) {
      query[key] = value;
    } else if (Array.isArray(query[key])) {
      (query[key] as string[]).push(value);
    } else {
      query[key] = [query[key] as string, value];
    }
  });
  return urlParamsToApiParams(query);
};
