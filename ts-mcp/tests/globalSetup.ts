import { spawn } from "node:child_process";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { config as loadEnv } from "dotenv";

const waitForHealth = async (url: string, timeoutMs = 30000) => {
	const deadline = Date.now() + timeoutMs;
	while (Date.now() < deadline) {
		try {
			const res = await fetch(url, { method: "GET" });
			if (res.ok) {
				return;
			}
		} catch {
			// retry
		}
		await new Promise((resolve) => setTimeout(resolve, 300));
	}
	throw new Error(`Worker did not become healthy at ${url}`);
};

export default async function globalSetup() {
	const here = dirname(fileURLToPath(import.meta.url));
	const root = resolve(here, "..");
	loadEnv({ path: resolve(root, "..", ".env") });
	process.env.TEST_SERVER_URL = "http://127.0.0.1:8787/mcp";

	const proc = spawn(
		process.platform === "win32" ? "npx.cmd" : "npx",
		["wrangler", "dev", "--local", "--port", "8787", "--ip", "127.0.0.1"],
		{
			cwd: root,
			stdio: ["ignore", "pipe", "pipe"],
			env: {
				...process.env,
			},
		},
	);

	proc.stdout?.on("data", (data) => {
		process.stdout.write(data);
	});
	proc.stderr?.on("data", (data) => {
		process.stderr.write(data);
	});

	await waitForHealth("http://127.0.0.1:8787/health");

	return async () => {
		proc.kill("SIGTERM");
		await new Promise((resolve) => {
			proc.on("close", resolve);
			setTimeout(resolve, 5000);
		});
	};
}
