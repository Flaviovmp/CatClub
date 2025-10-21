from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import sqlite3
import os
import re

DB_PATH = os.path.join(os.path.dirname(__file__), "catclub.db")

UF_LIST = ["AC","AL","AP","AM","BA","CE","DF","ES","GO","MA","MT","MS","MG","PA","PB","PR","PE","PI","RJ","RN","RS","RO","RR","SC","SP","SE","TO"]

def only_digits(s):
    return "".join(ch for ch in (s or "") if ch.isdigit())

def validate_cpf(cpf_raw: str) -> bool:
    cpf = only_digits(cpf_raw)
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    sum1 = sum(int(cpf[i]) * (10 - i) for i in range(9))
    d1 = (sum1 * 10) % 11
    d1 = 0 if d1 == 10 else d1
    sum2 = sum(int(cpf[i]) * (11 - i) for i in range(10))
    d2 = (sum2 * 10) % 11
    d2 = 0 if d2 == 10 else d2
    return d1 == int(cpf[9]) and d2 == int(cpf[10])

def validate_cep(cep_raw: str) -> bool:
    if not cep_raw:
        return True
    return re.fullmatch(r"\d{5}-?\d{3}", cep_raw.strip()) is not None

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")

    # ---------- DB INIT ----------
    with get_db() as db:
        db.executescript(open(os.path.join(os.path.dirname(__file__), "schema.sql"), "r", encoding="utf-8").read())
        # Seed minimal data if empty
        bcount = db.execute("SELECT COUNT(*) AS c FROM breeds").fetchone()["c"]
        if bcount == 0:
            seed_code = ""
            with open(os.path.join(os.path.dirname(__file__), "seed.py"), "r", encoding="utf-8") as f:
                seed_code = f.read()
            exec(seed_code, {"get_db": get_db})
    return app

app = create_app()

def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    with get_db() as db:
        return db.execute("SELECT * FROM users WHERE id = ?", (uid,)).fetchone()

def login_required(fn):
    from functools import wraps
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            flash("Faça login para continuar.", "warning")
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

def admin_required(fn):
    from functools import wraps
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = current_user()
        if not user or not user["is_admin"]:
            flash("Acesso restrito ao administrador.", "danger")
            return redirect(url_for("index"))
        return fn(*args, **kwargs)
    return wrapper

