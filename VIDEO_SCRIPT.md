# Demo video script (~2:00)

**0:00–0:15 · Hook** (screen: graph view)
"I'm a solo freelancer. My business is spread across five platforms, chats and payments. This is Freelance Brain: my whole business as a FalkorDB graph, with an agent that answers questions and shows its work."

**0:15–0:35 · The graph** (hover nodes: blue clients, orange orders, red platforms, green services, yellow stars = decisions)
"Clients place orders through platforms. Orders are for services that need skills. Messages and payments hang off orders. Decisions are nodes too, linked to the message that triggered them. All data here is synthetic."

**0:35–0:55 · Q1** click "Which clients bring the most revenue?"
"Gemini picks a curated tool. Here's the answer, the exact Cypher it ran, and the rows. The clients light up in the graph."

**0:55–1:10 · Q2** click "Where do orders come from and what do fees cost me?"
"Net versus gross per platform, so I can see what each platform's commission actually costs me."

**1:10–1:30 · Q3** click "Why did we decide things? Trace decisions"
"This is the company-brain part: every decision traces back to its source message and the order it affected."

**1:30–1:45 · Q4** type "How many orders per month in 2026?"
"No tool for this one, so the agent writes Cypher itself. It runs read-only with a timeout, and if FalkorDB rejects the query, the error goes back for one repair."

**1:45–2:00 · Wrap** (terminal: `docker compose up`, `pytest -q` → 14 passed)
"One command with Docker, or embedded FalkorDB with no setup at all. Track 3, Company Brain. Thanks!"
