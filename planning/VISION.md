# Vision for a CFPB MCP Server

<!--
DANGER: AGENTS MUST NOT MODIFY THIS FILE.
This file is governed by automation and/or repository policies; manual edits will be overwritten.
To request changes, open an issue or submit a pull request to repository maintainers.
-->

> NOTE: Agents DO NOT MODIFY THIS FILE. The hash is being tracked outside of this system.

I want to build an MCP server for the CFPB api. Swagger is here: [CFPB CCDB5 API documentation](https://cfpb.github.io/ccdb5-api/documentation/).

Field reference is here: [CCDB Field Reference](https://cfpb.github.io/api/ccdb/fields.html).

This is the GitHub for CFPB's search and visualization harness, which is super useful: [cfpb/ccdb5-ui](https://github.com/cfpb/ccdb5-ui).

Here's the GitHub repo for the API: [cfpb/ccdb5-api](https://github.com/cfpb/ccdb5-api).

We want the MCP server to enable agents to help users in at least the following ways:

```use case
1. Arming the Advocates.  
This is mostly what we talked about on Tuesday -- it would be amazing to arm advocates with some great stories from the database that follow the fact pattern we discussed (sympathetic figures like students, elderly, service members/veterans, who were screwed over and left hanging and eventually got a monetary resolution after they made their CFPB complaint). 

I think here, one thing we'd be demonstrating is that our technology could find, for example, a supbrime auto story in Ohio (so understand the data well enough to search on two elements). So maybe one way to structure the project (and limit the scope) is to pick a couple of years, and find a constituent story for each member of the Senate Banking Committee or the House Financial Services Committee. If we can swing it, I could also give you a set of topics/consumer products (student loans, mortgages, bank fees, mortgages, auto loans etc) and we see if we can pull stories on specific topics for specific members.

Separately, one thing a lot of people are interested in understanding is how real people talk about issues we are thinking about in Washington. It would also be interested in doing some sort of word association product. How are the consumers (complainants) talking about subprime loans now? What is the source of their frustration? What about banks? Venmo? 

2. Telling the story of the impact of the CFPB. 
It would be interesting to tell some stories about the evolution and maturation of the CFPB. CFPB has basically had four-ish epochs: 
2010-2011: The standup, before it had legal authorities. Elizabeth Warren was in charge. It was a sprinty startup. I'm not sure when the database came online.
2011-2017: Childhood and adolescence. CFPB hires people, gets authority and starts to use it. Attracts the very best people. In this era, it would be interesting to see the growth of complaints. When do they start to go national? There was serious outreach with military families and veterans, same with students and seniors. Can you see different populations come online at different times? Also I would expect mortgages to start as a larger proportion of complaints at the beginning after the financial crisis and then diminish.
2017-2020: What happened to complaints during the Trump administration? I don't actually know. Do you see evidence of worsening behavior by institutions? 
2021-2024: Are you seeing more people complain about junk fees as the bureau takes action against them? I expect you would see more complaints against fintechs and non-banks
3. (Potentially the coolest) Standing in as the Regulator in the Absence of the CFPB
In 2025, even as all the CFPB employees were fired, complaints increased by 50% (though nobody at CFPB was monitoring them). What can we learn about the consumer markets now that is actionable?
There are some basic things -- what are the top complaints? What companies are getting the most complaints? There is reporting that debt collection practices and overdraft fees have gone back to the bad old days already. Interested if you see that in the data. 
What's different from last year? Some companies always get a lot of complaints (Equifax) but are there any companies where complaints have exploded this year? Or any kinds of complaints (e.g., overdraft fees)
There are some markets that the consumer world is really worried about -- Buy Now/Pay Later (Affirm, Klarna), private student loans, auto loans (especially subprime), crypto. What are we seeing?
Are there any emergencies that the CFPB missed? For example, in 2021, CFPB caught that the Rush card had an outage (and a ton of consumers lost access to their money) and was able to take action immediately because they saw consumer complaints pouring in. Is there anything similar.
```

The API has a lot of useful ways to search, and the database harness on GitHub is super duper useful, but one challenge is that there's no semantic search, so the MCP server would need to extrapolate a user's natural language query into potentially viable keywords and then be ready to parse through lots of junk to find matching complaints.

This MCP server will be private for now, so on the server side, we can actually run our own agent-assisted workflows that we know will be repeatedly useful and that we don't want to leave to chance with respect to the behavior of the agent who is calling the MCP functions.

## CRITICAL REQUIREMENTS

1. We absolutely must be able to properly cite every access we make to the database with a deeplink URL that goes directly to the complaint in the CFPB UI. This is non-negotiable. The viability of the entire project depends on humans being able to verify the complaints data (both individual complaints and aggregate data) that the MCP server returns.
2. The above is necessary but not sufficient. The success of the MCP server will also depend on the ability of the server to act as a copilot for humans who are trying to accomplish the tasks outlined in the use cases above. This means that the MCP server must be able to intelligently combine multiple API calls, filter and sort results, and summarize findings in a way that is useful for humans while also providing the ironclad citations and traceability. Providing deeplink URLs to web views that are served at consumerfinance.gov is a key part of this, but we can do even better by using the CFPB's data visualization harness directly instead of trying to do it ourselves.
3. A stretch goal will be to use the structure of our MCP server creatively to constrain the behavior of the calling agents in a way that makes them more reliable and predictable. For example, we might want to build a set of standard agent workflows that are known to work well for the use cases above, and then have the MCP server guide the calling agents to use those workflows instead of trying to improvise on their own. This could involve providing detailed prompts or templates for the agents to follow, perhaps something like a "suggestions" endpoint, or even returning guardrails or guidance as an additional key part of the MCP response.
