let rpcId = 0;

export const callRpc = async (
  serverUrl: string,
  method: string,
  params?: Record<string, unknown>
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
    let payload: any;
    try {
      payload = JSON.parse(text);
    } catch {
      lastError = new Error(
        `rpc_error: status=${response.status} body=${text.slice(0, 200)}`
      );
      if (attempt < attempts && response.status >= 500) {
        await new Promise((resolve) => setTimeout(resolve, 200 * attempt));
        continue;
      }
      throw lastError;
    }

    if (payload.error) {
      lastError = new Error(
        `${payload.error.code ?? "rpc_error"}: ${payload.error.message}`
      );
      if (attempt < attempts && response.status >= 500) {
        await new Promise((resolve) => setTimeout(resolve, 200 * attempt));
        continue;
      }
      throw lastError;
    }
    return payload.result;
  }
  throw lastError ?? new Error("rpc_error: exhausted retries");
};
