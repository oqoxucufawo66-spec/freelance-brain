import os
from flask import Flask, jsonify, render_template, request
from .graph import connect, load
from .agent import ask, subgraph, TOOLS

app = Flask(__name__)
G = connect()
if os.getenv("SEED", "1") == "1": load(G)

@app.get("/")
def index(): return render_template("index.html", tools=TOOLS)
@app.get("/api/graph")
def graph(): return jsonify(subgraph(G))
@app.post("/api/ask")
def api_ask():
    try: return jsonify(ask(G, request.json.get("q", "")))
    except Exception as ex: return jsonify({"error": str(ex)}), 400

if __name__ == "__main__": app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
