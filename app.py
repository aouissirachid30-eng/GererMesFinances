# -*- coding: utf-8 -*-
from flask import Flask, render_template, request, redirect
import sqlite3
import shutil
from datetime import datetime
import os

app = Flask(__name__)


DB = "finance.db"

# ================= DB =================
def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def get_parametres():
    db = get_db()
    param = db.execute("SELECT * FROM parametres LIMIT 1").fetchone()
    db.close()
    return param

# ================= INIT DB =================
def init_db():
    db = get_db()

    db.execute("""
    CREATE TABLE IF NOT EXISTS comptes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT,
        solde_initial REAL
    )
    """)

    db.execute("""
    CREATE TABLE IF NOT EXISTS familles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT,
        icone TEXT,
        budget REAL DEFAULT 0
    )
    """)

    db.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        compte_id INTEGER,
        date TEXT,
        categorie TEXT,
        famille_id INTEGER,
        designation TEXT,
        montant REAL
    )
    """)

    db.execute("""
    CREATE TABLE IF NOT EXISTS budgets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        famille_id INTEGER,
        montant REAL
    )
    """)

    db.execute("""
    CREATE TABLE IF NOT EXISTS parametres (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        devise TEXT DEFAULT 'DZD',
        theme TEXT DEFAULT 'clair',
        langue TEXT DEFAULT 'fr',
        date_debut TEXT DEFAULT '2026-01-01',
        date_fin TEXT DEFAULT '2026-12-31'
    )
    """)

    # INSERT SAFE (UNE SEULE LIGNE)
    db.execute("""
    INSERT OR IGNORE INTO parametres (id, devise, theme, langue, date_debut, date_fin)
    VALUES (1, 'DZD', 'clair', 'fr', '2026-01-01', '2026-12-31')
    """)

    db.commit()
    db.close()
#=================Test====================
#@app.route("/test")
#def test():
#    return "FLASK OK"
# ================= LOGIN =================
def get_periode():
    db = get_db()
    p = db.execute("SELECT * FROM parametres LIMIT 1").fetchone()
    db.close()

    if not p:
        return {
            "date_debut": "2000-01-01",
            "date_fin": "2099-12-31"
        }

    # 🔥 sécurité obligatoire (cas ancienne DB)
    return {
        "id": p["id"],
        "devise": p["devise"],
        "theme": p["theme"],
        "langue": p["langue"],
        "date_debut": p["date_debut"] if "date_debut" in p.keys() else "2000-01-01",
        "date_fin": p["date_fin"] if "date_fin" in p.keys() else "2099-12-31"
    }


def hors_periode():
    p = get_periode()
    today = datetime.now().strftime("%Y-%m-%d")

    return not (p["date_debut"] <= today <= p["date_fin"])

# ================= PROTECTION =================
@app.route("/")
def index():

    db = get_db()

    comptes = db.execute("SELECT * FROM comptes").fetchall()

    comptes_avec_solde = []

    for c in comptes:
        total = db.execute("""
            SELECT 
                SUM(CASE 
                    WHEN categorie = 'Revenu' THEN montant
                    ELSE -montant
                END) as solde
            FROM transactions
            WHERE compte_id=?
        """, (c["id"],)).fetchone()["solde"]

        solde_actuel = c["solde_initial"] + (total if total else 0)

        comptes_avec_solde.append({
            "id": c["id"],
            "nom": c["nom"],
            "solde_initial": c["solde_initial"],
            "solde_actuel": solde_actuel
        })

    db.close()

    return render_template("index.html", comptes=comptes_avec_solde)
# ================= PARAMETRES =================
@app.route("/parametres", methods=["GET", "POST"])
def parametres():

    db = get_db()

    if request.method == "POST":
        db.execute("""
        UPDATE parametres
        SET devise=?, theme=?, langue=?, date_debut=?, date_fin=?
        """, (
            request.form["devise"],
            request.form["theme"],
            request.form["langue"],
            request.form["date_debut"],
            request.form["date_fin"]
        ))
        db.commit()

    param = db.execute("SELECT * FROM parametres LIMIT 1").fetchone()
    db.close()

    return render_template("parametres.html", param=param)


# ================= RESTORE =================
@app.route("/restore", methods=["POST"])
def restore():

    file = request.files["file"]

    if not file:
        return "Aucun fichier sélectionné"

    backup_name = "backup_before_restore_" + datetime.now().strftime("%Y%m%d_%H%M") + ".db"
    shutil.copy(DB, backup_name)

    db_path = os.path.join(os.getcwd(), DB)
    file.save(db_path)

    return f"✔ Restauré + backup {backup_name}"

# ================= COMPTES =================
@app.route("/add_compte", methods=["POST"])
def add_compte():
    db = get_db()
    db.execute("INSERT INTO comptes (nom, solde_initial) VALUES (?, ?)",
               (request.form["nom"], float(request.form["solde"])))
    db.commit()
    db.close()
    return redirect("/")

#@app.route("/delete_compte/<int:id>")
#def delete_compte(id):
#    db = get_db()
#    db.execute("DELETE FROM comptes WHERE id=?", (id,))
#    db.commit()
#    db.close()
#    return redirect("/")
#=================Supp_Compte=====================
@app.route("/delete_compte/<int:id>")
def delete_compte(id):
    db = get_db()
    db.execute("DELETE FROM comptes WHERE id=?", (id,))
    db.commit()
    db.close()
    return redirect("/")

# ================= TRANSACTIONS =================
@app.route("/transactions/<int:id>")
def transactions(id):

    db = get_db()

    compte = db.execute("SELECT * FROM comptes WHERE id=?", (id,)).fetchone()

    trans = db.execute("""
    SELECT t.*, f.nom as famille
    FROM transactions t
    LEFT JOIN familles f ON t.famille_id = f.id
    WHERE t.compte_id=?
    ORDER BY t.date
    """, (id,)).fetchall()

    solde = compte["solde_initial"]
    result = []

    for t in trans:
        if t["categorie"] == "Revenu":
            solde += t["montant"]
        else:
            solde -= t["montant"]

        result.append(dict(t))
        result[-1]["solde"] = solde

    familles = db.execute("SELECT * FROM familles").fetchall()
    db.close()

    return render_template("transactions.html",
                           transactions=result,
                           familles=familles,
                           compte=compte)

@app.route("/add_transaction/<int:id>", methods=["POST"])
def add_transaction(id):

    db = get_db()

    db.execute("""
    INSERT INTO transactions (compte_id, date, categorie, famille_id, designation, montant)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (
        id,
        request.form["date"],
        request.form["categorie"],
        request.form["famille_id"],
        request.form["designation"],
        float(request.form["montant"])
    ))

    db.commit()
    db.close()

    return redirect(f"/transactions/{id}")
