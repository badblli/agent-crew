"""README illustrations of the crew board and quota pane, with demo data (en + tr).

Usage: python docs/assets/make_previews.py docs/assets
"""
import sys
from pathlib import Path

OUT = Path(sys.argv[1])
SRC_QUOTA = Path(sys.argv[2]) if len(sys.argv) > 2 else OUT / "quota-preview-tr.svg"  # Turkish source
F = "system-ui,-apple-system,'Segoe UI',sans-serif"
STRIPES = ["#f97316", "#a78bfa", "#22d3ee", "#f472b6", "#4ade80", "#38bdf8"]
ACCENT = "#d97757"

L = {
    "en": dict(sub="Phase 2 · search + CSV export", steps=["assigned", "working", "report", "review", "approve", "PR", "merged"],
               rows=[("Builder", "#f97316", "ac12 search API", "review", "codex · standard", "now: pytest -q tests/search"),
                     ("Designer", "#f472b6", "ac13 results page", "working", "claude · standard", "edit: src/ui/Results.tsx"),
                     ("Tester", "#4ade80", "ac14 export tests", "assigned", "codex · light", "waiting for ac12")]),
    "tr": dict(sub="Faz 2 · arama + CSV dışa aktarma", steps=["atandı", "çalışıyor", "rapor", "inceleme", "onay", "PR", "birleşti"],
               rows=[("Builder", "#f97316", "ac12 arama API", "inceleme", "codex · standard", "şimdi: pytest -q tests/search"),
                     ("Designer", "#f472b6", "ac13 sonuç sayfası", "çalışıyor", "claude · standard", "düzenliyor: src/ui/Results.tsx"),
                     ("Tester", "#4ade80", "ac14 dışa aktarma testleri", "atandı", "codex · light", "ac12 bekleniyor")]),
}


def step_track(labels, at, y):
    gap, out = 56, []
    for i, lab in enumerate(labels):
        x = 14 + i * gap + gap / 2
        state = "done" if i < at else "now" if i == at else "next"
        if i:
            out.append(f'<line x1="{x - gap + 8}" y1="{y}" x2="{x - 8}" y2="{y}" stroke="{ACCENT if i <= at else "#8885"}" stroke-width="2"/>')
        if state == "now":
            out.append(f'<circle cx="{x}" cy="{y}" r="11" fill="{ACCENT}" opacity="0.25"><animate attributeName="r" values="9;12;9" dur="1.6s" repeatCount="indefinite"/></circle>')
        fill = ACCENT if state != "next" else "none"
        out.append(f'<circle cx="{x}" cy="{y}" r="7" fill="{fill}" stroke="{ACCENT if state != "next" else "#888"}" stroke-width="1.5"/>')
        if state == "done":
            out.append(f'<path d="M{x-3.2} {y} l2.2 2.4 l4.2 -4.6" fill="none" stroke="#fff" stroke-width="1.8" stroke-linecap="round"/>')
        out.append(f'<text x="{x}" y="{y + 22}" text-anchor="middle" font-size="9" fill="{ACCENT if state == "now" else "#999"}" '
                   f'font-weight="{700 if state == "now" else 400}">{lab}</text>')
    return "".join(out)


def board(lang):
    c = L[lang]
    w = 420
    stripe = (w - 20) / len(STRIPES)
    parts = [
        f'<defs><linearGradient id="g" x1="0" x2="1"><stop offset="0" stop-color="{ACCENT}" stop-opacity="0.35"/>'
        f'<stop offset="1" stop-color="{ACCENT}" stop-opacity="0.05"/></linearGradient></defs>',
        f'<rect x="10" y="4" width="{w - 20}" height="56" rx="10" fill="url(#g)" stroke="{ACCENT}66"/>',
        *[f'<rect x="{10 + i * stripe}" y="62" width="{stripe - 2}" height="5" rx="2" fill="{col}"/>' for i, col in enumerate(STRIPES)],
        f'<text x="24" y="30" font-size="17" font-weight="800" fill="{ACCENT}">◆ DEMO-SHOP · Classic</text>',
        f'<text x="24" y="49" font-size="11" fill="#999">{c["sub"]}</text>',
        step_track(c["steps"], 3, 92),
    ]
    y = 140
    for name, col, wp, step, model, now in c["rows"]:
        parts.append(f'<rect x="10" y="{y - 14}" width="{w - 20}" height="34" rx="7" fill="{col}12" stroke="{col}44"/>'
                     f'<circle cx="24" cy="{y - 2}" r="4.5" fill="{col}"/>'
                     f'<text x="34" y="{y + 2}" font-size="11.5" font-weight="700" fill="{col}">{name}</text>'
                     f'<text x="98" y="{y + 2}" font-size="11" fill="#999">{wp}</text>'
                     f'<text x="{w - 18}" y="{y + 2}" text-anchor="end" font-size="10" fill="#999">{step} · {model}</text>'
                     f'<text x="34" y="{y + 15}" font-size="9.5" fill="#888" font-family="ui-monospace,Consolas,monospace">{now}</text>')
        y += 40
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {y - 6}" font-family="{F}" role="img">'
            f'<title>Crew board (demo data)</title>{"".join(parts)}</svg>\n')


for lang in L:
    suf = "" if lang == "en" else "-tr"
    (OUT / f"board-preview{suf}.svg").write_text(board(lang), encoding="utf-8")

tr = SRC_QUOTA.read_text(encoding="utf-8")
(OUT / "quota-preview-tr.svg").write_text(tr if tr.endswith("\n") else tr + "\n", encoding="utf-8")
en = tr
for a, b in [("2 sa 5 dk sonra sıfırlanır", "resets in 2 h 5 min"), ("2 sa 9 dk sonra sıfırlanır", "resets in 2 h 9 min"),
             ("bağlam %17", "context 17%"), ("431k token", "431k tokens"), ("DOLU", "FULL"), ("kota hatası yok", "no quota errors"),
             ("yeşil &lt; %75 · sarı ≥ %75 · kırmızı ≥ %90", "green &lt; 75% · yellow ≥ 75% · red ≥ 90%")]:
    assert a in en, a
    en = en.replace(a, b)
(OUT / "quota-preview.svg").write_text(en if en.endswith("\n") else en + "\n", encoding="utf-8")
print("ok")
