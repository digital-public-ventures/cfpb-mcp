const MIN_STDDEV_SAMPLES = 2;
const MIN_SIGNAL_POINTS = 2;
const MIN_BASELINE_POINTS = 2;

export type TrendPoint = [string, number];

export const mean = (values: number[]): number =>
	values.length ? values.reduce((sum, v) => sum + v, 0) / values.length : 0;

const asRecord = (value: unknown): Record<string, unknown> | null => {
	if (!value || typeof value !== "object") {
		return null;
	}
	return value as Record<string, unknown>;
};

export const stddev = (values: number[]): number => {
	if (values.length < MIN_STDDEV_SAMPLES) {
		return 0;
	}
	const m = mean(values);
	const variance =
		values.reduce((acc, v) => acc + (v - m) ** 2, 0) / (values.length - 1);
	return Math.sqrt(variance);
};

const currentMonthPrefix = (now?: Date): string => {
	const n = now ?? new Date();
	const year = n.getUTCFullYear();
	const month = `${n.getUTCMonth() + 1}`.padStart(2, "0");
	return `${year}-${month}-`;
};

export const dropCurrentMonth = (points: TrendPoint[]): TrendPoint[] => {
	const prefix = currentMonthPrefix();
	return points.filter(([label]) => !String(label).startsWith(prefix));
};

export const extractOverallPoints = (payload: unknown): TrendPoint[] => {
	const payloadRecord = asRecord(payload);
	const aggregations = asRecord(payloadRecord?.aggregations);
	const dateRangeArea = asRecord(aggregations?.dateRangeArea);
	const dateRangeAreaInner = asRecord(dateRangeArea?.dateRangeArea);
	const buckets = dateRangeAreaInner?.buckets;
	if (!Array.isArray(buckets)) {
		return [];
	}

	const rows: Array<[number, string, number]> = [];
	for (const bucket of buckets) {
		const bucketRecord = asRecord(bucket);
		if (!bucketRecord) {
			continue;
		}
		const key = bucketRecord.key;
		const label = bucketRecord.key_as_string;
		const count = bucketRecord.doc_count;
		if (
			(typeof key !== "number" && typeof key !== "bigint") ||
			label === undefined ||
			(typeof count !== "number" && typeof count !== "bigint")
		) {
			continue;
		}
		rows.push([Number(key), String(label), Number(count)]);
	}

	rows.sort((a, b) => a[0] - b[0]);
	return rows.map(([, label, count]) => [label, count]);
};

const extractPointsWithKey = (
	trendBuckets: Array<Record<string, unknown>>,
): Array<[number | null, string, number]> => {
	const points: Array<[number | null, string, number]> = [];
	for (const bucket of trendBuckets) {
		const bucketRecord = asRecord(bucket);
		if (!bucketRecord) {
			continue;
		}
		const label = bucketRecord.key_as_string;
		const key = bucketRecord.key;
		const count = bucketRecord.doc_count;
		if (label === undefined || typeof count !== "number") {
			continue;
		}
		const keyNum =
			typeof key === "number"
				? key
				: typeof key === "bigint"
					? Number(key)
					: null;
		points.push([keyNum, String(label), Number(count)]);
	}
	return points;
};

export const extractGroupSeries = (
	payload: unknown,
	group: string,
): Array<{ group: string; doc_count: number; points: TrendPoint[] }> => {
	const payloadRecord = asRecord(payload);
	const aggregations = asRecord(payloadRecord?.aggregations);
	const groupAgg = asRecord(aggregations?.[group]);
	const groupInner = asRecord(groupAgg?.[group]);
	const groupBuckets = groupInner?.buckets;
	if (!Array.isArray(groupBuckets)) {
		return [];
	}

	const series: Array<{
		group: string;
		doc_count: number;
		points: TrendPoint[];
	}> = [];
	for (const bucket of groupBuckets) {
		const bucketRecord = asRecord(bucket);
		if (!bucketRecord) {
			continue;
		}
		const groupKey = bucketRecord.key;
		const docCount = bucketRecord.doc_count;
		const trendPeriod = asRecord(bucketRecord.trend_period);
		const trendBuckets = trendPeriod?.buckets;
		if (groupKey === undefined || !Array.isArray(trendBuckets)) {
			continue;
		}
		const pointsWithKey = extractPointsWithKey(trendBuckets);
		const hasKey = pointsWithKey.some(([key]) => key !== null);
		pointsWithKey.sort((a, b) => {
			if (hasKey) {
				const aKey = a[0] ?? Number.MAX_SAFE_INTEGER;
				const bKey = b[0] ?? Number.MAX_SAFE_INTEGER;
				return aKey - bKey;
			}
			return a[1].localeCompare(b[1]);
		});
		const points = pointsWithKey.map(
			([, label, count]) => [label, count] as TrendPoint,
		);
		series.push({
			group: String(groupKey),
			doc_count:
				typeof docCount === "number" ? docCount : Number(docCount ?? 0),
			points,
		});
	}

	return series;
};

export const computeSimpleSignals = (
	points: TrendPoint[],
	baselineWindow = 8,
	minBaselineMean = 10,
): Record<string, unknown> => {
	if (points.length < MIN_SIGNAL_POINTS) {
		return { error: "not_enough_points", num_points: points.length };
	}
	const labels = points.map(([label]) => label);
	const values = points.map(([, value]) => value);

	const lastLabel = labels[labels.length - 1];
	const lastVal = values[values.length - 1];
	const prevLabel = labels[labels.length - 2];
	const prevVal = values[values.length - 2];

	const lastVsPrevPct = prevVal > 0 ? lastVal / prevVal - 1 : null;
	const baselineValues =
		values.length > MIN_BASELINE_POINTS
			? values.slice(-(baselineWindow + 1), -1)
			: [];
	const baselineMean = baselineValues.length ? mean(baselineValues) : null;
	const baselineSd = baselineValues.length ? stddev(baselineValues) : null;

	let ratio: number | null = null;
	let z: number | null = null;
	if (
		baselineMean !== null &&
		baselineMean >= minBaselineMean &&
		baselineSd !== null
	) {
		ratio = baselineMean > 0 ? lastVal / baselineMean : null;
		z = baselineSd > 0 ? (lastVal - baselineMean) / baselineSd : null;
	}

	return {
		num_points: points.length,
		last_bucket: { label: lastLabel, count: lastVal },
		prev_bucket: { label: prevLabel, count: prevVal },
		signals: {
			last_vs_prev: { abs: lastVal - prevVal, pct: lastVsPrevPct },
			last_vs_baseline: {
				baseline_window: baselineWindow,
				baseline_mean: baselineMean,
				baseline_sd: baselineSd,
				ratio,
				z,
				min_baseline_mean: minBaselineMean,
			},
		},
	};
};

export const companyBucketsFromSearch = (
	payload: unknown,
): Array<[string, number]> => {
	const payloadRecord = asRecord(payload);
	const aggregations = asRecord(payloadRecord?.aggregations);
	const companyAgg = asRecord(aggregations?.company);
	const companyInner = asRecord(companyAgg?.company);
	const buckets = companyInner?.buckets;
	if (!Array.isArray(buckets)) {
		return [];
	}
	const out: Array<[string, number]> = [];
	for (const bucket of buckets) {
		const bucketRecord = asRecord(bucket);
		if (!bucketRecord) {
			continue;
		}
		const key = bucketRecord.key;
		const count = bucketRecord.doc_count;
		if (typeof key !== "string" || typeof count !== "number") {
			continue;
		}
		out.push([key, count]);
	}
	return out.sort((a, b) => b[1] - a[1]);
};
