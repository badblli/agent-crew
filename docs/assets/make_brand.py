"""Generate agent-crew brand SVGs: mascot (Reis), README banners, social preview.

Usage: python docs/assets/make_brand.py docs/assets
(social-preview.png is a 1280x640 browser screenshot of social-preview.svg.)
"""
import sys
from pathlib import Path

OUT = Path(sys.argv[1])
OUT.mkdir(parents=True, exist_ok=True)

INK = "#3b2320"       # outline
BODY = "#f2775b"      # coral
BODY_DK = "#d65a40"
SUCKER = "#fbc3b4"
NAVY = "#1f2a44"
GOLD = "#f5b83d"
FONT = "system-ui,-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"


def arm(d, w=17):
    return (f'<path d="{d}" fill="none" stroke="{INK}" stroke-width="{w + 6}" stroke-linecap="round"/>'
            f'<path d="{d}" fill="none" stroke="{BODY}" stroke-width="{w}" stroke-linecap="round"/>')


def suckers(points):
    return "".join(f'<circle cx="{x}" cy="{y}" r="2.6" fill="{SUCKER}"/>' for x, y in points)


def mascot_group():
    """Reis: a small octopus captain. 256x256 coordinate space."""
    arms = "".join([
        # lower, resting arms
        arm("M100 150 C 86 182, 58 196, 66 220 C 72 236, 92 228, 86 216"),
        arm("M116 156 C 112 190, 104 214, 116 232 C 124 242, 138 234, 130 224"),
        arm("M140 156 C 144 190, 152 214, 140 232 C 132 242, 118 234, 126 224"),
        arm("M156 150 C 170 182, 198 196, 190 220 C 184 236, 164 228, 170 216"),
        # working arms (hold tools)
        arm("M84 132 C 64 128, 44 116, 38 94"),     # wrench
        arm("M80 148 C 60 160, 42 162, 30 152"),    # magnifier
        arm("M172 132 C 192 128, 208 116, 214 98"),  # PR flag
        arm("M176 148 C 196 160, 214 162, 226 152"),  # test tube
    ])
    dots = suckers([(70, 212), (114, 222), (142, 222), (186, 212), (52, 120), (46, 158), (204, 120), (212, 158)])

    head = (
        f'<ellipse cx="128" cy="104" rx="62" ry="60" fill="{BODY}" stroke="{INK}" stroke-width="4"/>'
        f'<path d="M70 118 C 80 160, 176 160, 186 118 C 176 150, 80 150, 70 118 Z" fill="{BODY_DK}" opacity="0.55"/>'
        f'<ellipse cx="94" cy="96" rx="9" ry="14" fill="#fff" opacity="0.28" transform="rotate(-20 94 96)"/>'
    )
    face = (
        f'<ellipse cx="106" cy="114" rx="13" ry="15" fill="#fff" stroke="{INK}" stroke-width="3"/>'
        f'<ellipse cx="150" cy="114" rx="13" ry="15" fill="#fff" stroke="{INK}" stroke-width="3"/>'
        f'<circle cx="109" cy="117" r="7" fill="{NAVY}"/><circle cx="153" cy="117" r="7" fill="{NAVY}"/>'
        f'<circle cx="111.5" cy="113.5" r="2.4" fill="#fff"/><circle cx="155.5" cy="113.5" r="2.4" fill="#fff"/>'
        f'<ellipse cx="88" cy="136" rx="8" ry="5" fill="#ff9e8a" opacity="0.9"/>'
        f'<ellipse cx="168" cy="136" rx="8" ry="5" fill="#ff9e8a" opacity="0.9"/>'
        f'<path d="M118 138 Q128 148 138 138" fill="none" stroke="{INK}" stroke-width="3.5" stroke-linecap="round"/>'
    )
    hat = (
        # white crown
        f'<path d="M66 64 C 70 30, 186 30, 190 64 L182 80 C 150 70, 106 70, 74 80 Z" fill="#f7f8fb" stroke="{INK}" stroke-width="4" stroke-linejoin="round"/>'
        # navy band
        f'<path d="M74 80 C 106 70, 150 70, 182 80 L180 92 C 150 84, 106 84, 76 92 Z" fill="{NAVY}" stroke="{INK}" stroke-width="3.5" stroke-linejoin="round"/>'
        # visor
        f'<path d="M76 92 C 106 84, 150 84, 180 92 C 178 101, 166 102, 128 98 C 90 102, 78 101, 76 92 Z" fill="#141a2b" stroke="{INK}" stroke-width="3" stroke-linejoin="round"/>'
        # gold braid
        f'<path d="M84 92 C 110 86, 146 86, 172 92" fill="none" stroke="{GOLD}" stroke-width="2.5" stroke-linecap="round"/>'
        # badge: angle-bracket code emblem on a gold disc
        f'<circle cx="128" cy="68" r="11" fill="{GOLD}" stroke="{INK}" stroke-width="3"/>'
        f'<path d="M124 63 L119 68 L124 73 M132 63 L137 68 L132 73" fill="none" stroke="{NAVY}" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>'
    )
    # open-end wrench: a round head with a square jaw cut out of its top, on a straight handle
    wrench_shape = ('M-5 4 L-5 -8 A 13 13 0 0 1 -9 -17 A 13 13 0 0 1 -4 -31 L-4 -22 L4 -22 L4 -31 '
                    'A 13 13 0 0 1 9 -17 A 13 13 0 0 1 5 -8 L5 4 Z')
    wrench = (
        '<g transform="translate(40 94) rotate(-32)">'
        f'<path d="{wrench_shape}" fill="#aab4c3" stroke="{INK}" stroke-width="3" stroke-linejoin="round"/>'
        '<rect x="-2" y="-6" width="4" height="8" rx="2" fill="#8792a3"/>'
        '</g>'
    )
    magnifier = (
        f'<line x1="30" y1="152" x2="20" y2="140" stroke="{INK}" stroke-width="7" stroke-linecap="round"/>'
        f'<circle cx="14" cy="130" r="12" fill="#cfe8ff" fill-opacity="0.85" stroke="{INK}" stroke-width="4"/>'
        '<path d="M8 125 A 7 7 0 0 1 14 121" fill="none" stroke="#fff" stroke-width="2.5" stroke-linecap="round"/>'
    )
    flag = (
        f'<line x1="216" y1="104" x2="216" y2="36" stroke="{INK}" stroke-width="4.5" stroke-linecap="round"/>'
        f'<path d="M216 38 L250 38 L242 50 L250 62 L216 62 Z" fill="#8957e5" stroke="{INK}" stroke-width="3" stroke-linejoin="round"/>'
        # pull-request glyph
        '<g fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round">'
        '<circle cx="224" cy="44" r="2.4"/><circle cx="224" cy="56" r="2.4"/><circle cx="236" cy="56" r="2.4"/>'
        '<line x1="224" y1="46.5" x2="224" y2="53.5"/><path d="M236 53.5 V48 Q236 45 233 45 H229"/></g>'
    )
    tube = (
        '<g transform="translate(234 136) rotate(22)">'
        f'<rect x="-6" y="-26" width="12" height="34" rx="6" fill="#eef7f2" fill-opacity="0.9" stroke="{INK}" stroke-width="3"/>'
        '<path d="M-3.5 -6 H3.5 V2 A 3.5 3.5 0 0 1 -3.5 2 Z" fill="#3fbf7f"/>'
        f'<rect x="-8" y="-29" width="16" height="5" rx="2.5" fill="#aab4c3" stroke="{INK}" stroke-width="2.5"/>'
        '<circle cx="0" cy="-12" r="1.8" fill="#3fbf7f"/><circle cx="2" cy="-18" r="1.2" fill="#3fbf7f"/>'
        '</g>'
    )
    return f'<g>{arms}{dots}{head}{face}{hat}{wrench}{magnifier}{flag}{tube}</g>'


