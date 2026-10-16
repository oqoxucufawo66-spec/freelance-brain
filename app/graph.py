import os, re
from collections import defaultdict
from .seed import build

GRAPH = os.getenv("GRAPH_NAME", "freelance_brain")

def connect():
    host = os.getenv("FALKORDB_HOST")
    if host:
        from falkordb import FalkorDB
        db = FalkorDB(host=host, port=int(os.getenv("FALKORDB_PORT", 6379)))
    else:  # embedded FalkorDB (falkordblite) for zero-setup local runs
        from redislite.falkordb_client import FalkorDB
        db = FalkorDB(os.getenv("FALKORDB_FILE", "/tmp/freelance_brain.db"))
    return db.select_graph(GRAPH)

def load(g, seed=42):
    try: g.delete()
    except Exception: pass
    nodes, rels = build(seed)
    by = defaultdict(list)
    for label, p in nodes: by[label].append(p)
    for label, rows in by.items():
        g.query(f"UNWIND $rows AS r CREATE (n:{label}) SET n = r", {"rows": rows})
        g.query(f"CREATE INDEX FOR (n:{label}) ON (n.id)")
    rb = defaultdict(list)
    for a, t, b, p in rels: rb[t].append({"a": a, "b": b, "p": p})
    for t, rows in rb.items():
        g.query(f"UNWIND $rows AS r MATCH (a {{id:r.a}}), (b {{id:r.b}}) CREATE (a)-[x:{t}]->(b) SET x = r.p", {"rows": rows})
    return len(nodes), len(rels)

SCHEMA = """Nodes: Client{id,name,since} Platform{id,name,fee_pct} Service{id,name,base_price} Skill{id,name}
Industry{id,name} Order{id,title,price,status('done'|'in_progress'|'cancelled'),created} Payment{id,amount,net,paid}
Message{id,topic,sentiment,text,at} Decision{id,title,rationale,at}
Edges: (Client)-[:PLACED]->(Order) (Order)-[:FOR_SERVICE]->(Service) (Order)-[:VIA]->(Platform)
(Order)-[:PAID_BY]->(Payment) (Client)-[:SENT]->(Message)-[:ABOUT]->(Order) (Client)-[:IN_INDUSTRY]->(Industry)
(Client)-[:REFERRED]->(Client) (Service)-[:REQUIRES]->(Skill) (Decision)-[:BASED_ON]->(Message) (Decision)-[:AFFECTS]->(Order)"""

WRITE = re.compile(r"\b(CREATE|MERGE|DELETE|DETACH|SET|REMOVE|DROP|LOAD|CALL\s+db\.idx)\b", re.I)

def safe_ro(g, cypher, params=None):
    if WRITE.search(cypher): raise ValueError("write clauses are not allowed")
    return g.ro_query(cypher, params or {}, timeout=5000)
