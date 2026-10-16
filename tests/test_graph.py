import os, pytest
os.environ.setdefault("FALKORDB_FILE", "/tmp/fb_test.db"); os.environ["GRAPH_NAME"] = "test_brain"
from app.graph import connect, load, safe_ro
from app.agent import ask, TOOLS, subgraph
from app.seed import build

class NoLLM: client = None

@pytest.fixture(scope="module")
def g():
    g = connect(); load(g); return g

def test_seed_deterministic(): assert build(1) == build(1)
def test_no_real_names():
    for label, p in build()[0]:
        if label == "Client": assert p["name"].startswith("Client-")
def test_load_counts(g):
    assert safe_ro(g, "MATCH (c:Client) RETURN count(c)").result_set[0][0] == 30
@pytest.mark.parametrize("tool", list(TOOLS))
def test_tools_run(g, tool): assert safe_ro(g, TOOLS[tool][1]).result_set
def test_write_blocked(g):
    with pytest.raises(ValueError): safe_ro(g, "MATCH (n) DETACH DELETE n")
def test_ask_routing(g):
    r = ask(g, "Which clients bring the most revenue?", llm=NoLLM())
    assert r["tool"] == "top_clients" and r["rows"][0]["net_revenue"] > 0
def test_decision_traceable(g):
    r = ask(g, "why did we decide this", llm=NoLLM())
    assert all(x["source_message"].startswith("ms:") for x in r["rows"])
def test_subgraph(g): assert subgraph(g)["edges"]
