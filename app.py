# app.py — CatClube (Flask + SQLAlchemy)
import os
import csv
import datetime as dt

from flask import (
    Flask, render_template, request, redirect, url_for, flash, session, g, jsonify
)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_, func
from sqlalchemy.orm import joinedload
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

# ------------------------------------------------------------------------------
# Configuração básica
# ------------------------------------------------------------------------------
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "catclube.db")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-catclube")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{DB_PATH}"
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
# Se for usar no Render, considere APP_BASE_URL para links absolutos de reset
APP_BASE_URL = os.getenv("APP_BASE_URL", "")

db = SQLAlchemy(app)

# ------------------------------------------------------------------------------
# Modelos
# ------------------------------------------------------------------------------
class User(db.Model):
    __tablename__ = "users"
    id         = db.Column(db.Integer, primary_key=True)
    name       = db.Column(db.String(200), nullable=False)
    dob        = db.Column(db.Date, nullable=True)
    sex        = db.Column(db.String(50), nullable=True)
    cpf        = db.Column(db.String(40), nullable=True)
    email      = db.Column(db.String(200), unique=True, nullable=False)
    phone      = db.Column(db.String(50), nullable=True)

    address    = db.Column(db.String(255), nullable=True)
    address2   = db.Column(db.String(255), nullable=True)
    district   = db.Column(db.String(120), nullable=True)
    city       = db.Column(db.String(120), nullable=True)
    state      = db.Column(db.String(10), nullable=True)
    zipcode    = db.Column(db.String(20), nullable=True)
    country    = db.Column(db.String(120), nullable=True)

    password_hash = db.Column(db.String(255), nullable=False)
    is_admin      = db.Column(db.Boolean, default=False)

    created_at = db.Column(db.DateTime, default=dt.datetime.utcnow)

    cats = db.relationship("Cat", backref="owner", lazy=True)

    def set_password(self, raw):
        self.password_hash = generate_password_hash(raw)

    def check_password(self, raw):
        return check_password_hash(self.password_hash, raw)


class Breed(db.Model):
    __tablename__ = "breeds"
    id   = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), unique=True, nullable=False)

    colors = db.relationship("Color", backref="breed", lazy=True)


class Color(db.Model):
    __tablename__ = "colors"
    id       = db.Column(db.Integer, primary_key=True)
    breed_id = db.Column(db.Integer, db.ForeignKey("breeds.id"), nullable=False)
    name     = db.Column(db.String(200), nullable=False)
    ems_code = db.Column(db.String(100), nullable=False)


class Cat(db.Model):
    __tablename__ = "cats"
    id        = db.Column(db.Integer, primary_key=True)
    owner_id  = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    breed_id  = db.Column(db.Integer, db.ForeignKey("breeds.id"), nullable=True)
    color_id  = db.Column(db.Integer, db.ForeignKey("colors.id"), nullable=True)

    name      = db.Column(db.String(200), nullable=False)
    dob       = db.Column(db.Date, nullable=True)
    sex       = db.Column(db.String(20), nullable=True)  # "Macho" | "Fêmea"
    neutered  = db.Column(db.Boolean, default=False)
    microchip = db.Column(db.String(120), nullable=True)

    registry_number = db.Column(db.String(120), nullable=True)
    registry_entity = db.Column(db.String(120), nullable=True)  # "FIFE Brasil" | "FIFE não Brasil" | "não FIFE"

    breeder_type = db.Column(db.String(40), nullable=True)  # "eu mesmo" | "outro"
    breeder_name = db.Column(db.String(200), nullable=True)

    sire_name       = db.Column(db.String(200), nullable=True)
    sire_breed_id   = db.Column(db.Integer, db.ForeignKey("breeds.id"), nullable=True)
    sire_color_id   = db.Column(db.Integer, db.ForeignKey("colors.id"), nullable=True)

    dam_name        = db.Column(db.String(200), nullable=True)
    dam_breed_id    = db.Column(db.Integer, db.ForeignKey("breeds.id"), nullable=True)
    dam_color_id    = db.Column(db.Integer, db.ForeignKey("colors.id"), nullable=True)

    status     = db.Column(db.String(20), default="pending")  # "pending" | "approved" | "rejected"
    created_at = db.Column(db.DateTime, default=dt.datetime.utcnow)

    breed = db.relationship("Breed", foreign_keys=[breed_id], lazy=True)
    color = db.relationship("Color", foreign_keys=[color_id], lazy=True)
    sire_breed = db.relationship("Breed", foreign_keys=[sire_breed_id], lazy=True)
    sire_color = db.relationship("Color", foreign_keys=[sire_color_id], lazy=True)
    dam_breed  = db.relationship("Breed", foreign_keys=[dam_breed_id], lazy=True)
    dam_color  = db.relationship("Color", foreign_keys=[dam_color_id], lazy=True)

