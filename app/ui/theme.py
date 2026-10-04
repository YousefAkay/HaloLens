"""Newsprint theme: design tokens and the CSS injected at the top of every page.

Owner: FCT (redesign I-11c, from the design hand-off). Paper ground, near-black serif, cyan for what can be touched, magenta
only for "changed" markers and the AI section. No boxes and no divider rules: hierarchy comes from type scale and whitespace.
The tokens below are the single source: .streamlit/config.toml repeats the five theme colours and a test keeps them equal.
"""

from __future__ import annotations

import streamlit as st

from leaselens.contracts import COLOR_CONTRACT, COLOR_NET

NET = COLOR_NET  # anything that means "net of incentives": the same colour as the notebook charts (AGENTS.md section 11)
CONTRACT = COLOR_CONTRACT  # anything that means "contractual rent": likewise
PAPER = "#f3f2f2"  # page ground
SURFACE = "#eae9e9"  # inputs and quiet fills
INK = "#201e1d"  # text
ACCENT = "#0088b0"  # interactive, bars, markers
ACCENT_TEXT = "#006786"  # accent when used for text or solid fills
SECOND = "#d6006c"  # rare second spot: "changed" markers and the AI section
SECOND_TEXT = "#aa0b56"  # magenta used for text
SECOND_TINT = "#f6d2e3"  # light magenta for the synthetic-data notice
NEUTRALS = ("#d7d3d3", "#bab6b6", "#9b9797", "#605d5d")  # 200..600 ramp, light to dark
NEUTRAL_200, NEUTRAL_300, NEUTRAL_500, NEUTRAL_600 = NEUTRALS
FONT_FAMILY = "'Source Serif 4', Georgia, 'Times New Roman', serif"
# The @import below makes the visitor's BROWSER fetch one typeface (Source Serif 4) from Google Fonts.
# It sends none of the app's data and it is the only external address in the app (a test enforces that).
# Offline, the stack falls back to Georgia, then to any serif, so the page stays readable.
# The sidebar trust notes say so in plain words.
FONT_IMPORT = "https://fonts.googleapis.com/css2?family=Source+Serif+4:ital,wght@0,400;0,600;1,400&display=swap"
CONTENT_MAX_WIDTH_PX = 1120
PAGE_PADDING_PX = 40
PAGE_BOTTOM_PX = 120
SECTION_TOP_PX = 24  # space above a section's heading inside its tab
HERO_MIN_PX, HERO_VW, HERO_MAX_PX = 120, 19, 220  # hero number: clamp(min, vw, max)
H2_PX = 44
KICKER_PX = 16
BODY_PX = 18
ANSWER_PX = 21
CONTROL_RADIUS_PX = 2
FOCUS_OUTLINE_PX = 2
MOTION_SECONDS = 0.35  # marker transition in the Scenario Lab

