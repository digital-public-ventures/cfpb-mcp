const LOCAL_SERVER_URL = "http://127.0.0.1:8787/mcp";
const REMOTE_SERVER_URL = "https://cfpb-mcp.jimmoffet.workers.dev/mcp";

const parseArgs = (argv) => {
	const args = { url: null };
	for (let i = 2; i < argv.length; i += 1) {
		const token = argv[i];
		if (token === "--remote") {
			args.url = REMOTE_SERVER_URL;
		} else if (token === "--local") {
			args.url = LOCAL_SERVER_URL;
		} else if (token === "--url") {
			args.url = argv[i + 1] ?? null;
			i += 1;
		}
	}
	return args;
};

const buildRpc = (id, method, params) => ({
	jsonrpc: "2.0",
	id,
	method,
	params,
});

const logHeader = (label) => {
	console.log(`\n=== ${label} ===`);
};

const callRpc = async (url, rpc) => {
	const response = await fetch(url, {
		method: "POST",
		headers: {
			"content-type": "application/json",
			accept: "application/json, text/event-stream",
		},
		body: JSON.stringify(rpc),
	});
	const text = await response.text();
	let parsed = null;
	try {
		parsed = JSON.parse(text);
	} catch {
		parsed = null;
	}
	return {
		status: response.status,
		headers: Object.fromEntries(response.headers.entries()),
		text,
		parsed,
	};
};

const main = async () => {
	const args = parseArgs(process.argv);
	const url = args.url || process.env.TEST_SERVER_URL || LOCAL_SERVER_URL;
	console.log("[mcp-probe] url", url);

	let rpcId = 0;
	const calls = [
		{ label: "tools/list", method: "tools/list", params: undefined },
		{
			label: "search_complaints basic",
			method: "tools/call",
			params: {
				name: "search_complaints",
				arguments: { search_term: "forbearance", size: 10 },
			},
		},
		{
			label: "search_complaints product filter",
			method: "tools/call",
			params: {
				name: "search_complaints",
				arguments: {
					product: ["Mortgage"],
					search_term: "forbearance",
					size: 10,
				},
			},
		},
		{
			label: "search_complaints minimal",
			method: "tools/call",
			params: {
				name: "search_complaints",
				arguments: { size: 5 },
			},
		},
		{
			label: "list_complaint_trends invalid",
			method: "tools/call",
			params: {
				name: "list_complaint_trends",
				arguments: { lens: "product", trend_depth: 6 },
			},
		},
		{
			label: "list_complaint_trends valid",
			method: "tools/call",
			params: {
				name: "list_complaint_trends",
				arguments: {
					lens: "product",
					search_term: "forbearance",
					sub_lens: "issue",
					trend_depth: 12,
				},
			},
		},
		{
			label: "get_overall_trend_signals",
			method: "tools/call",
			params: {
				name: "get_overall_trend_signals",
				arguments: { search_term: "forbearance", trend_depth: 12 },
			},
		},
		{
			label: "suggest_filter_values",
			method: "tools/call",
			params: {
				name: "suggest_filter_values",
				arguments: { field: "company", text: "wells" },
			},
		},
	];

	for (const call of calls) {
		rpcId += 1;
		logHeader(call.label);
		const rpc = buildRpc(rpcId, call.method, call.params);
		console.log(
			"[mcp-probe] request",
			JSON.stringify({ id: rpc.id, method: rpc.method, params: rpc.params }),
		);
		const result = await callRpc(url, rpc);
		console.log(
			"[mcp-probe] response",
			JSON.stringify({
				status: result.status,
				body: result.text,
				json: result.parsed,
			}),
		);
		if (result.parsed) {
			console.log(JSON.stringify(result.parsed, null, 2));
		} else {
			console.log(result.text);
		}
	}
};

main().catch((err) => {
	console.error("probe failed:", err);
	process.exitCode = 1;
});
