"""Graph agent: curated Cypher tools + LLM text-to-Cypher fallback. Every answer returns the Cypher it ran
and the node ids it used, so results are traceable to source."""
import json, os, re
from .graph import SCHEMA, safe_ro

TOOLS = {
 "top_clients": ("Clients ranked by net revenue (lifetime value)",
  """MATCH (c:Client)-[:PLACED]->(o:Order)-[:PAID_BY]->(p:Payment)
     RETURN c.name AS client, count(o) AS orders, sum(p.net) AS net_revenue ORDER BY net_revenue DESC LIMIT 10"""),
 "platform_mix": ("Where orders come from: orders, gross, net and fees lost per platform",
  """MATCH (o:Order)-[:VIA]->(pl:Platform) OPTIONAL MATCH (o)-[:PAID_BY]->(p:Payment)
     RETURN pl.name AS platform, count(o) AS orders, sum(coalesce(p.amount,0)) AS gross,
            sum(coalesce(p.net,0)) AS net, sum(coalesce(p.amount,0)-coalesce(p.net,0)) AS fees ORDER BY net DESC"""),
 "service_profit": ("Revenue per service and the skills it needs",
  """MATCH (s:Service)<-[:FOR_SERVICE]-(o:Order)-[:PAID_BY]->(p:Payment)
     WITH s, count(o) AS orders, sum(p.net) AS net, avg(p.net) AS avg_net
     OPTIONAL MATCH (s)-[:REQUIRES]->(k:Skill)
     RETURN s.name AS service, orders, net, toInteger(avg_net) AS avg_check, collect(k.name) AS skills ORDER BY net DESC"""),
 "referrals": ("Referral chains (multi-hop): who brought whom, and revenue those referrals generated",
  """MATCH path=(a:Client)-[:REFERRED*1..3]->(b:Client)
     OPTIONAL MATCH (b)-[:PLACED]->(:Order)-[:PAID_BY]->(p:Payment)
     RETURN a.name AS referrer, b.name AS referred, length(path) AS hops, sum(coalesce(p.net,0)) AS referred_net ORDER BY referred_net DESC"""),
 "decision_trace": ("Decisions with the message they were based on and the order they affected",
  """MATCH (d:Decision)-[:BASED_ON]->(m:Message)<-[:SENT]-(c:Client)
     OPTIONAL MATCH (d)-[:AFFECTS]->(o:Order)
     RETURN d.title AS decision, d.rationale AS why, m.id AS source_message, m.text AS source_text, c.name AS client, o.title AS order"""),
 "at_risk": ("Clients at risk: negative messages or cancelled orders",
  """MATCH (c:Client)-[:SENT]->(m:Message {sentiment:'negative'})
     WITH c, count(m) AS neg OPTIONAL MATCH (c)-[:PLACED]->(o:Order {status:'cancelled'})
     RETURN c.name AS client, neg AS negative_msgs, count(o) AS cancelled ORDER BY negative_msgs+cancelled DESC LIMIT 10"""),
 "industry_mix": ("Net revenue by client industry",
  """MATCH (i:Industry)<-[:IN_INDUSTRY]-(c:Client)-[:PLACED]->(:Order)-[:PAID_BY]->(p:Payment)
     RETURN i.name AS industry, count(DISTINCT c) AS clients, sum(p.net) AS net ORDER BY net DESC"""),
}
KEYWORDS = [("top_clients", r"client.*(revenue|money|best|top|value)|most revenue|ltv"),
            ("platform_mix", r"platform|where.*(come|from)|source|channel|fee"),
            ("service_profit", r"service|skill|profitab"),
            ("referrals", r"referr|recommend"),
            ("decision_trace", r"decision|why did|decided"),
            ("at_risk", r"risk|churn|unhappy|negative|cancel"),
            ("industry_mix", r"industr|niche|sector")]

def rows(res):
    cols = [h[1] if isinstance(h, (list, tuple)) else h for h in res.header]
    return [dict(zip(cols, r)) for r in res.result_set]