CSS = f"""
@import url('{FONT_IMPORT}');
:root {{ --paper:{PAPER}; --surface:{SURFACE}; --ink:{INK}; --accent:{ACCENT}; --accent-text:{ACCENT_TEXT};
        --second:{SECOND}; --second-text:{SECOND_TEXT}; --n200:{NEUTRAL_200}; --n300:{NEUTRAL_300}; --n500:{NEUTRAL_500};
        --n600:{NEUTRAL_600}; --net:{NET}; --contract:{CONTRACT}; }}
html, body, .stApp, .stApp *:not([data-testid="stIconMaterial"]) {{ font-family:{FONT_FAMILY}; }}
[data-testid="stIconMaterial"] {{ font-family:'Material Symbols Rounded' !important; }}
body, .stApp {{ background:var(--paper); color:var(--ink); font-size:{BODY_PX}px; line-height:1.5; }}
#MainMenu, footer, [data-testid="stToolbar"], [data-testid="stDecoration"] {{ display:none !important; visibility:hidden; }}
header, [data-testid="stHeader"] {{ background:transparent !important; }}
.block-container {{ max-width:{CONTENT_MAX_WIDTH_PX}px; padding:0 {PAGE_PADDING_PX}px {PAGE_BOTTOM_PX}px; }}
a, .stApp a, [data-testid="stMarkdownContainer"] a {{ color:var(--accent-text) !important; }}
:focus-visible {{ outline:{FOCUS_OUTLINE_PX}px solid var(--accent); outline-offset:{FOCUS_OUTLINE_PX}px; }}

/* masthead: title and badge above the tabs */
.ll-title {{ font-size:28px; font-weight:600; line-height:1.1; margin:6px 0 0; }}
.ll-sub {{ font-size:15px; color:var(--n600); margin:2px 0 8px; }}
.ll-badge {{ font-size:12px; font-weight:600; color:var(--accent-text); margin-left:10px; letter-spacing:.04em; text-transform:uppercase; }}
.ll-notice {{ background:{SECOND_TINT}; color:var(--second-text); font-size:14px; padding:6px 10px; margin:0 0 4px; }}

/* tabs and sidebar */
[data-baseweb="tab-list"] {{ gap:4px; flex-wrap:wrap; }}
button[data-baseweb="tab"] {{ background:transparent; font-size:17px; color:var(--ink); padding:8px 14px; }}
button[data-baseweb="tab"][aria-selected="true"] {{ color:var(--accent-text); font-weight:600; }}
[data-baseweb="tab-highlight"] {{ background:var(--accent) !important; }}
[data-baseweb="tab-border"] {{ background:var(--n300) !important; }}
[data-testid="stSidebar"] {{ background:var(--surface); }}
[data-testid="stSidebar"] * {{ font-size:15px; }}

/* sections: kicker, sentence headline, generous space */
.ll-section {{ padding-top:{SECTION_TOP_PX}px; }}
.ll-kicker {{ color:var(--accent-text); font-size:{KICKER_PX}px; font-weight:600; margin-bottom:10px; }}
.ll-kicker.ai {{ color:var(--second-text); }}
.ll-h2 {{ font-size:{H2_PX}px; line-height:1.1; font-weight:600; margin:0 0 28px; letter-spacing:-.01em; text-wrap:balance; }}
.ll-caption {{ font-size:15px; color:var(--n600); }}
.ll-small {{ font-size:15px; color:var(--n600); margin-top:6px; }}

/* hero */
.ll-hero-row {{ display:flex; align-items:flex-end; gap:40px; flex-wrap:wrap; margin:10px 0 18px; }}
.ll-hero-number {{ font-size:clamp({HERO_MIN_PX}px, {HERO_VW}vw, {HERO_MAX_PX}px); font-weight:600; letter-spacing:-.04em; line-height:.9; color:var(--net); }}
.ll-hero-pct {{ font-size:.4em; letter-spacing:0; margin-left:.06em; }}
.ll-hero-text {{ max-width:430px; padding-bottom:14px; }}
.ll-hero-label {{ font-size:28px; font-weight:600; line-height:1.15; }}
.ll-hero-text p {{ margin:8px 0 0; color:var(--n600); font-size:17px; }}

/* percent-positioned bars */
.ll-scale {{ position:relative; height:46px; margin:24px 0 6px; }}
.ll-track {{ position:absolute; left:0; right:0; top:21px; height:2px; background:var(--n300); }}
.ll-band {{ position:absolute; top:12px; height:20px; background:var(--n200); }}
.ll-band.lab {{ background:#cfe6ee; }}
.ll-marker {{ position:absolute; top:6px; width:3px; height:32px; margin-left:-1.5px; transition:left {MOTION_SECONDS}s; }}
.ll-marker.net {{ background:var(--net); }}
.ll-marker.contract {{ background:var(--contract); width:3px; height:26px; top:9px; margin-left:-1.5px; }}
.ll-dot {{ position:absolute; top:12px; width:20px; height:20px; margin-left:-10px; border-radius:50%; transition:left {MOTION_SECONDS}s; box-sizing:border-box; }}
.ll-dot.base {{ border:2px solid var(--ink); background:var(--paper); }}
.ll-dot.scenario {{ background:var(--net); border:2px solid var(--net); }}
.ll-axis {{ position:relative; height:20px; font-size:13px; color:var(--n600); }}
.ll-axis span {{ position:absolute; transform:translateX(-50%); white-space:nowrap; }}
.ll-legend {{ font-size:14px; color:var(--n600); display:flex; gap:20px; flex-wrap:wrap; }}
.ll-legend i {{ display:inline-block; width:12px; height:12px; margin-right:6px; vertical-align:-1px; }}
.ll-legend i.net {{ background:var(--net); }}
.ll-legend i.contract {{ background:var(--contract); }}
.ll-legend i.band {{ background:var(--n200); }}

/* supporting stats, no cards */
.ll-stats {{ display:grid; grid-template-columns:repeat(4, 1fr); gap:34px; margin-top:44px; }}
.ll-stat-title {{ font-size:15px; font-weight:600; color:var(--accent-text); margin-bottom:6px; }}
.ll-stat-body {{ font-size:17px; line-height:1.4; }}
@media (max-width: 900px) {{ .ll-stats {{ grid-template-columns:repeat(2, 1fr); }} }}

/* why */
.ll-steps {{ display:grid; grid-template-columns:repeat(3, 1fr); gap:34px; margin-bottom:56px; }}
.ll-step-k {{ font-size:15px; font-weight:600; color:var(--accent-text); }}
.ll-step-k.ai {{ color:var(--second-text); }}
.ll-step-t {{ font-size:26px; font-weight:600; line-height:1.15; margin:4px 0 6px; }}

/* validation charts */
.ll-rows {{ display:grid; gap:12px; }}
.ll-row {{ display:grid; grid-template-columns:150px 1fr 70px; align-items:center; gap:14px; font-size:16px; }}
.ll-row .lbl {{ overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
.ll-row .val {{ text-align:right; font-variant-numeric:tabular-nums; }}
.ll-trk {{ position:relative; height:22px; }}
.ll-fill {{ position:absolute; left:0; top:4px; height:14px; background:var(--net); opacity:.4; }}
.ll-fill.lead {{ background:var(--net); opacity:1; }}
.ll-fill.actual {{ background:var(--net); opacity:1; }}
.ll-fill.forecast {{ background:var(--net); opacity:.4; }}
.ll-fill.thin {{ height:9px; }}
.ll-tick {{ position:absolute; top:1px; width:2px; height:20px; margin-left:-1px; background:var(--ink); }}
.ll-hollow {{ position:absolute; top:5px; width:12px; height:12px; margin-left:-6px; border:2px solid var(--ink); border-radius:50%; box-sizing:border-box; background:var(--paper); }}
.ll-year {{ font-weight:600; }}
.ll-pair {{ display:grid; gap:3px; }}

/* lab */
.ll-changed {{ color:var(--second-text); font-size:14px; font-style:italic; margin-left:8px; }}
.ll-lab-label {{ font-size:15px; font-weight:600; margin:14px 0 4px; }}
.ll-big-row {{ display:flex; align-items:flex-end; gap:34px; flex-wrap:wrap; }}
.ll-base-num {{ font-size:44px; font-weight:600; color:var(--net); opacity:.45; line-height:1; }}
.ll-scn-num {{ font-size:84px; font-weight:600; letter-spacing:-.03em; line-height:.95; color:var(--net); }}
.ll-delta {{ font-size:22px; font-weight:600; color:var(--second-text); padding-bottom:10px; }}
.ll-num-cap {{ font-size:14px; color:var(--n600); }}

/* tornado */
.ll-torn {{ display:grid; gap:9px; margin-top:12px; }}
.ll-torn-row {{ display:grid; grid-template-columns:300px 1fr 70px; gap:14px; align-items:center; font-size:15px; }}
.ll-torn-trk {{ position:relative; height:18px; }}
.ll-torn-mid {{ position:absolute; left:50%; top:0; width:1px; height:18px; background:var(--ink); }}
.ll-torn-bar {{ position:absolute; top:3px; height:12px; }}
.ll-torn-bar.neg {{ background:var(--n600); }}
.ll-torn-bar.pos {{ background:var(--accent-text); }}

/* buildings */
.ll-bd-row {{ display:grid; grid-template-columns:260px 1fr 190px; gap:14px; align-items:center; font-size:16px; min-height:34px; }}
.ll-bd-trk {{ position:relative; height:30px; }}
.ll-bd-dot {{ position:absolute; top:50%; border-radius:50%; background:var(--net); transform:translate(-50%, -50%); opacity:.9; }}
.ll-bd-tick {{ position:absolute; top:4px; width:2px; height:22px; background:var(--ink); margin-left:-1px; }}
.ll-bd-axis {{ position:relative; height:20px; margin-left:274px; margin-right:204px; font-size:13px; color:var(--n600); }}
.ll-bd-axis span {{ position:absolute; transform:translateX(-50%); white-space:nowrap; }}

/* ask */
.ll-q {{ font-style:italic; font-size:20px; margin:30px 0 8px; }}
.ll-a {{ font-size:{ANSWER_PX}px; font-weight:600; line-height:1.3; margin:0 0 10px; }}
.ll-a-list {{ margin:0 0 10px 1.1em; padding:0; }}
.ll-a-foot {{ font-size:14px; color:var(--n600); }}
.ll-a-foot .ok {{ color:var(--accent-text); margin-left:14px; }}
.ll-chip {{ display:inline-block; padding:2px 10px; margin:0 6px 6px 0; background:var(--surface); font-size:14px; }}
.ll-plain {{ font-size:17px; color:var(--n600); max-width:640px; }}

/* Streamlit widgets: quiet */
.stButton > button {{ border:none; background:var(--surface); color:var(--ink); border-radius:{CONTROL_RADIUS_PX}px; font-size:16px; padding:6px 14px; }}
.stButton > button:hover {{ background:var(--surface); color:var(--accent-text); text-decoration:underline; }}
.st-key-pills .stButton > button {{ border-radius:999px; padding:5px 16px; height:auto; white-space:normal; text-align:left; }}
.st-key-pills .stButton > button p {{ white-space:normal; text-align:left; }}
.st-key-copilot_go .stButton > button, .st-key-reset_lab .stButton > button {{ background:transparent; padding:0; color:var(--accent-text); text-decoration:underline; }}
.stTextInput input {{ background:var(--surface); border:none; border-radius:{CONTROL_RADIUS_PX}px; font-size:17px; }}
[data-testid="stSegmentedControl"] button, [data-testid="stButtonGroup"] button, button[data-testid="stBaseButton-segmented_control"] {{
  background:var(--surface); border:none; border-radius:{CONTROL_RADIUS_PX}px; color:var(--ink); }}
[data-testid="stSegmentedControl"] button[aria-checked="true"], [data-testid="stSegmentedControl"] button[aria-pressed="true"],
[data-testid="stButtonGroup"] button[aria-checked="true"], [data-testid="stButtonGroup"] button[aria-pressed="true"],
button[data-testid="stBaseButton-segmented_controlActive"], button[kind="segmented_controlActive"] {{
  background:var(--accent-text) !important; color:#fff !important; }}
button[data-testid="stBaseButton-segmented_controlActive"] *, button[kind="segmented_controlActive"] * {{ color:#fff !important; }}
[data-testid="stExpander"], [data-testid="stExpander"] details, [data-testid="stExpander"] summary {{
  border:none !important; background:transparent !important; box-shadow:none !important; }}
[data-testid="stExpander"] summary {{ font-size:16px; color:var(--accent-text); }}
[data-testid="stDataFrame"] {{ font-size:15px; }}
"""


def inject_css() -> None:
    """Write the theme into the page. Called first in main()."""
    st.markdown(f"<style>{CSS}</style>", unsafe_allow_html=True)
