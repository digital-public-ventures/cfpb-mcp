import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { WebStandardStreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/webStandardStreamableHttp.js";
import { handlers, toolSpecs } from "./tools/handlers.js";
import {
	hashKeyPrefix,
	rateLimitAllows,
	validateApiKey,
} from "./utils/security.js";

type Env = {
	CFPB_MCP_API_KEYS?: string;
	CFPB_MCP_RATE_LIMIT_RPS?: string;
	CFPB_MCP_RATE_LIMIT_BURST?: string;
};

const logMcpEvent = (label: string, payload: Record<string, unknown>) => {
	console.log(`[mcp-worker] ${label} ${JSON.stringify(payload)}`);
};

const parseJson = (text: string): unknown => {
	if (!text) {
		return null;
	}
	try {
		return JSON.parse(text);
	} catch {
		return null;
	}
};

const createServer = () => {
	const server = new McpServer({
		name: "cfpb-mcp",
		version: "1.0.0",
	});
	for (const spec of toolSpecs) {
		server.registerTool(
			spec.name,
			{
				description: spec.description,
				inputSchema: spec.inputSchema,
			},
			async (args: Record<string, unknown>) =>
				handlers[spec.name as keyof typeof handlers](args),
		);
	}
	return server;
};

const jsonResponse = (payload: unknown, status = 200) =>
	new Response(JSON.stringify(payload), {
		status,
		headers: { "content-type": "application/json" },
	});

const handleMcp = async (
	request: Request,
	env: Env,
	apiKey: string | null,
): Promise<Response> => {
	if (!validateApiKey(apiKey, env.CFPB_MCP_API_KEYS)) {
		return new Response("Unauthorized", { status: 401 });
	}

	const bucketId = apiKey || "anon";
	if (
		!rateLimitAllows(
			bucketId,
			env.CFPB_MCP_RATE_LIMIT_RPS,
			env.CFPB_MCP_RATE_LIMIT_BURST,
		)
	) {
		return new Response("Too Many Requests", { status: 429 });
	}

	const server = createServer();
	const transport = new WebStandardStreamableHTTPServerTransport({
		sessionIdGenerator: undefined,
		enableJsonResponse: true,
	});
	await server.connect(transport);
	return transport.handleRequest(request);
};

export default {
	async fetch(request: Request, env: Env): Promise<Response> {
		const url = new URL(request.url);
		if (url.pathname === "/health") {
			return jsonResponse({ status: "ok" });
		}
		if (url.pathname !== "/mcp") {
			return jsonResponse(
				{
					name: "cfpb-mcp",
					message: "CFPB MCP worker is running.",
					mcp: { http: "/mcp" },
				},
				200,
			);
		}

		const apiKey = request.headers.get("x-api-key");
		try {
			const requestClone = request.clone();
			const requestText = await requestClone.text();
			const requestJson = parseJson(requestText);
			logMcpEvent("request", {
				url: request.url,
				method: request.method,
				api_key: hashKeyPrefix(apiKey),
				body: requestText,
				json: requestJson,
			});

			const response = await handleMcp(request, env, apiKey);
			const responseClone = response.clone();
			const responseText = await responseClone.text();
			const responseJson = parseJson(responseText);
			logMcpEvent("response", {
				status: response.status,
				body: responseText,
				json: responseJson,
			});
			return response;
		} catch (error) {
			const message = error instanceof Error ? error.message : String(error);
			logMcpEvent("error", {
				message,
				api_key: hashKeyPrefix(apiKey),
			});
			return jsonResponse(
				{ error: message, api_key: hashKeyPrefix(apiKey) },
				500,
			);
		}
	},
};