def svg(viewbox, body, title=None, extra=""):
    t = f"<title>{title}</title>" if title else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{viewbox}" role="img"{extra}>'
            f"{t}{body}</svg>\n")


MASCOT = mascot_group()
(OUT / "mascot.svg").write_text(
    svg("-4 20 264 228", MASCOT, "Reis, the agent-crew octopus captain"), encoding="utf-8")

THEMES = {
    "light": dict(bg1="#f4f8fc", bg2="#e3edf8", wave="#cfe0f2", wave2="#bcd3ec", title="#1f2a44",
                  text="#41506b", chip_bg="#ffffff", chip_bd="#c9d6e6", chip_tx="#1f2a44", accent="#d65a40"),
    "dark": dict(bg1="#0f1726", bg2="#16233a", wave="#1b2b46", wave2="#223658", title="#f4f6fb",
                 text="#b3c0d6", chip_bg="#1a2740", chip_bd="#2c3f62", chip_tx="#e6ecf6", accent="#ff8a6e"),
}

COPY = {
    "en": dict(tag1="Claude Code leads. Your coding agents ship.",
               tag2="Work packages · parallel worktrees · real review · PR · merge on green",
               chips=["Claude", "Codex", "Gemini"]),
    "tr": dict(tag1="Claude Code yönetir. Kodlama ajanların teslim eder.",
               tag2="İş paketleri · paralel worktree · gerçek inceleme · PR · yeşilde merge",
               chips=["Claude", "Codex", "Gemini"]),
}


