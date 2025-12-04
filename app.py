from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session
import pyrebase
import os

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret")

# ---- Firebase config (set these in Render Environment) ----
firebase_config = {
    "apiKey": os.environ.get("FIREBASE_API_KEY"),
    "authDomain": os.environ.get("FIREBASE_AUTH_DOMAIN"),
    "databaseURL": os.environ.get("FIREBASE_DB_URL"),
    "projectId": os.environ.get("FIREBASE_PROJECT_ID"),
    "storageBucket": os.environ.get("FIREBASE_STORAGE_BUCKET"),
    "messagingSenderId": os.environ.get("FIREBASE_SENDER_ID"),
    "appId": os.environ.get("FIREBASE_APP_ID"),
}
firebase = pyrebase.initialize_app(firebase_config)
db = firebase.database()

# ---- Ranks and medals (from your notebook) ----
enlisted_ranks = {
    "E1": "Private","E2": "Private First Class","E3": "Specialist","E4": "Corporal",
    "E5": "Sergeant","E6": "Staff Sergeant","E7": "Sergeant First Class",
    "E8": "Master Sergeant","E9": "Sergeant Major"
}
officer_ranks = {
    "O1": "Second Lieutenant","O2": "First Lieutenant","O3": "Captain","O4": "Major",
    "O5": "Lieutenant Colonel","O6": "Colonel","O7": "Brigadier General",
    "O8": "Major General","O9": "Lieutenant General","O10": "General"
}
all_rank_codes = set(enlisted_ranks.keys()) | set(officer_ranks.keys())

medals = {
    "1":"Iron Valor Cross","2":"Silver Shield","3":"Golden Eagle","4":"Sapphire Flame",
    "5":"Obsidian Spear","6":"Emerald Banner","7":"Phantom Strike Medal",
    "8":"Commander’s Flame","9":"Recruiter’s Honor Medal"
}

aldanese_history = """The History of the Aldanese Army

Origins at Lunch (11/18/25)
It began humbly, with a devoted group gathered around a lunch table.
The first to rise was Aldan Toba, founding O‑10, inspiring the Army’s creation.

The First Wave (11/19/25)
Jayden Li, Luca Lewis, and Marcus Stephan joined, formalizing the officer corps and strengthening the foundation.

The Rise of the Joint Chief of Staff
Declan Benito was appointed Joint Chief of Staff (O‑10), architecting organization and discipline alongside Aldan Toba.

Expansion of the Enlisted (11/20–11/21/25)
Henry Wang, Luke Lafrancois, and Quinn Tompkins entered as enlisted, proving the Army was open to all loyal followers.

December Recruits (12/1–12/2/25)
Rhodes Kentor and Ethan Long joined; Ethan’s quick promotion showed momentum and opportunity.

Legacy and Archives
From a lunch table to a structured force, led by O‑10s Aldan Toba and Declan Benito.
"""

# ---- Helpers (adapted from your notebook) ----
def today_str():
    return datetime.now().strftime("%m/%d/%y")

def get_rank_name(code):
    return enlisted_ranks.get(code, officer_ranks.get(code, code))

def valid_rank(code):
    return code in all_rank_codes

def rank_type_and_level(rank_code):
    if not rank_code or len(rank_code) < 2: return (None, None)
    t = rank_code[0].upper()
    try:
        lvl = int(rank_code[1:])
    except:
        return (None, None)
    if t in ("O","E"): return (t, lvl)
    return (None, None)

