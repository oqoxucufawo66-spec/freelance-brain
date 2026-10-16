# I Gave My Freelance Business a Brain: Building a Company-Brain Agent on FalkorDB

*Graph Hacks 2026 · Track 03: Company Brain · by Vladimir Matusevichus (team "Vladimir Solo")*

## The problem: a one-person company with ten tabs open

I run a small freelance studio. I build Telegram bots, marketplace ad automation, landing pages and 3D interior renders.
Orders come from Kwork, FL.ru, Avito, Upwork and word of mouth. Each platform has its own chat, its own fee and its own
idea of what a "client" is. Payments arrive later and land somewhere else. Decisions like "we'll do this feature for
free because the client is on a support retainer" sit in a chat message I can never find again.

The questions I care about are relational: *Which clients actually make me money after platform fees? Which platform is
worth the commission? Who referred whom, and was that referral worth it? Why did I agree to that change?* A spreadsheet
can't answer these without a lot of VLOOKUPs, and an LLM over a pile of chat logs makes things up. A graph handles them
naturally, so for Graph Hacks I built **Freelance Brain**: a company-brain agent backed by FalkorDB.

## What it does

You open a web page with an interactive graph of the business on the right and a chat box on the left. You ask:

- "Which clients bring the most revenue?"
- "Where do orders come from and what do fees cost me?"
- "Show referral chains"
- "Why did we decide things? Trace decisions"
- …or anything else, like "How many orders per month in 2026?"

Every answer comes with three things: a short natural-language summary with real numbers, **the exact Cypher query that
produced it**, and the raw rows. The nodes involved light up in the graph. The aim is an agent you can audit, not one you
have to trust.

All the data in the public demo is synthetic. A deterministic generator produces 30 clients, about 60 orders, about 150
messages and 6 decisions that mirror the shape of my real business without exposing a single real name.

## The graph model

The model is intentionally small:

```
(Client)-[:PLACED]->(Order)-[:FOR_SERVICE]->(Service)-[:REQUIRES]->(Skill)
(Order)-[:VIA]->(Platform)          (Order)-[:PAID_BY]->(Payment)
(Client)-[:SENT]->(Message)-[:ABOUT]->(Order)
(Client)-[:IN_INDUSTRY]->(Industry) (Client)-[:REFERRED]->(Client)
(Decision)-[:BASED_ON]->(Message)   (Decision)-[:AFFECTS]->(Order)
```

The two edges that make this a *company brain* rather than a CRM are `Decision-[:BASED_ON]->Message` and
`Decision-[:AFFECTS]->Order`. A decision is a first-class node. It points back to the message that triggered it and
forward to the work it changed. "Why did we re-render that view?" stops being archaeology and becomes a two-hop query
that returns the decision, its rationale, the source message id, the client and the order.

Payments store both `amount` and `net` (after the platform's fee), so platform economics fall out of a single traversal.
`REFERRED` is a client-to-client edge, and variable-length paths (`[:REFERRED*1..3]`) show referral chains plus the
revenue each chain eventually produced. That multi-hop question is painful in SQL and natural in Cypher.

## How the agent works

The agent is a small planner wrapped around FalkorDB:

1. **Plan.** Gemini receives the graph schema, a menu of curated tools (named, tested Cypher queries) and the question.
   It replies with JSON: either `{"tool": "platform_mix"}` or `{"cypher": "MATCH …"}`.
2. **Guard.** Generated Cypher passes through a read-only guard. Any `CREATE/MERGE/SET/DELETE` is rejected, and the
   query runs through FalkorDB's `GRAPH.RO_QUERY` with a 5-second timeout. The agent can explore, but it can't damage the graph.
3. **Self-repair.** If FalkorDB rejects a generated query (on my first run the model reached for `datetime()` on string
   dates), the error message goes back to the model once, together with the schema, and the repaired query runs.
4. **Summarize.** The rows go back to Gemini for a 2–4 sentence answer with concrete numbers. The UI shows the answer,
   the Cypher, the rows and an execution trace.
5. **Degrade gracefully.** With no API key, or when the model is rate-limited (which happened to me *during* the
   hackathon), the agent falls back to keyword routing over the curated tools and a model fallback chain. The demo never
   shows a stack trace.

Curated tools plus free-form text-to-Cypher is, in my view, the right split. The questions you ask every week get
fast, correct, tested queries. The long tail goes to the LLM, inside guardrails.

## Running it

FalkorDB made two deployment modes nearly free. `docker compose up` starts the FalkorDB server (with its browser UI on
port 3000) next to the Flask app. For zero-setup development I used **falkordblite**, an embedded FalkorDB that runs
in-process from a pip install. The same `select_graph()` / `query()` API works in both modes, so switching is just an
environment variable. Loading uses `UNWIND $rows … CREATE` batched per label and per relationship type, plus an index on
`id` for every label. The whole graph loads in well under a second.

A 14-test pytest suite checks that the seed is deterministic, that no real-looking names appear, that every curated
tool returns rows, that writes are blocked, and that decision answers always carry a source message id.

## What I learned

- **Model the "why", not just the "what".** Adding `Decision` as a node took ten lines and became the most useful
  feature. Provenance is a graph problem.
- **Ground the LLM in the schema and the dialect.** Text-to-Cypher got much more reliable once the prompt said
  "dates are strings YYYY-MM-DD; use `substring()`", and once database errors were fed back for one repair attempt.
- **Show your work.** Returning the Cypher next to every answer changed how I trust the tool. When a number looks off,
  I can read the query instead of arguing with a chatbot.
- **Plan for the LLM being down.** Rate limits are real. Curated tools and fallbacks kept the demo alive.
- **Embedded graph databases are underrated** for hackathons and personal tools. I didn't need any infrastructure until
  I wanted the Docker demo.

## What's next

Next I want to connect real exports from freelance platforms (anonymized on ingest) and add an agent that writes back:
proposing follow-ups to at-risk clients, flagging scope creep against the original spec, and storing every new
decision with its source message automatically.

*Repo: (link after publishing) · Demo video: (link)*
