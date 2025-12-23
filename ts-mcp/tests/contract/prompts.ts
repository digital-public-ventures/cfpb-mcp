export const SYSTEM_PROMPT =
  "You are a CFPB complaint analyst. Use the MCP tools to find a relevant complaint. " +
  "Respond with the complaint id, company (if present), state (if present), and a 2-3 sentence summary grounded in the complaint.";

export const USER_PROMPT =
  "I'm researching CFPB consumer complaints about loan forbearance. Please find a complaint mentioning 'forbearance' where the company name is present, then tell me the complaint id, the company (if present), the state (if present), and a short 2-3 sentence summary grounded in the complaint. If you can't use tools, say 'MCP tools unavailable'.";
