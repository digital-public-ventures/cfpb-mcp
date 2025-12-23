import { sha256 } from "js-sha256";

type TokenBucketOptions = {
	capacity: number;
	refillPerSec: number;
	now: number;
};

class TokenBucket {
	capacity: number;
	refillPerSec: number;
	tokens: number;
	last: number;

	constructor(options: TokenBucketOptions) {
		this.capacity = options.capacity;
		this.refillPerSec = options.refillPerSec;
		this.tokens = options.capacity;
		this.last = options.now;
	}

	consume(now: number, amount = 1): boolean {
		const elapsed = Math.max(0, now - this.last);
		this.last = now;
		this.tokens = Math.min(
			this.capacity,
			this.tokens + elapsed * this.refillPerSec,
		);
		if (this.tokens >= amount) {
			this.tokens -= amount;
			return true;
		}
		return false;
	}
}

const buckets = new Map<string, TokenBucket>();

const timingSafeEqual = (a: string, b: string): boolean => {
	const encoder = new TextEncoder();
	const aBytes = encoder.encode(a);
	const bBytes = encoder.encode(b);
	if (aBytes.length !== bBytes.length) {
		return false;
	}
	let diff = 0;
	for (let i = 0; i < aBytes.length; i += 1) {
		diff |= aBytes[i] ^ bBytes[i];
	}
	return diff === 0;
};

export const getAllowedApiKeys = (rawKeys?: string): string[] => {
	if (!rawKeys) {
		return [];
	}
	return rawKeys
		.split(",")
		.map((key) => key.trim())
		.filter(Boolean);
};

export const validateApiKey = (
	apiKey: string | null,
	rawKeys?: string,
): boolean => {
	const allowed = getAllowedApiKeys(rawKeys);
	if (!allowed.length) {
		return true;
	}
	if (!apiKey) {
		return false;
	}
	return allowed.some((key) => timingSafeEqual(apiKey, key));
};

export const rateLimitAllows = (
	bucketId: string,
	rps?: string,
	burst?: string,
): boolean => {
	const rpsNum = Number.parseFloat(rps ?? "0");
	const burstNum = Number.parseFloat(burst ?? "0");
	if (!rpsNum || !burstNum) {
		return true;
	}
	const now = performance.now() / 1000;
	let bucket = buckets.get(bucketId);
	if (!bucket) {
		bucket = new TokenBucket({ capacity: burstNum, refillPerSec: rpsNum, now });
		buckets.set(bucketId, bucket);
	}
	return bucket.consume(now);
};

export const hashKeyPrefix = (apiKey: string | null): string => {
	if (!apiKey) {
		return "none";
	}
	return sha256(apiKey).slice(0, 8);
};
