"""Deterministic SYNTHETIC data for a solo freelance studio. No real people or companies."""
import random
from datetime import date, timedelta

PLATFORMS = ["Kwork", "FL.ru", "Avito", "Upwork", "Referral"]
SERVICES = [("Telegram bot", 9000), ("WB ads automation", 25000), ("Landing page", 12000),
            ("AI consultant bot", 15000), ("3D interior render", 8000), ("Data parser", 6000)]
SKILLS = {"Telegram bot": ["Python", "aiogram"], "WB ads automation": ["Python", "WB API", "SQLite"],
          "Landing page": ["HTML", "Netlify"], "AI consultant bot": ["Python", "LLM"],
          "3D interior render": ["Blender", "SDXL"], "Data parser": ["Python", "Playwright"]}
INDUSTRIES = ["E-commerce", "Travel", "Real estate", "Education", "Restaurants", "Beauty"]
TOPICS = ["scope", "price", "deadline", "bug", "feature request", "payment", "feedback"]
DECISIONS = [
    ("WB ads automation", "Add buy-out % to unit economics for free", "Client argued unit economics are meaningless without it; support retainer justifies it."),
    ("WB ads automation", "Charge new features as paid options", "Protect fixed-price scope; anything outside the spec is an option."),
    ("3D interior render", "Re-render overhead view", "Client feedback: dark floor and missing door in view 2."),
    ("WB ads automation", "Remove test mode toggle", "Client confirmed dry-run behaved correctly."),
    ("Telegram bot", "Launch cheap entry kworks", "Low-price gigs pull clients toward flagship services."),
    ("Landing page", "Move landing to another static host", "Hosting limits; keep custom domain."),
]

def build(seed: int = 42):
    r = random.Random(seed)
    nodes, rels = [], []
    def n(label, **p): nodes.append((label, p)); return p["id"]
    def e(a, t, b, **p): rels.append((a, t, b, p))
    for p in PLATFORMS: n("Platform", id=f"pl:{p}", name=p, fee_pct={"Kwork": 20, "FL.ru": 10, "Avito": 0, "Upwork": 10, "Referral": 0}[p])
    for s, base in SERVICES:
        n("Service", id=f"sv:{s}", name=s, base_price=base)
        for sk in SKILLS[s]:
            if not any(x[1]["id"] == f"sk:{sk}" for x in nodes): n("Skill", id=f"sk:{sk}", name=sk)
            e(f"sv:{s}", "REQUIRES", f"sk:{sk}")
    for i in INDUSTRIES: n("Industry", id=f"in:{i}", name=i)
    clients = []
    for k in range(1, 31):
        cid = n("Client", id=f"cl:{k:03d}", name=f"Client-{k:03d}", since=str(date(2026, 1, 1) + timedelta(days=r.randint(0, 200))))
        e(cid, "IN_INDUSTRY", f"in:{r.choice(INDUSTRIES)}")
        clients.append(cid)
    for k in range(4, 31, 7): e(f"cl:{k:03d}", "REFERRED", f"cl:{k-3:03d}")
    oid = 0; mid = 0; orders = []
    weights = [5, 2, 2, 1, 1]
    for cid in clients:
        loyal = r.random() < 0.3
        for _ in range(r.randint(2, 5) if loyal else r.randint(1, 2)):
            oid += 1
            s, base = r.choice(SERVICES)
            plat = r.choices(PLATFORMS, weights)[0]
            price = int(base * r.uniform(0.7, 2.2) // 100 * 100)
            status = r.choices(["done", "in_progress", "cancelled"], [7, 2, 1])[0]
            d = date(2026, 1, 1) + timedelta(days=r.randint(0, 280))
            o = n("Order", id=f"or:{oid:04d}", title=f"{s} #{oid}", price=price, status=status, created=str(d))
            orders.append(o)
            e(cid, "PLACED", o); e(o, "FOR_SERVICE", f"sv:{s}"); e(o, "VIA", f"pl:{plat}")
            if status == "done":
                fee = {"Kwork": 20, "FL.ru": 10, "Upwork": 10}.get(plat, 0)
                n("Payment", id=f"pa:{oid:04d}", amount=price, net=int(price * (100 - fee) / 100), paid=str(d + timedelta(days=r.randint(3, 20))))
                e(o, "PAID_BY", f"pa:{oid:04d}")
            for _ in range(r.randint(1, 4)):
                mid += 1
                t = r.choice(TOPICS)
                n("Message", id=f"ms:{mid:05d}", topic=t, sentiment=r.choice(["positive", "neutral", "negative"]),
                  text=f"[{t}] synthetic message about {s.lower()}", at=str(d + timedelta(days=r.randint(0, 10))))
                e(f"ms:{mid:05d}", "ABOUT", o); e(cid, "SENT", f"ms:{mid:05d}")
    svc_of = {}
    for a, t, b, _ in rels:
        if t == "FOR_SERVICE": svc_of[a] = b
    for k, (svc, title, why) in enumerate(DECISIONS, 1):
        n("Decision", id=f"de:{k:02d}", title=title, rationale=why, at=str(date(2026, 10, 1) + timedelta(days=k)))
        target = r.choice([o for o in orders if svc_of[o] == f"sv:{svc}"])
        src = r.choice([a for a, t, b, _ in rels if t == "ABOUT" and b == target])
        e(f"de:{k:02d}", "BASED_ON", src)
        e(f"de:{k:02d}", "AFFECTS", target)
    return nodes, rels