# ------------------------------------------------------------------------------
# Helpers: auth & paginação
# ------------------------------------------------------------------------------
def _reset_serializer():
    return URLSafeTimedSerializer(app.config["SECRET_KEY"], salt="password-reset")

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
        uid = session.get("user_id")
        if not uid:
            flash("Faça login para continuar.", "warning")
            return redirect(url_for("login"))
        user = db.session.get(User, uid)
        if not user or not user.is_admin:
            flash("Acesso restrito ao administrador.", "danger")
            return redirect(url_for("index"))
        g.user = user
        return fn(*args, **kwargs)
    return wrapper

def _paginate(query, page, per_page=20):
    total = query.count()
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))
    items = query.offset((page - 1) * per_page).limit(per_page).all()
    return items, {
        "page": page,
        "per_page": per_page,
        "total": total,
        "total_pages": total_pages,
        "has_prev": page > 1,
        "has_next": page < total_pages,
        "prev_page": page - 1 if page > 1 else None,
        "next_page": page + 1 if page < total_pages else None,
    }

def _parse_date(s):
    if not s:
        return None
    try:
        return dt.date.fromisoformat(s)
    except Exception:
        return None

# ------------------------------------------------------------------------------
# Hooks & Context
# ------------------------------------------------------------------------------
@app.before_request
def load_current_user():
    g.user = None
    uid = session.get("user_id")
    if uid:
        g.user = db.session.get(User, uid)

@app.context_processor
def inject_user():
    return {"user": g.get("user")}

# ------------------------------------------------------------------------------
# Rotas públicas: index, cadastro, login, logout, dashboard, gato novo
# ------------------------------------------------------------------------------
@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

@app.route("/make-admin", methods=["POST"])
def make_admin():
    # atalho demo: promover um usuário informado por email
    email = (request.form.get("email") or "").strip().lower()
    if not email:
        flash("Informe um e-mail.", "warning")
        return redirect(url_for("index"))
    u = db.session.query(User).filter(func.lower(User.email) == email).first()
    if not u:
        flash("Usuário não encontrado.", "warning")
        return redirect(url_for("index"))
    u.is_admin = True
    db.session.commit()
    flash(f"{u.email} agora é administrador.", "success")
    return redirect(url_for("index"))

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name  = (request.form.get("name") or "").strip()
        dob   = _parse_date(request.form.get("dob"))
        sex   = request.form.get("sex") or None
        cpf   = request.form.get("cpf") or None
        email = (request.form.get("email") or "").strip().lower()
        phone = request.form.get("phone") or None

        address  = request.form.get("address") or None
        address2 = request.form.get("address2") or None
        district = request.form.get("district") or None
        city     = request.form.get("city") or None
        state    = request.form.get("state") or None
        zipcode  = request.form.get("zipcode") or None
        country  = request.form.get("country") or None

        p1 = request.form.get("password") or ""
        p2 = request.form.get("password2") or ""
        if not name or not email or not p1:
            flash("Preencha nome, email e senha.", "warning")
            return render_template("register.html")
        if p1 != p2:
            flash("As senhas não coincidem.", "warning")
            return render_template("register.html")
        if db.session.query(User).filter(func.lower(User.email)==email).first():
            flash("Email já cadastrado.", "warning")
            return render_template("register.html")

        u = User(
            name=name, dob=dob, sex=sex, cpf=cpf, email=email, phone=phone,
            address=address, address2=address2, district=district, city=city,
            state=state, zipcode=zipcode, country=country
        )
        u.set_password(p1)
        db.session.add(u)
        db.session.commit()

        session["user_id"] = u.id
        flash("Cadastro realizado. Bem-vindo!", "success")
        return redirect(url_for("dashboard"))
    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        password = request.form.get("password") or ""
        u = db.session.query(User).filter(func.lower(User.email)==email).first()
        if not u or not u.check_password(password):
            flash("Credenciais inválidas.", "danger")
            return render_template("login.html")
        session["user_id"] = u.id
        flash("Login efetuado.", "success")
        return redirect(url_for("dashboard"))
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("user_id", None)
    flash("Você saiu da sua conta.", "info")
    return redirect(url_for("index"))