@app.route("/")
def index():
    return render_template("index.html", user=current_user())

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        # Personal data
        name = request.form.get("name","").strip()
        dob = request.form.get("dob") or None
        sex = request.form.get("sex","").strip()
        cpf = request.form.get("cpf","").strip()
        email = request.form.get("email","").strip().lower()
        phone = request.form.get("phone","").strip()

        # Address
        address = request.form.get("address","").strip()
        address2 = request.form.get("address2","").strip()
        district = request.form.get("district","").strip()
        city = request.form.get("city","").strip()
        state = request.form.get("state","").strip()
        zipcode = request.form.get("zipcode","").strip()
        country = request.form.get("country","").strip()

        # Access
        password = request.form.get("password","")
        password2 = request.form.get("password2","")

        # Validations
        if not name or not email or not password:
            flash("Preencha pelo menos Nome, Email e Senha.", "danger")
            return redirect(url_for("register"))
        if password != password2:
            flash("As senhas não conferem.", "danger")
            return redirect(url_for("register"))
        if cpf and not validate_cpf(cpf):
            flash("CPF inválido.", "danger")
            return redirect(url_for("register"))
        if state and state not in UF_LIST:
            flash("Selecione um estado (UF) válido.", "danger")
            return redirect(url_for("register"))
        if zipcode and not validate_cep(zipcode):
            flash("CEP inválido. Use 00000-000.", "danger")
            return redirect(url_for("register"))

        with get_db() as db:
            existing = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
            if existing:
                flash("Já existe um usuário com este email.", "danger")
                return redirect(url_for("register"))
            db.execute("""
                INSERT INTO users
                (name, dob, sex, cpf, email, phone, address, address2, district, city, state, zipcode, country, password_hash, is_admin)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            """, (name, dob, sex, cpf, email, phone, address, address2, district, city, state, zipcode, country, generate_password_hash(password)))
            db.commit()
        flash("Cadastro realizado com sucesso! Faça o login para continuar.", "success")
        return redirect(url_for("login"))

    return render_template("register.html", user=current_user())

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email","").lower().strip()
        password = request.form.get("password","")
        with get_db() as db:
            user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            flash("Login realizado!", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("Email ou senha inválidos.", "danger")
    return render_template("login.html", user=current_user())

@app.route("/logout")
def logout():
    session.clear()
    flash("Você saiu da sua conta.", "info")
    return redirect(url_for("index"))

@app.route("/dashboard")
@login_required
def dashboard():
    user = current_user()
    with get_db() as db:
        cats = db.execute("""
            SELECT c.*, b.name AS breed_name, col.name AS color_name, col.ems_code
            FROM cats c
            LEFT JOIN breeds b ON b.id = c.breed_id
            LEFT JOIN colors col ON col.id = c.color_id
            WHERE c.owner_id = ?
            ORDER BY c.created_at DESC
        """, (user["id"],)).fetchall()
    return render_template("dashboard.html", user=user, cats=cats)

@app.route("/api/colors")
def api_colors():
    breed_id = request.args.get("breed_id")
    if not breed_id:
        return jsonify([])
    with get_db() as db:
        rows = db.execute("SELECT id, name, ems_code FROM colors WHERE breed_id = ? ORDER BY name", (breed_id,)).fetchall()
    return jsonify([{"id": r["id"], "name": r["name"], "ems_code": r["ems_code"]} for r in rows])

@app.route("/cats/new", methods=["GET","POST"])
@login_required
def cat_new():
    user = current_user()
    with get_db() as db:
        breeds = db.execute("SELECT id, name FROM breeds ORDER BY name").fetchall()

    if request.method == "POST":
        form = request.form
        name = form.get("name","").strip()
        breed_id = form.get("breed_id")
        color_id = form.get("color_id")
        dob = form.get("dob") or None
        registry_number = form.get("registry_number","").strip()
        registry_entity = form.get("registry_entity","").strip()
        microchip = form.get("microchip","").strip()
        sex = form.get("sex","").strip()
        neutered = 1 if form.get("neutered") == "SIM" else 0
        breeder_type = form.get("breeder_type","").strip()
        breeder_name = form.get("breeder_name","").strip() if breeder_type == "outro" else ""

        sire_name = form.get("sire_name","").strip()
        sire_breed_id = form.get("sire_breed_id")
        sire_color_id = form.get("sire_color_id")

        dam_name = form.get("dam_name","").strip()
        dam_breed_id = form.get("dam_breed_id")
        dam_color_id = form.get("dam_color_id")

        if not name or not breed_id or not color_id or not sex:
            flash("Preencha pelo menos: Nome do gato, Raça, Cor e Sexo.", "danger")
            return redirect(url_for("cat_new"))

        with get_db() as db:
            db.execute("""
                INSERT INTO cats
                (owner_id, name, breed_id, color_id, dob, registry_number, registry_entity, microchip, sex, neutered, breeder_type, breeder_name,
                 sire_name, sire_breed_id, sire_color_id, dam_name, dam_breed_id, dam_color_id, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)
            """, (user["id"], name, breed_id, color_id, dob, registry_number, registry_entity, microchip, sex, neutered, breeder_type, breeder_name,
                  sire_name, sire_breed_id, sire_color_id, dam_name, dam_breed_id, dam_color_id, datetime.utcnow().isoformat()))
            db.commit()
        flash("Cadastro enviado! Aguarde aprovação do administrador.", "success")
        return redirect(url_for("dashboard"))

    return render_template("cat_form.html", user=user, breeds=breeds)

@app.route("/admin")
@admin_required
def admin_home():
    with get_db() as db:
        pending = db.execute("""
            SELECT c.*, u.name AS owner_name, b.name AS breed_name, col.name AS color_name, col.ems_code
            FROM cats c
            JOIN users u ON u.id = c.owner_id
            LEFT JOIN breeds b ON b.id = c.breed_id
            LEFT JOIN colors col ON col.id = c.color_id
            WHERE c.status = 'pending'
            ORDER BY c.created_at ASC
        """).fetchall()
    return render_template("admin_pending.html", user=current_user(), cats=pending)

@app.route("/admin/cats/<int:cat_id>/<action>", methods=["POST"])
@admin_required
def admin_cat_action(cat_id, action):
    if action not in ("approve","reject"):
        flash("Ação inválida.", "danger")
        return redirect(url_for("admin_home"))
    new_status = "approved" if action == "approve" else "rejected"
    with get_db() as db:
        db.execute("UPDATE cats SET status = ? WHERE id = ?", (new_status, cat_id))
        db.commit()
    flash(f"Registro do gato atualizado para: {new_status}.", "success")
    return redirect(url_for("admin_home"))

@app.route("/make-admin", methods=["POST"])
def make_admin():
    email = request.form.get("email","").lower().strip()
    if not email:
        flash("Informe um email.", "danger")
        return redirect(url_for("index"))
    with get_db() as db:
        db.execute("UPDATE users SET is_admin = 1 WHERE email = ?", (email,))
        db.commit()
    flash(f"{email} agora é admin.", "success")
    return redirect(url_for("index"))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