def waves(t, w, h):
    return (f'<path d="M0 {h-46} C {w*.12} {h-70}, {w*.25} {h-22}, {w*.4} {h-44} S {w*.7} {h-66}, {w*.85} {h-40} S {w} {h-50}, {w} {h-50} V {h} H 0 Z" fill="{t["wave"]}"/>'
            f'<path d="M0 {h-24} C {w*.15} {h-40}, {w*.3} {h-8}, {w*.48} {h-26} S {w*.78} {h-40}, {w} {h-20} V {h} H 0 Z" fill="{t["wave2"]}"/>')


def chips(t, labels, x, y):
    out, cx = [], x
    dots = {"Claude": "#d97757", "Codex": "#10a37f", "Gemini": "#4285f4"}
    for lab in labels:
        wdt = 26 + len(lab) * 10.5
        out.append(f'<rect x="{cx}" y="{y}" width="{wdt}" height="32" rx="16" fill="{t["chip_bg"]}" stroke="{t["chip_bd"]}"/>'
                   f'<circle cx="{cx + 16}" cy="{y + 16}" r="5" fill="{dots[lab]}"/>'
                   f'<text x="{cx + 27}" y="{y + 21.5}" font-size="15" font-weight="600" fill="{t["chip_tx"]}">{lab}</text>')
        cx += wdt + 10
    return "".join(out)


def banner(theme, lang):
    t, c = THEMES[theme], COPY[lang]
    w, h = 1200, 340
    body = (
        f'<defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{t["bg1"]}"/>'
        f'<stop offset="1" stop-color="{t["bg2"]}"/></linearGradient>'
        f'<clipPath id="r"><rect width="{w}" height="{h}" rx="24"/></clipPath></defs>'
        f'<g clip-path="url(#r)"><rect width="{w}" height="{h}" fill="url(#bg)"/>{waves(t, w, h)}</g>'
        f'<g transform="translate(70 26) scale(1.16)">{MASCOT}</g>'
        f'<g font-family="{FONT}">'
        f'<text x="400" y="130" font-size="76" font-weight="800" fill="{t["title"]}" letter-spacing="-1.5">agent<tspan fill="{t["accent"]}">-</tspan>crew</text>'
        f'<text x="402" y="178" font-size="27" font-weight="600" fill="{t["title"]}">{c["tag1"]}</text>'
        f'<text x="402" y="214" font-size="18" fill="{t["text"]}">{c["tag2"]}</text>'
        f'{chips(t, c["chips"], 402, 238)}'
        '</g>'
    )
    return svg(f"0 0 {w} {h}", body, f"agent-crew — {c['tag1']}")


for theme in THEMES:
    for lang in COPY:
        suffix = "" if lang == "en" else "-tr"
        (OUT / f"banner{suffix}-{theme}.svg").write_text(banner(theme, lang), encoding="utf-8")


def social():
    t, c = THEMES["dark"], COPY["en"]
    w, h = 1280, 640
    body = (
        f'<defs><linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{t["bg1"]}"/>'
        f'<stop offset="1" stop-color="{t["bg2"]}"/></linearGradient></defs>'
        f'<rect width="{w}" height="{h}" fill="url(#bg)"/>{waves(t, w, h)}'
        f'<g transform="translate(70 120) scale(1.75)">{MASCOT}</g>'
        f'<g font-family="{FONT}">'
        f'<text x="560" y="250" font-size="96" font-weight="800" fill="{t["title"]}" letter-spacing="-2">agent<tspan fill="{t["accent"]}">-</tspan>crew</text>'
        f'<text x="563" y="312" font-size="34" font-weight="600" fill="{t["title"]}">Claude Code leads.</text>'
        f'<text x="563" y="356" font-size="34" font-weight="600" fill="{t["title"]}">Your coding agents ship.</text>'
        f'<text x="563" y="404" font-size="22" fill="{t["text"]}">A Claude Code plugin · live crew board · MIT</text>'
        f'{chips(t, c["chips"], 563, 430)}'
        '</g>'
    )
    return svg(f"0 0 {w} {h}", body, "agent-crew")


(OUT / "social-preview.svg").write_text(social(), encoding="utf-8")
print("ok", sorted(p.name for p in OUT.iterdir()))