#=============Modif_Transaction=========================
@app.route("/edit_transaction/<int:id>/<int:compte_id>", methods=["GET", "POST"])
def edit_transaction(id, compte_id):
    db = get_db()

    if request.method == "POST":
        db.execute("""
            UPDATE transactions
            SET designation=?, montant=?, date=?, categorie=?, famille_id=?
            WHERE id=?
        """, (
            request.form["designation"],
            request.form["montant"],
            request.form["date"],
            request.form["categorie"],
            request.form["famille_id"],
            id
        ))
        db.commit()
        db.close()
        return redirect(f"/transactions/{compte_id}")

    transaction = db.execute(
        "SELECT * FROM transactions WHERE id=?",
        (id,)
    ).fetchone()

    familles = db.execute("SELECT * FROM familles").fetchall()

    db.close()

    return render_template(
        "modifier_transaction.html",
        transaction=transaction,
        compte_id=compte_id,
        familles=familles
    )

#=================Supp_Transaction===============
@app.route("/delete_transaction/<int:id>/<int:compte_id>")
def delete_transaction(id, compte_id):
    db = get_db()
    db.execute("DELETE FROM transactions WHERE id = ?", (id,))
    db.commit()
    db.close()
    return redirect("/transactions")
#===================FAMILLES===================
@app.route("/familles")
def familles():
    db = get_db()
    familles = db.execute("SELECT * FROM familles").fetchall()
    db.close()
    return render_template("familles.html", familles=familles)
#===================AJOUT_FAMILLE==============
@app.route("/add_famille", methods=["POST"])
def add_famille():
    db = get_db()

    nom = request.form["nom"]
    budget = request.form.get("budget")

    if not budget:
        budget = 0

    icone = request.form.get("icone", "")

    db.execute(
        "INSERT INTO familles (nom, budget, icone) VALUES (?, ?, ?)",
        (nom, float(budget), icone)
    )

    db.commit()
    db.close()

    return redirect("/familles")
#====================EDIT_FAMILLE==============
@app.route("/edit_famille/<int:id>", methods=["GET", "POST"])
def edit_famille(id):
    db = get_db()

    if request.method == "POST":
        db.execute("""
            UPDATE familles
            SET nom=?, budget=?, icone=?
            WHERE id=?
        """, (
            request.form["nom"],
            float(request.form.get("budget", 0)),
            request.form.get("icone", ""),
            id
        ))

        db.commit()
        db.close()
        return redirect("/familles")

    famille = db.execute(
        "SELECT * FROM familles WHERE id=?",
        (id,)
    ).fetchone()

    db.close()

    return render_template("edit_famille.html", famille=famille)
#====================DELETE_FAMILLE============
@app.route("/delete_famille/<int:id>")
def delete_famille(id):
    db = get_db()

    db.execute("DELETE FROM transactions WHERE famille_id=?", (id,))
    db.execute("DELETE FROM familles WHERE id=?", (id,))

    db.commit()
    db.close()

    return redirect("/familles")
