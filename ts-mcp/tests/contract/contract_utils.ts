const asRecord = (value: unknown): Record<string, unknown> | null => {
	if (!value || typeof value !== "object") {
		return null;
	}
	return value as Record<string, unknown>;
};

export const extractComplaintIdFromSearch = (
	payload: unknown,
): number | null => {
	const payloadRecord = asRecord(payload);
	const dataRecord = asRecord(payloadRecord?.data);
	const hitsRecord = asRecord(dataRecord?.hits);
	const hits = hitsRecord?.hits;
	if (!Array.isArray(hits) || !hits.length) {
		return null;
	}
	const hit0 = asRecord(hits[0]);
	const raw = hit0?._id ?? asRecord(hit0?._source)?.complaint_id ?? null;
	if (!raw) {
		return null;
	}
	const id = Number.parseInt(String(raw), 10);
	if (!Number.isFinite(id)) {
		return null;
	}
	const len = String(id).length;
	return len >= 4 && len <= 9 ? id : null;
};

export const extractCompanyFromDocument = (payload: unknown): string => {
	const payloadRecord = asRecord(payload);
	const hitsRecord = asRecord(payloadRecord?.hits);
	const hits = hitsRecord?.hits;
	let source = payloadRecord;
	if (Array.isArray(hits) && hits.length) {
		const hit0 = asRecord(hits[0]);
		source = asRecord(hit0?._source) ?? payloadRecord;
	}
	const company = source?.company;
	return String(company ?? "").trim();
};

export const extractComplaintIdFromText = (text: string): number | null => {
	const matches = text.match(/\b\d{4,9}\b/g);
	if (!matches || !matches.length) {
		return null;
	}
	const token = matches.sort((a, b) => b.length - a.length)[0];
	const id = Number.parseInt(token, 10);
	if (!Number.isFinite(id)) {
		return null;
	}
	const len = String(id).length;
	return len >= 4 && len <= 9 ? id : null;
};