class LLM:
    def __init__(self):
        self.client = None
        key = os.getenv("GEMINI_API_KEY")
        if key:
            from google import genai
            self.client = genai.Client(api_key=key)
            self.models = os.getenv("GEMINI_MODELS", "gemini-flash-latest,gemini-3-flash-preview,gemini-flash-lite-latest").split(",")
    def __call__(self, prompt):
        import time
        for attempt, model in enumerate(self.models):
            try:
                r = self.client.models.generate_content(model=model, contents=prompt)
                return r.text.strip()
            except Exception as ex:
                err = ex
                time.sleep(1); continue  # try next model in the fallback chain
        if True:
            ex = err  # quota / network: degrade to deterministic tools instead of failing
            self.client = None
            raise LLMDown(str(ex)[:120])

class LLMDown(Exception): pass

def _route_kw(q):
    for t, pat in KEYWORDS:
        if re.search(pat, q, re.I): return t
    return None

def ask(g, q, llm=None):
    llm = llm if llm is not None else LLM()
    trace = []
    tool, cypher = None, None
    if llm and llm.client:
        menu = "\n".join(f"- {k}: {v[0]}" for k, v in TOOLS.items())
        try: plan = llm(f"""You route questions about a freelance business graph in FalkorDB.
Schema:\n{SCHEMA}\nTools:\n{menu}\nQuestion: {q}
Dates are strings YYYY-MM-DD: use substring(o.created,0,7) for months, no datetime().
Reply ONLY JSON: {{"tool": "<name>"}} if a tool answers it, else {{"cypher": "<read-only openCypher, LIMIT 25>"}}""")
        except LLMDown as ex: plan = "{}"; trace.append(f"LLM unavailable, keyword routing: {ex}")
        try:
            j = json.loads(re.sub(r"^```(json)?|```$", "", plan, flags=re.M).strip())
            tool, cypher = j.get("tool"), j.get("cypher")
        except Exception: trace.append(f"planner output not JSON: {plan[:120]}")
    if not tool and not cypher: tool = _route_kw(q)
    if not tool and not cypher:
        return {"answer": "I can answer about clients, platforms, services, referrals, decisions, risk and industries.",
                "tool": None, "cypher": None, "rows": [], "trace": trace}
    if tool in TOOLS: cypher = TOOLS[tool][1]
    try:
        data = rows(safe_ro(g, cypher))
    except Exception as ex:
        if not tool and llm and llm.client:  # self-heal: give the error back to the LLM once
            trace.append(f"generated Cypher failed: {ex}; repairing")
            cypher = re.sub(r"^```(cypher)?|```$", "", llm(f"Schema:\n{SCHEMA}\nThis FalkorDB openCypher failed with '{ex}':\n{cypher}\nDates are strings YYYY-MM-DD. Return ONLY the fixed read-only query."), flags=re.M).strip()
            data = rows(safe_ro(g, cypher))
        elif not tool and _route_kw(q):  # fall back to curated tool: fall back to curated tool
            trace.append(f"generated Cypher failed: {ex}"); tool = _route_kw(q); cypher = TOOLS[tool][1]
            data = rows(safe_ro(g, cypher))
        else: raise
    answer = None
    if llm and llm.client:
        try: answer = llm(f"Question: {q}\nGraph query result (JSON): {json.dumps(data[:25], default=str)}\n"
                     "Answer in 2-4 sentences with concrete numbers (RUB). Mention names exactly as in data.")
        except LLMDown as ex: trace.append(f"LLM unavailable for summary: {ex}")
    if answer is None and tool:
        answer = f"{TOOLS[tool][0]}. Top row: " + (json.dumps(data[0], ensure_ascii=False, default=str) if data else "no data")
    if answer is None: answer = f"{len(data)} rows returned by generated Cypher."
    return {"answer": answer, "tool": tool, "cypher": " ".join(cypher.split()), "rows": data[:25], "trace": trace}

def subgraph(g, limit=400):
    res = safe_ro(g, f"""MATCH (a)-[r]->(b) WHERE NOT a:Message AND NOT b:Message AND NOT b:Payment
        RETURN a.id, labels(a)[0], coalesce(a.name,a.title), type(r), b.id, labels(b)[0], coalesce(b.name,b.title) LIMIT {int(limit)}""")
    nodes, edges = {}, []
    for a, la, na, t, b, lb, nb in res.result_set:
        nodes[a] = {"id": a, "label": na, "group": la}; nodes[b] = {"id": b, "label": nb, "group": lb}
        edges.append({"from": a, "to": b, "label": t})
    return {"nodes": list(nodes.values()), "edges": edges}