# ---- Cloud persistence via Firebase ----
def load_army():
    data = db.child("aldanese_army").get().val()
    if not data:
        # Build default roster (same as your notebook)
        def uname(n): return n.replace(" ", "_")
        units = [
            {"id":"u-001","username":uname("Aldan Toba"),"name":"Aldan Toba","rank":"O10","join_date":"11/18/25","last_change":"11/20/25","medals":[],"history":[]},
            {"id":"u-002","username":uname("Declan Benito"),"name":"Declan Benito","rank":"O10","join_date":"11/19/25","last_change":"11/28/25","medals":[],"history":[]},
            {"id":"u-003","username":uname("Jayden Li"),"name":"Jayden Li","rank":"O9","join_date":"11/19/25","last_change":"11/20/25","medals":[],"history":[]},
            {"id":"u-004","username":uname("Luca Lewis"),"name":"Luca Lewis","rank":"O8","join_date":"11/19/25","last_change":"11/20/25","medals":[],"history":[]},
            {"id":"u-005","username":uname("Marcus Stephan"),"name":"Marcus Stephan","rank":"O6","join_date":"11/19/25","last_change":"11/20/25","medals":[],"history":[]},
            {"id":"u-006","username":uname("Henry Wang"),"name":"Henry Wang","rank":"E6","join_date":"11/20/25","last_change":"11/24/25","medals":[],"history":[]},
            {"id":"u-007","username":uname("Luke Lafrancois"),"name":"Luke Lafrancois","rank":"E5","join_date":"11/20/25","last_change":"11/24/25","medals":[],"history":[]},
            {"id":"u-008","username":uname("Quinn Tompkins"),"name":"Quinn Tompkins","rank":"E5","join_date":"11/21/25","last_change":"11/24/25","medals":[],"history":[]},
            {"id":"u-009","username":uname("Rhodes Kentor"),"name":"Rhodes Kentor","rank":"E1","join_date":"12/01/25","last_change":"N/A","medals":[],"history":[]},
            {"id":"u-010","username":uname("Ethan Long"),"name":"Ethan Long","rank":"E2","join_date":"12/01/25","last_change":"12/02/25","medals":[],"history":[]},
        ]
        data = {"units": units, "last_change": today_str()}
        db.child("aldanese_army").set(data)
    return data

def save_army(army):
    army["last_change"] = today_str()
    db.child("aldanese_army").set(army)

def find_member_by_name(name, army):
    return next((m for m in army["units"] if m["name"].lower().strip() == name.lower().strip()), None)

def find_member_by_username(username, army):
    return next((m for m in army["units"] if m["username"].lower().strip() == username.lower().strip()), None)

# ---- Role resolution & permissions (unchanged rules) ----
def resolve_role_for_user(user):
    if user["name"] == "Declan Benito": return "JCOS"
    if user["name"] == "Aldan Toba": return "CIC"
    r = user["rank"]
    t, lvl = rank_type_and_level(r)
    if t == "O":
        if 6 <= lvl <= 9: return "HRO"
        elif 1 <= lvl <= 5: return "PCO"
        else: return "CIC"
    elif t == "E":
        if 1 <= lvl <= 7: return "LR"
        elif 8 <= lvl <= 9: return "SNCO"
    return "LR"

def actor_can_modify(actor_user, actor_role, target_member, action_type, new_rank_code=None):
    if actor_role == "LR": return False, "Lower Rank users cannot perform that action."
    if actor_role in ("JCOS","CIC"): return True, None
    if actor_role == "SNCO":
        if action_type in ("promote","demote"):
            ttype, tlevel = rank_type_and_level(target_member["rank"])
            if ttype != "E": return False, "SNCOs can only modify enlisted ranks."
            atype, alevel = rank_type_and_level(actor_user["rank"])
            if atype != "E": return False, "SNCO role requires an enlisted actor."
            if tlevel >= alevel: return False, f"SNCOs can only modify enlisted ranks below {actor_user['rank']}."
            if new_rank_code:
                ntype, nlevel = rank_type_and_level(new_rank_code)
                if ntype != "E": return False, "SNCOs can only set enlisted ranks."
                if nlevel >= alevel: return False, f"SNCOs cannot set a rank equal or above their own ({actor_user['rank']})."
            return True, None
        else:
            return False, "SNCOs cannot perform that action."
    if actor_role == "PCO":
        if action_type in ("promote","demote"):
            ttype, tlevel = rank_type_and_level(target_member["rank"])
            atype, alevel = rank_type_and_level(actor_user["rank"])
            if ttype == "O":
                if atype != "O": return False, "PCO must be an officer to modify officers."
                if tlevel >= alevel: return False, "PCO can only modify officers below their rank."
                if new_rank_code:
                    ntype, nlevel = rank_type_and_level(new_rank_code)
                    if ntype != "O": return False, "PCO must set an officer rank when modifying officers."
                    if nlevel >= alevel: return False, "PCO cannot set an officer rank equal or above their own."
                return True, None
            if ttype == "E": return True, None
            return False, "Invalid target rank type."
        else:
            return True, None
    if actor_role == "HRO":
        if action_type in ("promote","demote"):
            ttype, tlevel = rank_type_and_level(target_member["rank"])
            if ttype == "O":
                if tlevel >= 10: return False, "HRO cannot modify O10."
                return True, None
            if ttype == "E": return True, None
            return False, "Invalid target rank type."
        else:
            return True, None
    return False, "Permission denied."

