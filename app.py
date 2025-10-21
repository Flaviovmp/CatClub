from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import sqlite3, os, re

import secrets
from datetime import timedelta
from urllib.parse import urljoin

def url_base():
    # Tente deduzir a URL base a partir do HOST externo
    return os.environ.get("APP_BASE_URL")  # ex.: https://seuapp.onrender.com

def send_email(to, subject, body):
    """Envio de email opcional (placeholder).
    Produção: configure SENDGRID_API_KEY ou SMTP.
    Aqui, por padrão, apenas "printa" no log do servidor para copiar o link.
    """
    print("=== EMAIL SIMULADO ===")
    print("Para:", to)
    print("Assunto:", subject)
    print("Corpo:\n", body)
    print("======================")
    # Se quiser integrar SendGrid:
    # import requests
    # key = os.environ.get("SENDGRID_API_KEY")
    # if key:
    #   requests.post("https://api.sendgrid.com/v3/mail/send", headers=..., json=...)


def parse_pagination(default_per_page=20, max_per_page=100):
    try:
        page = int(request.args.get("page", 1))
    except ValueError:
        page = 1
    try:
        per_page = int(request.args.get("per_page", default_per_page))
    except ValueError:
        per_page = default_per_page
    per_page = max(1, min(per_page, max_per_page))
    page = max(1, page)
    offset = (page - 1) * per_page
    return page, per_page, offset

def build_pagination_meta(total, page, per_page):
    from math import ceil
    total_pages = max(1, ceil(total / per_page)) if total else 1
    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages,
        "has_prev": page > 1,
        "has_next": page < total_pages,
        "prev_page": page - 1 if page > 1 else None,
        "next_page": page + 1 if page < total_pages else None,
    }


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

# ----- Admin: Breeds (Raças) -----
@app.route("/admin/breeds")
@admin_required
def admin_breeds():
    q = request.args.get("q","").strip()
    sql = "SELECT * FROM breeds"
    params = ()
    if q:
        sql += " WHERE name LIKE ?"
        params = (f"%{q}%",)
    sql += " ORDER BY name"
    with get_db() as db:
        breeds = db.execute(sql, params).fetchall()
    return render_template("admin_breeds.html", user=current_user(), breeds=breeds, q=q)

@app.route("/admin/breeds/new", methods=["GET","POST"])
@admin_required
def admin_breed_new():
    if request.method == "POST":
        name = request.form.get("name","").strip()
        if not name:
            flash("Informe o nome da raça.", "danger")
            return redirect(url_for("admin_breed_new"))
        try:
            with get_db() as db:
                db.execute("INSERT INTO breeds (name) VALUES (?)", (name,))
                db.commit()
            flash("Raça adicionada.", "success")
            return redirect(url_for("admin_breeds"))
        except sqlite3.IntegrityError:
            flash("Essa raça já existe.", "warning")
            return redirect(url_for("admin_breed_new"))
    return render_template("admin_breed_form.html", user=current_user(), mode="new", breed=None)

@app.route("/admin/breeds/<int:breed_id>/edit", methods=["GET","POST"])
@admin_required
def admin_breed_edit(breed_id):
    with get_db() as db:
        breed = db.execute("SELECT * FROM breeds WHERE id = ?", (breed_id,)).fetchone()
        if not breed:
            flash("Raça não encontrada.", "danger")
            return redirect(url_for("admin_breeds"))
    if request.method == "POST":
        name = request.form.get("name","").strip()
        if not name:
            flash("Informe o nome da raça.", "danger")
            return redirect(url_for("admin_breed_edit", breed_id=breed_id))
        try:
            with get_db() as db:
                db.execute("UPDATE breeds SET name = ? WHERE id = ?", (name, breed_id))
                db.commit()
            flash("Raça atualizada.", "success")
            return redirect(url_for("admin_breeds"))
        except sqlite3.IntegrityError:
            flash("Já existe uma raça com esse nome.", "warning")
            return redirect(url_for("admin_breed_edit", breed_id=breed_id))
    return render_template("admin_breed_form.html", user=current_user(), mode="edit", breed=breed)

@app.route("/admin/breeds/<int:breed_id>/delete", methods=["POST"])
@admin_required
def admin_breed_delete(breed_id):
    try:
        with get_db() as db:
            db.execute("DELETE FROM breeds WHERE id = ?", (breed_id,))
            db.commit()
        flash("Raça removida.", "success")
    except sqlite3.IntegrityError:
        flash("Não é possível remover: existem cores ou gatos vinculados.", "danger")
    return redirect(url_for("admin_breeds"))


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

