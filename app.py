from flask import Flask, render_template, request, jsonify
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from io import BytesIO
import base64
import re
import os

app = Flask(__name__)

CSV = "dataset.csv"
if not os.path.exists(CSV):
    raise FileNotFoundError(f"{CSV} not found in project root.")

# ------- Configuration -------
MIN_MATCHES = 5
LOOKBACK = 20
CAP_MIN = 5.0
CAP_MAX = 95.0
# -----------------------------

# canonical mapping code <-> full name (edit if your CSV uses slightly different names)
CODE_TO_NAME = {
    "IND": "India",
    "AUS": "Australia",
    "ENG": "England",
    "WI": "West Indies",
    "NZ": "New Zealand",
    "SA": "South Africa",
    "PAK": "Pakistan",
    "BAN": "Bangladesh",
    "NED": "Netherlands"
}
NAME_TO_CODE = {v.lower(): k for k, v in CODE_TO_NAME.items()}

# Read CSV and normalize column names + text values
df = pd.read_csv(CSV)
df.columns = [c.strip() for c in df.columns]  # remove stray spaces in header names

# Normalize string columns (strip spaces)
for col in df.select_dtypes(include="object").columns:
    df[col] = df[col].astype(str).str.strip()

# Ensure Team column upper-case shortcodes (user said Team column uses shortcodes)
df['Team'] = df['Team'].str.upper().str.strip()

# Normalize Format (common variants)
df['Format'] = df['Format'].str.replace(r'\s+', '', regex=True).str.upper().str.strip()
df['Format'] = df['Format'].replace({"T20": "T20I", "TWENTY20": "T20I"})  # common fixes

# Normalize Opponent to remove parenthetical parts and extra spaces
def normalize_name(s):
    if not isinstance(s, str):
        return ''
    s = re.sub(r'\(.*?\)', '', s)          # remove parentheses content
    s = re.sub(r'\s+', ' ', s)             # collapse whitespace
    return s.strip().lower()

df['Opponent_norm'] = df['Opponent'].apply(normalize_name)

# Create OpponentCode - map normalized opponent full name -> code if possible, else fallback to uppercase of original
df['OpponentCode'] = df['Opponent_norm'].map(NAME_TO_CODE)
# If mapping failed, try if Opponent itself is already a code (e.g., "IND")
df.loc[df['OpponentCode'].isna(), 'OpponentCode'] = df.loc[df['OpponentCode'].isna(), 'Opponent'].str.upper().str.strip()

# Parse dates with a couple of common formats then fallback
def parse_date_series(s):
    # try several formats
    for fmt in ("%d-%b-%y", "%d-%b-%Y", "%d %b %Y", "%Y-%m-%d"):
        try:
            return pd.to_datetime(s, format=fmt, errors='coerce')
        except Exception:
            continue
    # fallback: let pandas infer
    return pd.to_datetime(s, errors='coerce')

df['Start Date'] = parse_date_series(df['Start Date'])

# Drop rows without a parseable date (optional)
df = df[df['Start Date'].notna()].copy()

# Available formats from the dataset (upper-case)
ALLOWED_FORMATS = sorted(df['Format'].dropna().unique().tolist())

# parse and normalize Result text
df['Result_norm'] = df['Result'].astype(str).str.strip().str.lower()

# margin parse helpers
def parse_margin(m):
    # return (runs, wkts)
    if not isinstance(m, str) or m.strip() == "":
        return (None, None)
    s = m.lower()
    # runs
    mnum = ''.join(ch for ch in s if (ch.isdigit() or ch == '-'))
    if "run" in s and mnum:
        try:
            return (abs(int(mnum)), None)
        except:
            pass
    # wickets
    if "wkt" in s or "wicket" in s or "wkts" in s:
        if mnum:
            try:
                return (None, abs(int(mnum)))
            except:
                pass
    return (None, None)

marg_parsed = df['Margin'].apply(parse_margin)
df['Margin_Runs'] = marg_parsed.apply(lambda t: t[0])
df['Margin_Wkts'] = marg_parsed.apply(lambda t: t[1])

# -------------------------
# Helper functions
# -------------------------
def team_stats(team_code, opponent_code=None, match_format=None, lookback=LOOKBACK):
    q = df[df['Team'] == team_code]
    if match_format:
        q = q[q['Format'] == match_format.upper()]
    if opponent_code:
        q = q[q['OpponentCode'] == opponent_code]
    q = q.sort_values('Start Date', ascending=False).head(lookback)

    total = len(q)
    wins = int((q['Result_norm'] == 'won').sum())
    losses = int((q['Result_norm'] == 'lost').sum())
    win_ratio = (wins / total) if total > 0 else 0.0

    runs = q['Margin_Runs'].dropna()
    wkts = q['Margin_Wkts'].dropna()
    avg_runs = float(runs.mean()) if not runs.empty else None
    avg_wkts = float(wkts.mean()) if not wkts.empty else None

    return {
        "total": total,
        "wins": wins,
        "losses": losses,
        "win_ratio": win_ratio,
        "avg_margin_runs": avg_runs,
        "avg_margin_wkts": avg_wkts
    }