#===================FAMILLES_DATES=============
@app.route("/famille/<int:id>")
def voir_famille(id):
    db = get_db()

    famille = db.execute(
        "SELECT * FROM familles WHERE id=?",
        (id,)
    ).fetchone()

    transactions = db.execute("""
        SELECT * FROM transactions
        WHERE famille_id=?
        ORDER BY date DESC
    """, (id,)).fetchall()

    revenus = sum(t["montant"] for t in transactions if t["categorie"] == "Revenu")
    depenses = sum(t["montant"] for t in transactions if t["categorie"] != "Revenu")

    db.close()

    return render_template(
        "voir_famille.html",
        famille=famille,
        transactions=transactions,
        revenus=revenus,
        depenses=depenses
    )
#===================NOUVELLE_ANNEE=============
@app.route("/nouvelle_annee", methods=["POST"])
def nouvelle_annee():
    db = get_db()   # ⚠️ OBLIGATOIRE

    param = get_parametres()

    if not param:
        db.close()
        return redirect("/dashboard")

    debut = param["date_debut"]
    fin = param["date_fin"]

    # sécurité si valeurs manquantes
    if not debut or not fin:
        db.close()
        return redirect("/dashboard")

    from datetime import datetime

    debut_dt = datetime.strptime(debut, "%Y-%m-%d")
    fin_dt = datetime.strptime(fin, "%Y-%m-%d")

    new_debut = debut_dt.replace(year=debut_dt.year + 1)
    new_fin = fin_dt.replace(year=fin_dt.year + 1)

    db.execute("""
        UPDATE parametres
        SET date_debut=?, date_fin=?
    """, (
        new_debut.strftime("%Y-%m-%d"),
        new_fin.strftime("%Y-%m-%d")
    ))

    db.commit()
    db.close()

    return redirect("/dashboard")
#===================DASHBOARD==================
@app.route("/dashboard")
def dashboard():
    if hors_periode():
        return render_template("hors_periode.html")

    db = get_db()
    param = get_parametres()

    data = db.execute("""
    SELECT 
        f.nom,
        COALESCE(f.budget, 0) as budget,
        COALESCE(SUM(t.montant), 0) as depense
    FROM familles f
    LEFT JOIN transactions t 
        ON t.famille_id = f.id 
        AND t.categorie != 'Revenu'
        AND t.date BETWEEN ? AND ?
    GROUP BY f.id
    """, (param["date_debut"], param["date_fin"])).fetchall()

    total = db.execute("""
    SELECT 
    COALESCE(SUM(CASE WHEN categorie='Revenu' THEN montant ELSE 0 END), 0) as revenus,
    COALESCE(SUM(CASE WHEN categorie!='Revenu' THEN montant ELSE 0 END), 0) as depenses
    FROM transactions
    WHERE date BETWEEN ? AND ?
    """, (param["date_debut"], param["date_fin"])).fetchone()

    # 🔥 SAFE FIX (IMPORTANT)
    total = dict(total) if total else {"revenus": 0, "depenses": 0}

    db.close()

    return render_template("dashboard.html", data=data, total=total, param=param)
# ================= TRANSFERT =================
@app.route("/transfert", methods=["POST"])
def transfert():

    db = get_db()

    source = int(request.form["source"])
    dest = int(request.form["dest"])
    montant = float(request.form["montant"])
    date = request.form["date"]

    db.execute("""
    INSERT INTO transactions (compte_id, date, categorie, designation, montant)
    VALUES (?, ?, 'Dépense', 'Transfert', ?)
    """, (source, date, montant))

    db.execute("""
    INSERT INTO transactions (compte_id, date, categorie, designation, montant)
    VALUES (?, ?, 'Revenu', 'Transfert', ?)
    """, (dest, date, montant))

    db.commit()
    db.close()

    return redirect("/")
#===============CONTEXT_PROCESSOR========
translations = {
    "fr": {
        "comptes": "Comptes",
        "familles": "Familles",
        "dashboard": "Dashboard",
        "parametres": "Paramètres"
    },
    "en": {
        "comptes": "Accounts",
        "familles": "Categories",
        "dashboard": "Dashboard",
        "parametres": "Settings"
    },
    "ar": {
        "comptes": "الحسابات",
        "familles": "الفئات",
        "dashboard": "لوحة التحكم",
        "parametres": "الإعدادات"
    }
}

@app.context_processor
def inject_param():
    param = get_parametres()

    return dict(
        param=param,
        t=translations.get(param["langue"] if param else "fr", translations["fr"])
    )
#====================PROCESSOR===========
#@app.context_processor
#def inject_param():
#    return dict(param=get_parametres())
#=================CARTE==================
@app.route("/carte")
def carte():
    db = get_db()

    comptes = db.execute("SELECT * FROM comptes").fetchall()

    total = 0
    for c in comptes:
        solde = c["solde_initial"]
        trans = db.execute(
            "SELECT * FROM transactions WHERE compte_id=?",
            (c["id"],)
        ).fetchall()

        for t in trans:
            if t["categorie"] == "Revenu":
                solde += t["montant"]
            else:
                solde -= t["montant"]

        total += solde

    db.close()

    return render_template("carte.html", solde=round(total, 2))
# ================= RUN =================
if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port)