@app.route("/dashboard")
@login_required
def dashboard():
    cats = (
        db.session.query(Cat)
        .options(joinedload(Cat.breed), joinedload(Cat.color))
        .filter(Cat.owner_id == g.user.id)
        .order_by(Cat.created_at.desc())
        .all()
    )
    rows = []
    for c in cats:
        rows.append({
            "name": c.name,
            "breed_name": c.breed.name if c.breed else None,
            "color_name": c.color.name if c.color else None,
            "ems_code": c.color.ems_code if c.color else None,
            "dob": c.dob.isoformat() if c.dob else None,
            "status": c.status,
        })
    return render_template("dashboard.html", cats=rows)

@app.route("/cats/new", methods=["GET", "POST"])
@login_required
def cat_new():
    breeds = db.session.query(Breed).order_by(Breed.name.asc()).all()
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        if not name:
            flash("Informe o nome do gato.", "warning")
            return render_template("cat_form.html", breeds=breeds)

        cat = Cat(
            owner_id=g.user.id,
            name=name,
            breed_id=request.form.get("breed_id", type=int),
            color_id=request.form.get("color_id", type=int),
            dob=_parse_date(request.form.get("dob")),
            sex=request.form.get("sex") or None,
            neutered=(request.form.get("neutered") == "SIM"),
            microchip=request.form.get("microchip") or None,
            registry_number=request.form.get("registry_number") or None,
            registry_entity=request.form.get("registry_entity") or None,
            breeder_type=request.form.get("breeder_type") or None,
            breeder_name=request.form.get("breeder_name") or None,
            sire_name=request.form.get("sire_name") or None,
            sire_breed_id=request.form.get("sire_breed_id", type=int),
            sire_color_id=request.form.get("sire_color_id", type=int),
            dam_name=request.form.get("dam_name") or None,
            dam_breed_id=request.form.get("dam_breed_id", type=int),
            dam_color_id=request.form.get("dam_color_id", type=int),
            status="pending",
        )
        db.session.add(cat)
        db.session.commit()
        flash("Cadastro enviado para aprovação do administrador.", "success")
        return redirect(url_for("dashboard"))

    return render_template("cat_form.html", breeds=breeds)

# ------------------------------------------------------------------------------
# API colors (para selects dinâmicos)
# ------------------------------------------------------------------------------
@app.route("/api/colors")
@login_required
def api_colors():
    breed_id = request.args.get("breed_id", type=int)
    if not breed_id:
        return jsonify([])
    colors = (
        db.session.query(Color)
        .filter(Color.breed_id == breed_id)
        .order_by(Color.name.asc())
        .all()
    )
    return jsonify([{"id": c.id, "name": c.name, "ems_code": c.ems_code} for c in colors])

# ------------------------------------------------------------------------------
# Admin - Home (pendentes) e ações aprovar/rejeitar
# ------------------------------------------------------------------------------
@app.route("/admin/home")
@admin_required
def admin_home():
    cats = (
        db.session.query(Cat)
        .options(joinedload(Cat.breed), joinedload(Cat.color), joinedload(Cat.owner))
        .filter(Cat.status == "pending")
        .order_by(Cat.created_at.desc())
        .all()
    )
    rows = []
    for c in cats:
        rows.append({
            "id": c.id,
            "name": c.name,
            "owner_name": c.owner.name if c.owner else "-",
            "breed_name": c.breed.name if c.breed else None,
            "color_name": c.color.name if c.color else None,
            "ems_code": c.color.ems_code if c.color else None,
            "created_at": c.created_at.strftime("%Y-%m-%d %H:%M"),
        })
    return render_template("admin_pending.html", cats=rows)

@app.route("/admin/cats/<int:cat_id>/<action>", methods=["POST"])
@admin_required
def admin_cat_action(cat_id, action):
    cat = db.session.get(Cat, cat_id)
    if not cat:
        flash("Gato não encontrado.", "warning")
        return redirect(url_for("admin_home"))
    if action == "approve":
        cat.status = "approved"
    elif action == "reject":
        cat.status = "rejected"
    else:
        flash("Ação inválida.", "danger")
        return redirect(url_for("admin_home"))
    db.session.commit()
    flash("Status atualizado.", "success")
    return redirect(url_for("admin_home"))