def compute_score_from_stats(stats):
    wr = stats['win_ratio']  # 0..1
    avg_runs = stats['avg_margin_runs'] or 0.0
    avg_wkts = stats['avg_margin_wkts'] or 0.0
    run_component = avg_runs / 200.0   # heuristic
    wkts_component = avg_wkts / 10.0
    score = (0.7 * wr) + (0.2 * run_component) + (0.1 * wkts_component)
    return float(score)

def cap_and_renormalize(p1, p2, cap_min=CAP_MIN, cap_max=CAP_MAX, apply=False):
    if not apply:
        return round(p1,2), round(p2,2)
    def cap(x):
        return cap_min + (x/100.0)*(cap_max - cap_min)
    c1 = cap(p1)
    c2 = cap(p2)
    total = c1 + c2
    if total == 0:
        return round(50.0,2), round(50.0,2)
    return round((c1/total)*100.0, 2), round((c2/total)*100.0, 2)

def make_chart_b64(team1, team2, p1, p2):
    fig, ax = plt.subplots(figsize=(6,3))
    bars = ax.bar([team1, team2], [p1, p2], color=['#0d6efd','#198754'])
    ax.set_ylim(0,100)
    ax.set_ylabel("Win Probability (%)")
    ax.set_title(f"{team1} vs {team2}")
    for bar in bars:
        h = bar.get_height()
        ax.text(bar.get_x()+bar.get_width()/2, h+1.5, f"{h:.1f}%", ha='center', va='bottom', fontsize=9)
    plt.tight_layout()
    buf = BytesIO()
    plt.savefig(buf, format='png')
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.getvalue()).decode('ascii')

# -------------------------
# Routes
# -------------------------
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/teams')
def teams():
    return jsonify(sorted(df['Team'].dropna().unique().tolist()))

@app.route('/formats')
def formats():
    # return canonical formats present in dataset (upper-case)
    return jsonify(ALLOWED_FORMATS)

@app.route('/predict', methods=['POST'])
def predict():
    payload = request.get_json(force=True)
    team1 = str(payload.get('team1','')).upper().strip()
    team2 = str(payload.get('team2','')).upper().strip()
    match_format = str(payload.get('format','')).upper().strip()

    if not team1 or not team2 or not match_format:
        return jsonify({"error":"Provide team1, team2 and format"}), 400
    if match_format not in ALLOWED_FORMATS:
        return jsonify({"error":f"Format must be one of {ALLOWED_FORMATS}"}), 400
    if team1 == team2:
        return jsonify({"error":"Pick two different teams"}), 400

    # map opponent codes (we expect Team column to contain shortcodes like IND)
    opp1_code = team2
    opp2_code = team1

    # head-to-head first
    t1_h2h = team_stats(team1, opponent_code=opp1_code, match_format=match_format, lookback=LOOKBACK)
    t2_h2h = team_stats(team2, opponent_code=opp2_code, match_format=match_format, lookback=LOOKBACK)

    # fallback to recent form if h2h insufficient
    t1_stats = t1_h2h
    t2_stats = t2_h2h
    t1_fallback = False
    t2_fallback = False

    if t1_stats['total'] < MIN_MATCHES:
        t1_stats = team_stats(team1, opponent_code=None, match_format=match_format, lookback=LOOKBACK*2)
        t1_fallback = True
    if t2_stats['total'] < MIN_MATCHES:
        t2_stats = team_stats(team2, opponent_code=None, match_format=match_format, lookback=LOOKBACK*2)
        t2_fallback = True

    # debug prints (server console)
    print(f"[DEBUG] {team1} used {t1_stats['total']} matches (h2h {t1_h2h['total']}), "
          f"{team2} used {t2_stats['total']} matches (h2h {t2_h2h['total']}). Format: {match_format}")

    insufficient = (t1_stats['total'] < 1) or (t2_stats['total'] < 1)

    # scores and probabilities
    s1 = compute_score_from_stats(t1_stats)
    s2 = compute_score_from_stats(t2_stats)
    if (s1 + s2) == 0:
        p1 = p2 = 50.0
    else:
        p1 = (s1/(s1+s2))*100.0
        p2 = (s2/(s1+s2))*100.0

    # if either side has less than MIN_MATCHES, cap to safe range
    apply_cap = (t1_stats['total'] < MIN_MATCHES) or (t2_stats['total'] < MIN_MATCHES)
    p1, p2 = cap_and_renormalize(p1, p2, apply=apply_cap)

    # final rounding
    p1 = round(p1, 2); p2 = round(p2, 2)

    chart_b64 = make_chart_b64(team1, team2, p1, p2) if not insufficient else ""

    resp = {
        "team1": team1,
        "team2": team2,
        "format": match_format,
        "t1_prob": p1,
        "t2_prob": p2,
        "chart": chart_b64,
        "stats": {
            "team1": t1_stats,
            "team1_head_to_head_used": t1_h2h['total'] >= MIN_MATCHES,
            "team1_fallback_used": t1_fallback,
            "team2": t2_stats,
            "team2_head_to_head_used": t2_h2h['total'] >= MIN_MATCHES,
            "team2_fallback_used": t2_fallback
        },
        "insufficient_data": insufficient
    }
    return jsonify(resp)

if __name__ == "__main__":
    app.run(debug=True)