# ---- Core actions (integrated to work with Firebase army dict) ----
def add_member(actor_user, actor_role, name, rank, army):
    if actor_role == "LR": return False, "Lower Rank users cannot add members."
    if not name.strip(): return False, "Name is required."
    if find_member_by_name(name, army): return False, "Already exists."
    rank = rank.upper()
    if not valid_rank(rank): return False, "Invalid rank. Use E1–E9 or O1–O10."
    new_id = f"u-{len(army['units'])+1:03d}"
    t = today_str()
    username = name.replace(" ", "_")
    army["units"].append({"id": new_id,"username": username,"name": name.strip(),"rank": rank,
                          "join_date": t,"last_change": t,"medals": [],"history": []})
    save_army(army)
    return True, f"{name} ({username}) added as {rank} ({get_rank_name(rank)})"

def promote_member(actor_user, actor_role, target_identifier, new_rank, army, actor_email):
    target = find_member_by_username(target_identifier, army) or find_member_by_name(target_identifier, army)
    if not target: return False, "Target not found."
    new_rank = new_rank.upper()
    if not valid_rank(new_rank): return False, "Invalid new rank."
    allowed, reason = actor_can_modify(actor_user, actor_role, target, "promote", new_rank)
    if not allowed: return False, reason
    old = target["rank"]
    target["rank"] = new_rank
    target["last_change"] = today_str()
    target.setdefault("history", []).append({
        "action":"promote","old_rank":old,"new_rank":new_rank,
        "timestamp":datetime.utcnow().isoformat(),"by": actor_email or "anonymous"
    })
    save_army(army)
    return True, f"{target['name']} promoted to {new_rank} ({get_rank_name(new_rank)})"

def demote_member(actor_user, actor_role, target_identifier, new_rank, army, actor_email):
    target = find_member_by_username(target_identifier, army) or find_member_by_name(target_identifier, army)
    if not target: return False, "Target not found."
    new_rank = new_rank.upper()
    if not valid_rank(new_rank): return False, "Invalid new rank."
    allowed, reason = actor_can_modify(actor_user, actor_role, target, "demote", new_rank)
    if not allowed: return False, reason
    old = target["rank"]
    target["rank"] = new_rank
    target["last_change"] = today_str()
    target.setdefault("history", []).append({
        "action":"demote","old_rank":old,"new_rank":new_rank,
        "timestamp":datetime.utcnow().isoformat(),"by": actor_email or "anonymous"
    })
    save_army(army)
    return True, f"{target['name']} demoted to {new_rank} ({get_rank_name(new_rank)})"

def award_medal(actor_user, actor_role, target_identifier, medal_name, army, actor_email):
    if actor_role == "LR": return False, "Lower Rank users cannot award medals."
    target = find_member_by_username(target_identifier, army) or find_member_by_name(target_identifier, army)
    if not target: return False, "Target not found."
    if medal_name.strip() == "": return False, "Medal name required."
    target.setdefault("medals", []).append(medal_name)
    target["last_change"] = today_str()
    target.setdefault("history", []).append({
        "action":"medal","old_rank":target["rank"],"new_rank":target["rank"],
        "timestamp":datetime.utcnow().isoformat(),"by": actor_email or "anonymous","medal": medal_name
    })
    save_army(army)
    return True, f"{target['name']} awarded: {medal_name}"

# ---- Stats snapshot ----
def compute_stats(army):
    officers = sum(1 for m in army["units"] if m["rank"].startswith("O"))
    enlisted = sum(1 for m in army["units"] if m["rank"].startswith("E"))
    total_medals = sum(len(m.get("medals", [])) for m in army["units"])
    return {"officers": officers, "enlisted": enlisted, "total": len(army["units"]), "total_medals": total_medals}

# ---- Login based on your notebook’s username/password set ----
def login_with_username(username, password, army):
    u = find_member_by_username(username, army)
    if not u: return None, None, "Username not found."
    p = (password or "").strip().lower()
    valid_pw = {"aldanishim","aldanesecic","aldanesejcos","armyhr","armylr","aldanesepmo"}
    if p not in valid_pw: return None, None, "Incorrect password."
    role = resolve_role_for_user(u)
    return u, role, None

