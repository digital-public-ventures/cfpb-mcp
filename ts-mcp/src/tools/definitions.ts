import { z } from "zod";

const searchField = z.enum(["complaint_what_happened", "company", "all"]);
const searchSort = z.enum(["relevance_desc", "created_date_desc"]);

const listString = z.array(z.string()).optional();
const dateString = z.string().optional();

const baseFilters = {
  search_term: z.string().optional(),
  field: searchField.default("complaint_what_happened"),
  company: listString,
  company_public_response: listString,
  company_response: listString,
  consumer_consent_provided: listString,
  consumer_disputed: listString,
  date_received_min: dateString,
  date_received_max: dateString,
  company_received_min: dateString,
  company_received_max: dateString,
  has_narrative: listString,
  issue: listString,
  product: listString,
  state: listString,
  submitted_via: listString,
  tags: listString,
  timely: listString,
  zip_code: listString,
};

export const toolDefinitions = {
  search_complaints: {
    description: "Search the Consumer Complaint Database.",
    schema: z.object({
      ...baseFilters,
      size: z.number().int().min(1).default(10),
      from_index: z.number().int().min(0).default(0),
      sort: searchSort.default("relevance_desc"),
      search_after: z.string().optional().nullable(),
      no_highlight: z.boolean().default(false),
    }),
  },
  list_complaint_trends: {
    description: "Get aggregated trend data for complaints over time.",
    schema: z.object({
      ...baseFilters,
      lens: z.string().default("overview"),
      trend_interval: z.string().default("month"),
      trend_depth: z.number().int().min(1).default(5),
      sub_lens: z.string().optional().nullable(),
      sub_lens_depth: z.number().int().min(0).default(5),
      focus: z.string().optional().nullable(),
    }),
  },
  get_state_aggregations: {
    description: "Get complaint counts aggregated by US State.",
    schema: z.object({
      ...baseFilters,
    }),
  },
  get_complaint_document: {
    description: "Retrieve a single complaint by its ID.",
    schema: z.object({
      complaint_id: z.string(),
    }),
  },
  suggest_filter_values: {
    description: "Autocomplete helper for filter values (company or zip_code).",
    schema: z.object({
      field: z.enum(["company", "zip_code"]),
      text: z.string(),
      size: z.number().int().min(1).default(10),
    }),
  },
  generate_cfpb_dashboard_url: {
    description:
      "Generate a deep-link URL to the official CFPB consumer complaints dashboard.",
    schema: z.object({
      search_term: z.string().optional(),
      date_received_min: dateString,
      date_received_max: dateString,
      company: listString,
      product: listString,
      issue: listString,
      state: listString,
      has_narrative: z.string().optional(),
      company_response: listString,
      company_public_response: listString,
      consumer_disputed: listString,
      tags: listString,
      submitted_via: listString,
      timely: listString,
      zip_code: listString,
      tab: z.string().optional(),
      lens: z.string().optional(),
      sub_lens: z.string().optional(),
      chart_type: z.string().optional(),
      date_interval: z.string().optional(),
    }),
  },
  get_overall_trend_signals: {
    description: "Compute simple spike/velocity signals from overall trends buckets.",
    schema: z.object({
      ...baseFilters,
      lens: z.string().default("overview"),
      trend_interval: z.string().default("month"),
      trend_depth: z.number().int().min(1).default(24),
      baseline_window: z.number().int().min(1).default(8),
      min_baseline_mean: z.number().min(0).default(10),
    }),
  },
  rank_group_spikes: {
    description: "Rank product or issue values by latest-bucket spike.",
    schema: z.object({
      ...baseFilters,
      group: z.enum(["product", "issue"]),
      lens: z.string().default("overview"),
      trend_interval: z.string().default("month"),
      trend_depth: z.number().int().min(1).default(12),
      sub_lens_depth: z.number().int().min(1).default(10),
      top_n: z.number().int().min(1).default(10),
      baseline_window: z.number().int().min(1).default(8),
      min_baseline_mean: z.number().min(0).default(10),
    }),
  },
  rank_company_spikes: {
    description:
      "Pipeline-style company spikes: search aggs -> top companies -> trends per company -> rank.",
    schema: z.object({
      ...baseFilters,
      lens: z.string().default("overview"),
      trend_interval: z.string().default("month"),
      trend_depth: z.number().int().min(1).default(12),
      top_n: z.number().int().min(1).default(10),
      baseline_window: z.number().int().min(1).default(8),
      min_baseline_mean: z.number().min(0).default(25),
    }),
  },
} as const;

export type ToolName = keyof typeof toolDefinitions;