@app.route("/admin/users")
@admin_required
def admin_users():
    q = request.args.get("q","").strip()
    page, per_page, offset = parse_pagination(default_per_page=20)

    base_sql = "FROM users"
    where = ""
    params = []
    if q:
        where = " WHERE name LIKE ? OR email LIKE ?"
        params = [f"%{q}%", f"%{q}%"]

    with get_db() as db:
        total = db.execute(f"SELECT COUNT(*) {base_sql}{where}", tuple(params)).fetchone()[0]
        users = db.execute(
            f"SELECT * {base_sql}{where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (*params, per_page, offset)
        ).fetchall()

    pagination = build_pagination_meta(total, page, per_page)
    return render_template("admin_users.html", user=current_user(), users=users, q=q, pagination=pagination)

@app.route("/admin/users/<int:user_id>/edit", methods=["GET","POST"])
@admin_required
def admin_user_edit(user_id):
    with get_db() as db:
        u = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not u:
            flash("Usuário não encontrado.", "danger")
            return redirect(url_for("admin_users"))
    if request.method == "POST":
        form = request.form
        fields = ["name","dob","sex","cpf","email","phone","address","address2","district","city","state","zipcode","country"]
        values = [form.get(k,"").strip() for k in fields]

        # validações básicas (ajuste se já tiver helpers)
        def only_digits(s): return "".join(ch for ch in (s or "") if ch.isdigit())
        def validate_cep(cep_raw): 
            import re
            return (not cep_raw) or bool(re.fullmatch(r"\d{5}-?\d{3}", cep_raw.strip()))

        if values[11] and not validate_cep(values[11]):  # CEP
            flash("CEP inválido. Use 00000-000.", "danger"); 
            return redirect(url_for("admin_user_edit", user_id=user_id))

        is_admin = 1 if form.get("is_admin") == "on" else 0
        try:
            with get_db() as db:
                db.execute("""
                    UPDATE users SET
                    name=?, dob=?, sex=?, cpf=?, email=?, phone=?, address=?, address2=?, district=?, city=?, state=?, zipcode=?, country=?, is_admin=?
                    WHERE id = ?
                """, (*values, is_admin, user_id))
                db.commit()
            flash("Usuário atualizado.", "success")
        except sqlite3.IntegrityError:
            flash("Já existe um usuário com este email.", "danger")
        return redirect(url_for("admin_users"))
    return render_template("admin_user_form.html", user=current_user(), u=u)

@app.route("/admin/users/<int:user_id>/reset-password", methods=["POST"])
@admin_required
def admin_user_reset_password(user_id):
    # Gera token válido por 24h
    with get_db() as db:
        u = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        if not u:
            flash("Usuário não encontrado.", "danger")
            return redirect(url_for("admin_users"))

        token = secrets.token_urlsafe(32)
        expires = (datetime.utcnow() + timedelta(hours=24)).isoformat()
        db.execute("""
            INSERT INTO password_resets (user_id, token, expires_at, used)
            VALUES (?, ?, ?, 0)
        """, (user_id, token, expires))
        db.commit()

    base = url_base() or request.host_url  # fallback para host atual
    reset_link = urljoin(base, f"/reset/{token}")

    # Envia email (opcional)
    body = f"Olá, {u['name']}!\n\nClique para definir uma nova senha:\n{reset_link}\n\nEste link expira em 24 horas."
    send_email(u["email"], "Reset de senha", body)

    flash(f"Link de reset gerado: {reset_link}", "success")
    return redirect(url_for("admin_user_edit", user_id=user_id))


@app.route("/reset/<token>", methods=["GET", "POST"])
def reset_with_token(token):
    with get_db() as db:
        pr = db.execute("""
            SELECT pr.*, u.email, u.name FROM password_resets pr
            JOIN users u ON u.id = pr.user_id
            WHERE pr.token = ?
        """, (token,)).fetchone()
    if not pr:
        flash("Token inválido.", "danger")
        return redirect(url_for("login"))

    # Verifica expirado/usado
    if pr["used"]:
        flash("Este link já foi utilizado.", "warning")
        return redirect(url_for("login"))
    try:
        expires = datetime.fromisoformat(pr["expires_at"])
    except Exception:
        expires = datetime.utcnow() - timedelta(seconds=1)
    if datetime.utcnow() > expires:
        flash("Este link expirou.", "warning")
        return redirect(url_for("login"))

    if request.method == "POST":
        pw = request.form.get("password","")
        pw2 = request.form.get("password2","")
        if not pw or len(pw) < 6:
            flash("Informe uma senha com pelo menos 6 caracteres.", "danger")
            return redirect(url_for("reset_with_token", token=token))
        if pw != pw2:
            flash("As senhas não conferem.", "danger")
            return redirect(url_for("reset_with_token", token=token))
        with get_db() as db:
            db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (generate_password_hash(pw), pr["user_id"]))
            db.execute("UPDATE password_resets SET used = 1 WHERE id = ?", (pr["id"],))
            db.commit()
        flash("Senha atualizada! Faça login com a nova senha.", "success")
        return redirect(url_for("login"))

    return render_template("reset_password.html", user=current_user(), token=token, pr=pr)


