SYSTEM_PROMPT = (
    'You are an assistant that must use the provided MCP tools to answer. '
    'Always include the complaint id in the final response when available.'
)

USER_PROMPT = (
    "I'm researching CFPB consumer complaints about loan forbearance. "
    "Please find a complaint mentioning 'forbearance' where the company name is present, then tell me the complaint id, "
    'the company (if present), the state (if present), and a short 2-3 sentence summary grounded in the complaint. '
    "If you can't use tools, say 'MCP tools unavailable'."
)