# ------------------------------------------------------------------------------
# Admin - Lista/ filtros / edição / exclusão de gatos
# ------------------------------------------------------------------------------
@app.route("/admin/cats")
@admin_required
def admin_cats():
    q = (request.args.get("q") or "").strip()
    status = (request.args.get("status") or "").strip()
    breed_id = (request.args.get("breed_id") or "").strip()
    owner_id = (request.args.get("owner_id") or "").strip()
    page = request.args.get("page", 1, type=int)

    query = (
        db.session.query(Cat)
        .options(joinedload(Cat.owner), joinedload(Cat.breed), joinedload(Cat.color))
        .order_by(Cat.created_at.desc())
    )

    if q:
        like = f"%{q}%"
        query = query.join(User, Cat.owner).filter(
            or_(
                Cat.name.ilike(like),
                Cat.microchip.ilike(like),
                Cat.registry_number.ilike(like),
                User.name.ilike(like),
            )
        )

    if status in {"pending", "approved", "rejected"}:
        query = query.filter(Cat.status == status)

    if breed_id.isdigit():
        query = query.filter(Cat.breed_id == int(breed_id))

    if owner_id.isdigit():
        query = query.filter(Cat.owner_id == int(owner_id))

    items, pagination = _paginate(query, page, per_page=20)

    rows = []
    for c in items:
        rows.append({
            "id": c.id,
            "name": c.name,
            "owner_name": c.owner.name if c.owner else "-",
            "breed_name": c.breed.name if c.breed else None,
            "color_name": c.color.name if c.color else None,
            "ems_code": c.color.ems_code if c.color else None,
            "dob": c.dob.isoformat() if c.dob else None,
            "status": c.status,
        })

    breeds = db.session.query(Breed).order_by(Breed.name.asc()).all()
    users  = db.session.query(User).order_by(User.name.asc()).all()

    return render_template(
        "admin_cats.html",
        cats=rows,
        q=q,
        status=status,
        breed_id=breed_id,
        owner_id=owner_id,
        breeds=breeds,
        users=users,
        pagination=pagination,
    )