# ---- Routes ----
@app.route("/")
def index():
    army = load_army()
    return render_template("index.html",
                           army=army,
                           ranks_enlisted=enlisted_ranks,
                           ranks_officers=officer_ranks,
                           ranks_all={**enlisted_ranks, **officer_ranks},
                           stats=compute_stats(army))

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        username = request.form["username"].strip()
        password = request.form["password"]
        army = load_army()
        user, role, err = login_with_username(username, password, army)
        if err: 
            flash(err, "error")
            return render_template("login.html")
        session["email"] = user["username"]
        session["role"] = role
        flash(f"Access granted! Role: {role}", "success")
        return redirect(url_for("index"))
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out.", "success")
    return redirect(url_for("index"))

@app.route("/soldier/<soldier_id>")
def soldier_page(soldier_id):
    army = load_army()
    soldier = next((s for s in army["units"] if s["id"] == soldier_id), None)
    if not soldier:
        flash("Soldier not found.", "error")
        return redirect(url_for("index"))
    return render_template("soldier.html",
                           soldier=soldier,
                           ranks_enlisted=enlisted_ranks,
                           ranks_officers=officer_ranks,
                           ranks_all={**enlisted_ranks, **officer_ranks},
                           medals=medals,
                           army_history=aldanese_history)

@app.route("/add", methods=["POST"])
def add():
    army = load_army()
    if not session.get("role") or session.get("role") == "LR":
        flash("Permission denied.", "error"); return redirect(url_for("index"))
    name = request.form["name"]
    rank = request.form["rank"]
    actor = find_member_by_username(session.get("email",""), army) or {"rank":"O10","name":"System"}  # fallback
    ok, msg = add_member(actor, session.get("role"), name, rank, army)
    flash(msg, "success" if ok else "error")
    return redirect(url_for("index"))

@app.route("/promote", methods=["POST"])
def promote():
    army = load_army()
    if not session.get("role") or session.get("role") == "LR":
        flash("Permission denied.", "error"); return redirect(url_for("index"))
    soldier_id = request.form["id"]
    new_rank = request.form["new_rank"]
    target = next((s for s in army["units"] if s["id"] == soldier_id), None)
    if not target:
        flash("Target not found.", "error"); return redirect(url_for("index"))
    actor = find_member_by_username(session.get("email",""), army) or {"rank":"O10","name":"System"}
    ok, msg = promote_member(actor, session.get("role"), target["username"], new_rank, army, session.get("email"))
    flash(msg, "success" if ok else "error")
    return redirect(url_for("soldier_page", soldier_id=soldier_id))

@app.route("/demote", methods=["POST"])
def demote():
    army = load_army()
    if not session.get("role") or session.get("role") == "LR":
        flash("Permission denied.", "error"); return redirect(url_for("index"))
    soldier_id = request.form["id"]
    new_rank = request.form["new_rank"]
    target = next((s for s in army["units"] if s["id"] == soldier_id), None)
    if not target:
        flash("Target not found.", "error"); return redirect(url_for("index"))
    actor = find_member_by_username(session.get("email",""), army) or {"rank":"O10","name":"System"}
    ok, msg = demote_member(actor, session.get("role"), target["username"], new_rank, army, session.get("email"))
    flash(msg, "success" if ok else "error")
    return redirect(url_for("soldier_page", soldier_id=soldier_id))

@app.route("/medal", methods=["POST"])
def medal():
    army = load_army()
    if not session.get("role") or session.get("role") == "LR":
        flash("Permission denied.", "error"); return redirect(url_for("index"))
    soldier_id = request.form["id"]
    medal_name = request.form["medal"]
    target = next((s for s in army["units"] if s["id"] == soldier_id), None)
    if not target:
        flash("Target not found.", "error"); return redirect(url_for("index"))
    actor = find_member_by_username(session.get("email",""), army) or {"rank":"O10","name":"System"}
    ok, msg = award_medal(actor, session.get("role"), target["username"], medal_name, army, session.get("email"))
    flash(msg, "success" if ok else "error")
    return redirect(url_for("soldier_page", soldier_id=soldier_id))