@app.route("/admin/users/<int:user_id>/delete", methods=["POST"])
@admin_required
def admin_user_delete(user_id):
    me = current_user()
    if me["id"] == user_id:
        flash("Você não pode excluir a si mesmo.", "danger")
        return redirect(url_for("admin_users"))

    with get_db() as db:
        # Verifica vínculos
        has_cats = db.execute("SELECT 1 FROM cats WHERE owner_id = ? LIMIT 1", (user_id,)).fetchone()
        if has_cats:
            flash("Não é possível excluir: o usuário possui gatos vinculados.", "danger")
            return redirect(url_for("admin_users"))

        db.execute("DELETE FROM users WHERE id = ?", (user_id,))
        db.commit()
    flash("Usuário excluído.", "success")
    return redirect(url_for("admin_users"))


@app.route("/admin/cats")
@admin_required
def admin_cats():
    q = request.args.get("q","").strip()
    status = request.args.get("status","")
    page, per_page, offset = parse_pagination(default_per_page=20)

    base_sql = """
        FROM cats c
        JOIN users u ON u.id = c.owner_id
        LEFT JOIN breeds b ON b.id = c.breed_id
        LEFT JOIN colors col ON col.id = c.color_id
    """
    where_clauses, params = [], []
    if q:
        where_clauses.append("(c.name LIKE ? OR u.name LIKE ? OR c.microchip LIKE ?)")
        params += [f"%{q}%", f"%{q}%", f"%{q}%"]
    if status in ("pending","approved","rejected"):
        where_clauses.append("c.status = ?")
        params.append(status)
    where = f" WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

    with get_db() as db:
        total = db.execute(f"SELECT COUNT(*) {base_sql}{where}", tuple(params)).fetchone()[0]
        cats = db.execute(f"""
            SELECT c.*, u.name AS owner_name, b.name AS breed_name, col.name AS color_name, col.ems_code
            {base_sql}{where}
            ORDER BY c.created_at DESC
            LIMIT ? OFFSET ?
        """, (*params, per_page, offset)).fetchall()
        breeds = db.execute("SELECT id, name FROM breeds ORDER BY name").fetchall()
        users = db.execute("SELECT id, name, email FROM users ORDER BY name").fetchall()

    pagination = build_pagination_meta(total, page, per_page)
    return render_template("admin_cats.html", user=current_user(), cats=cats, q=q, status=status,
                           breeds=breeds, users=users, pagination=pagination)


@app.route("/admin/cats/<int:cat_id>/edit", methods=["GET","POST"])
@admin_required
def admin_cat_edit(cat_id):
    with get_db() as db:
        cat = db.execute("SELECT * FROM cats WHERE id = ?", (cat_id,)).fetchone()
        if not cat:
            flash("Gato não encontrado.", "danger")
            return redirect(url_for("admin_cats"))
        breeds = db.execute("SELECT id, name FROM breeds ORDER BY name").fetchall()
        colors = db.execute("SELECT id, name, ems_code FROM colors WHERE breed_id = ? ORDER BY name", (cat["breed_id"],)).fetchall()
        users = db.execute("SELECT id, name FROM users ORDER BY name").fetchall()
    if request.method == "POST":
        f = request.form
        with get_db() as db:
            db.execute("""
                UPDATE cats SET
                  owner_id=?, name=?, breed_id=?, color_id=?, dob=?, registry_number=?, registry_entity=?,
                  microchip=?, sex=?, neutered=?, breeder_type=?, breeder_name=?,
                  sire_name=?, sire_breed_id=?, sire_color_id=?,
                  dam_name=?, dam_breed_id=?, dam_color_id=?, status=?
                WHERE id = ?
            """, (
                f.get("owner_id"), f.get("name","").strip(), f.get("breed_id"), f.get("color_id"),
                f.get("dob") or None, f.get("registry_number","").strip(), f.get("registry_entity","").strip(),
                f.get("microchip","").strip(), f.get("sex","").strip(), 1 if f.get("neutered") == "SIM" else 0,
                f.get("breeder_type","").strip(), f.get("breeder_name","").strip(),
                f.get("sire_name","").strip(), f.get("sire_breed_id") or None, f.get("sire_color_id") or None,
                f.get("dam_name","").strip(), f.get("dam_breed_id") or None, f.get("dam_color_id") or None,
                f.get("status","pending"), cat_id
            ))
            db.commit()
        flash("Gato atualizado.", "success")
        return redirect(url_for("admin_cats"))
    return render_template("admin_cat_form.html", user=current_user(), cat=cat, breeds=breeds, colors=colors, users=users)


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

@app.route("/admin/cats/<int:cat_id>/delete", methods=["POST"])
@admin_required
def admin_cat_delete(cat_id):
    with get_db() as db:
        db.execute("DELETE FROM cats WHERE id = ?", (cat_id,))
        db.commit()
    flash("Gato excluído.", "success")
    return redirect(url_for("admin_cats"))