@app.route("/admin/cats/<int:cat_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_cat_edit(cat_id):
    cat = db.session.get(Cat, cat_id)
    if not cat:
        flash("Gato não encontrado.", "warning")
        return redirect(url_for("admin_cats"))

    if request.method == "POST":
        cat.owner_id = request.form.get("owner_id", type=int)
        cat.name = (request.form.get("name") or "").strip()
        cat.dob  = _parse_date(request.form.get("dob"))
        cat.sex  = request.form.get("sex") or None
        cat.neutered = (request.form.get("neutered") == "SIM")
        cat.microchip = request.form.get("microchip") or None
        cat.status = request.form.get("status") or "pending"

        cat.breed_id = request.form.get("breed_id", type=int)
        cat.color_id = request.form.get("color_id", type=int)

        cat.registry_number = request.form.get("registry_number") or None
        cat.registry_entity = request.form.get("registry_entity") or None

        cat.breeder_type = request.form.get("breeder_type") or None
        cat.breeder_name = request.form.get("breeder_name") or None

        cat.sire_name = request.form.get("sire_name") or None
        cat.sire_breed_id = request.form.get("sire_breed_id", type=int)
        cat.sire_color_id = request.form.get("sire_color_id", type=int)
        cat.dam_name = request.form.get("dam_name") or None
        cat.dam_breed_id = request.form.get("dam_breed_id", type=int)
        cat.dam_color_id = request.form.get("dam_color_id", type=int)

        db.session.commit()
        flash("Gato atualizado com sucesso.", "success")
        return redirect(url_for("admin_cats"))

    breeds = db.session.query(Breed).order_by(Breed.name.asc()).all()
    users  = db.session.query(User).order_by(User.name.asc()).all()
    colors = []
    if cat.breed_id:
        colors = (
            db.session.query(Color)
            .filter(Color.breed_id == cat.breed_id)
            .order_by(Color.name.asc())
            .all()
        )

    return render_template(
        "admin_cat_form.html",
        cat=cat, breeds=breeds, users=users, colors=colors
    )

@app.route("/admin/cats/<int:cat_id>/delete", methods=["POST"])
@admin_required
def admin_cat_delete(cat_id):
    cat = db.session.get(Cat, cat_id)
    if not cat:
        flash("Gato não encontrado.", "warning")
        return redirect(url_for("admin_cats"))
    db.session.delete(cat)
    db.session.commit()
    flash("Gato excluído.", "success")
    return redirect(url_for("admin_cats"))

# ------------------------------------------------------------------------------
# Admin - Raças & Cores (CRUD + import CSV)
# ------------------------------------------------------------------------------
@app.route("/admin/breeds")
@admin_required
def admin_breeds():
    q = (request.args.get("q") or "").strip()
    query = db.session.query(Breed).order_by(Breed.name.asc())
    if q:
        like = f"%{q}%"
        query = query.filter(Breed.name.ilike(like))
    breeds = query.all()
    return render_template("admin_breeds.html", breeds=breeds, q=q)

@app.route("/admin/breeds/new", methods=["GET", "POST"])
@admin_required
def admin_breed_new():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        if not name:
            flash("Informe o nome da raça.", "warning")
            return render_template("admin_breed_form.html", mode="new", breed=None)
        if db.session.query(Breed).filter(func.lower(Breed.name)==name.lower()).first():
            flash("Essa raça já existe.", "warning")
            return render_template("admin_breed_form.html", mode="new", breed=None)
        b = Breed(name=name)
        db.session.add(b)
        db.session.commit()
        flash("Raça criada.", "success")
        return redirect(url_for("admin_breeds"))
    return render_template("admin_breed_form.html", mode="new", breed=None)

@app.route("/admin/breeds/<int:breed_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_breed_edit(breed_id):
    b = db.session.get(Breed, breed_id)
    if not b:
        flash("Raça não encontrada.", "warning")
        return redirect(url_for("admin_breeds"))
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        if not name:
            flash("Informe o nome da raça.", "warning")
            return render_template("admin_breed_form.html", mode="edit", breed=b)
        # evitar duplicata
        exists = (
            db.session.query(Breed)
            .filter(func.lower(Breed.name)==name.lower(), Breed.id != b.id)
            .first()
        )
        if exists:
            flash("Já existe uma raça com esse nome.", "warning")
            return render_template("admin_breed_form.html", mode="edit", breed=b)
        b.name = name
        db.session.commit()
        flash("Raça atualizada.", "success")
        return redirect(url_for("admin_breeds"))
    return render_template("admin_breed_form.html", mode="edit", breed=b)

@app.route("/admin/breeds/<int:breed_id>/delete", methods=["POST"])
@admin_required
def admin_breed_delete(breed_id):
    b = db.session.get(Breed, breed_id)
    if not b:
        flash("Raça não encontrada.", "warning")
        return redirect(url_for("admin_breeds"))
    # apaga também as cores vinculadas
    db.session.query(Color).filter(Color.breed_id == b.id).delete()
    db.session.delete(b)
    db.session.commit()
    flash("Raça excluída.", "success")
    return redirect(url_for("admin_breeds"))

@app.route("/admin/breeds/<int:breed_id>/colors")
@admin_required
def admin_colors(breed_id):
    b = db.session.get(Breed, breed_id)
    if not b:
        flash("Raça não encontrada.", "warning")
        return redirect(url_for("admin_breeds"))
    colors = (
        db.session.query(Color)
        .filter(Color.breed_id == b.id)
        .order_by(Color.name.asc())
        .all()
    )
    return render_template("admin_colors.html", breed=b, colors=colors)

@app.route("/admin/breeds/<int:breed_id>/colors/new", methods=["GET", "POST"])
@admin_required
def admin_color_new(breed_id):
    b = db.session.get(Breed, breed_id)
    if not b:
        flash("Raça não encontrada.", "warning")
        return redirect(url_for("admin_breeds"))
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        ems  = (request.form.get("ems_code") or "").strip()
        if not name or not ems:
            flash("Informe nome da cor e EMS.", "warning")
            return render_template("admin_color_form.html", mode="new", breed_id=b.id, color=None)
        c = Color(breed_id=b.id, name=name, ems_code=ems)
        db.session.add(c)
        db.session.commit()
        flash("Cor criada.", "success")
        return redirect(url_for("admin_colors", breed_id=b.id))
    return render_template("admin_color_form.html", mode="new", breed_id=b.id, color=None)

@app.route("/admin/colors/<int:color_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_color_edit(color_id):
    c = db.session.get(Color, color_id)
    if not c:
        flash("Cor não encontrada.", "warning")
        return redirect(url_for("admin_breeds"))
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        ems  = (request.form.get("ems_code") or "").strip()
        if not name or not ems:
            flash("Informe nome da cor e EMS.", "warning")
            return render_template("admin_color_form.html", mode="edit", breed_id=c.breed_id, color=c)
        c.name = name
        c.ems_code = ems
        db.session.commit()
        flash("Cor atualizada.", "success")
        return redirect(url_for("admin_colors", breed_id=c.breed_id))
    return render_template("admin_color_form.html", mode="edit", breed_id=c.breed_id, color=c)

@app.route("/admin/colors/<int:color_id>/delete", methods=["POST"])
@admin_required
def admin_color_delete(color_id):
    c = db.session.get(Color, color_id)
    if not c:
        flash("Cor não encontrada.", "warning")
        return redirect(url_for("admin_breeds"))
    breed_id = c.breed_id
    db.session.delete(c)
    db.session.commit()
    flash("Cor excluída.", "success")
    return redirect(url_for("admin_colors", breed_id=breed_id))

@app.route("/admin/colors/import", methods=["GET", "POST"])
@admin_required
def admin_colors_import():
    if request.method == "POST":
        f = request.files.get("file")
        if not f:
            flash("Envie um arquivo CSV.", "warning")
            return render_template("admin_colors_import.html")
        try:
            # CSV com cabeçalho: breed,color,ems
            # Atenção ao encoding: tente 'utf-8-sig' p/ arquivos do Excel
            stream = (f.stream.read()).decode("utf-8-sig").splitlines()
            reader = csv.DictReader(stream)
            add_count = 0
            for row in reader:
                breed_name = (row.get("breed") or "").strip()
                color_name = (row.get("color") or "").strip()
                ems_code   = (row.get("ems") or "").strip()
                if not breed_name or not color_name or not ems_code:
                    continue
                breed = db.session.query(Breed).filter(func.lower(Breed.name)==breed_name.lower()).first()
                if not breed:
                    breed = Breed(name=breed_name)
                    db.session.add(breed)
                    db.session.flush()
                color = Color(breed_id=breed.id, name=color_name, ems_code=ems_code)
                db.session.add(color)
                add_count += 1
            db.session.commit()
            flash(f"Importação concluída. {add_count} cores adicionadas.", "success")
            return redirect(url_for("admin_breeds"))
        except Exception as e:
            db.session.rollback()
            flash(f"Falha ao importar: {e}", "danger")
            return render_template("admin_colors_import.html")

    return render_template("admin_colors_import.html")

# ------------------------------------------------------------------------------
# Admin - Usuários (lista/busca/filtro/editar/excluir/reset)
# ------------------------------------------------------------------------------
@app.route("/admin/users")
@admin_required
def admin_users():
    q = (request.args.get("q") or "").strip()
    is_admin = request.args.get("is_admin", "")
    page = request.args.get("page", 1, type=int)

    query = db.session.query(User).order_by(User.created_at.desc())

    if q:
        like = f"%{q}%"
        query = query.filter(or_(User.name.ilike(like), User.email.ilike(like)))

    if is_admin == "1":
        query = query.filter(User.is_admin.is_(True))
    elif is_admin == "0":
        query = query.filter(User.is_admin.is_(False))

    items, pagination = _paginate(query, page, per_page=20)

    rows = [{
        "id": u.id,
        "name": u.name,
        "email": u.email,
        "is_admin": bool(u.is_admin),
        "created_at": u.created_at.strftime("%Y-%m-%d %H:%M") if u.created_at else "",
    } for u in items]

    return render_template(
        "admin_users.html",
        users=rows, q=q, is_admin=is_admin, pagination=pagination
    )

@app.route("/admin/users/<int:user_id>/edit", methods=["GET", "POST"])
@admin_required
def admin_user_edit(user_id):
    u = db.session.get(User, user_id)
    if not u:
        flash("Usuário não encontrado.", "warning")
        return redirect(url_for("admin_users"))

    if request.method == "POST":
        u.name = (request.form.get("name") or "").strip()
        u.dob  = _parse_date(request.form.get("dob"))
        u.sex  = request.form.get("sex") or None
        u.cpf  = request.form.get("cpf") or None
        u.email = (request.form.get("email") or "").strip().lower()
        u.phone = request.form.get("phone") or None
        u.address  = request.form.get("address") or None
        u.address2 = request.form.get("address2") or None
        u.district = request.form.get("district") or None
        u.city     = request.form.get("city") or None
        u.state    = request.form.get("state") or None
        u.zipcode  = request.form.get("zipcode") or None
        u.country  = request.form.get("country") or None
        u.is_admin = bool(request.form.get("is_admin"))

        db.session.commit()
        flash("Usuário atualizado com sucesso.", "success")
        return redirect(url_for("admin_users"))

    return render_template("admin_user_form.html", u=u)

@app.route("/admin/users/<int:user_id>/delete", methods=["POST"])
@admin_required
def admin_user_delete(user_id):
    if g.user and g.user.id == user_id:
        flash("Você não pode excluir a si mesmo enquanto está logado.", "warning")
        return redirect(url_for("admin_users"))
    u = db.session.get(User, user_id)
    if not u:
        flash("Usuário não encontrado.", "warning")
        return redirect(url_for("admin_users"))
    db.session.delete(u)
    db.session.commit()
    flash("Usuário excluído.", "success")
    return redirect(url_for("admin_users"))

@app.route("/admin/users/<int:user_id>/reset", methods=["POST"])
@admin_required
def admin_user_reset_password(user_id):
    u = db.session.get(User, user_id)
    if not u:
        flash("Usuário não encontrado.", "warning")
        return redirect(url_for("admin_users"))

    s = _reset_serializer()
    token = s.dumps({"uid": u.id, "email": u.email})

    if APP_BASE_URL:
        reset_url = f"{APP_BASE_URL}{url_for('reset_password', token=token)}"
    else:
        reset_url = url_for("reset_password", token=token, _external=True)

    flash(f"Link de reset de senha: {reset_url}", "info")
    return redirect(url_for("admin_users"))

# ------------------------------------------------------------------------------
# Reset de senha (público, via token)
# ------------------------------------------------------------------------------
@app.route("/reset/<token>", methods=["GET", "POST"])
def reset_password(token):
    s = _reset_serializer()
    try:
        data = s.loads(token, max_age=86400)  # 24h
    except SignatureExpired:
        flash("Link expirado. Gere um novo link de reset.", "warning")
        return redirect(url_for("login"))
    except BadSignature:
        flash("Link inválido.", "danger")
        return redirect(url_for("login"))

    u = db.session.get(User, data.get("uid"))
    if not u or (u.email or "").lower() != (data.get("email") or "").lower():
        flash("Link inválido para este usuário.", "danger")
        return redirect(url_for("login"))

    if request.method == "POST":
        p1 = request.form.get("password") or ""
        p2 = request.form.get("password2") or ""
        if len(p1) < 6:
            flash("A senha deve ter pelo menos 6 caracteres.", "warning")
            return render_template("reset_password.html")
        if p1 != p2:
            flash("As senhas não coincidem.", "warning")
            return render_template("reset_password.html")
        u.set_password(p1)
        db.session.commit()
        flash("Senha atualizada. Faça login.", "success")
        return redirect(url_for("login"))

    return render_template("reset_password.html")

# ------------------------------------------------------------------------------
# Inicialização do DB e admin padrão
# ------------------------------------------------------------------------------
def _ensure_default_admin():
    email = "admin@catclube.test"
    user = db.session.query(User).filter(func.lower(User.email)==email).first()
    if not user:
        user = User(
            name="Admin CatClube",
            email=email,
            is_admin=True,
            country="Brasil"
        )
        user.set_password("admin123")
        db.session.add(user)
        db.session.commit()
        print(f"[setup] Admin criado: {email} / admin123")

@app.cli.command("init-db")
def init_db_command():
    """Inicializa o banco e cria admin padrão."""
    db.create_all()
    _ensure_default_admin()
    print("Banco inicializado.")

# Execução local
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        _ensure_default_admin()
    app.run(host="0.0.0.0", port=5000, debug=True)
