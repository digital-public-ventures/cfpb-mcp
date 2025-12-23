let rpcId = 0;

export const LOCAL_SERVER_URL = "http://127.0.0.1:8787/mcp";
export const REMOTE_SERVER_URL = "https://cfpb-mcp.jimmoffet.workers.dev/mcp";

export const resolveServerUrl = (): string => {
	if (process.env.TEST_SERVER_TARGET === "local") {
		return LOCAL_SERVER_URL;
	}
	if (process.env.TEST_SERVER_TARGET === "remote") {
		return REMOTE_SERVER_URL;
	}
	if (process.env.TEST_SERVER_URL) {
		return process.env.TEST_SERVER_URL;
	}
	return LOCAL_SERVER_URL;
};

export const callRpc = async (
	serverUrl: string,
	method: string,
	params?: Record<string, unknown>,
) => {
	const attempts = 3;
	let lastError: Error | null = null;
	for (let attempt = 1; attempt <= attempts; attempt += 1) {
		rpcId += 1;
		const response = await fetch(serverUrl, {
			method: "POST",
			headers: {
				"content-type": "application/json",
				accept: "application/json, text/event-stream",
			},
			body: JSON.stringify({
				jsonrpc: "2.0",
				id: rpcId,
				method,
				params,
			}),
		});

		const text = await response.text();
		let payload: unknown;
		try {
			payload = JSON.parse(text);
		} catch {
			lastError = new Error(
				`rpc_error: status=${response.status} body=${text.slice(0, 200)}`,
			);
			if (attempt < attempts && response.status >= 500) {
				await new Promise((resolve) => setTimeout(resolve, 200 * attempt));
				continue;
			}
			throw lastError;
		}

		if (payload && typeof payload === "object" && "error" in payload) {
			const errorValue = (
				payload as { error?: { code?: unknown; message?: unknown } }
			).error;
			lastError = new Error(
				`${errorValue?.code ?? "rpc_error"}: ${errorValue?.message ?? "error"}`,
			);
			if (attempt < attempts && response.status >= 500) {
				await new Promise((resolve) => setTimeout(resolve, 200 * attempt));
				continue;
			}
			throw lastError;
		}
		if (payload && typeof payload === "object" && "result" in payload) {
			return (payload as { result: unknown }).result;
		}
		return payload;
	}
	throw lastError ?? new Error("rpc_error: exhausted retries");
};
