def seed_all_fife_breeds():
    # Lista oficial FIFe (out/2025): Categorias 1–4 (reconhecidas) + preliminares (BOM, LYO).
    # Referência: https://fifeweb.org/cats/breeds/ (FIFe Breeds page)
    category_1 = [
        "Exotic",
        "Persian",
        "Ragdoll",
        "Sacred Birman",
        "Turkish Van",
    ]
    category_2 = [
        "American Curl Longhair",
        "American Curl Shorthair",
        "LaPerm Longhair",
        "LaPerm Shorthair",
        "Maine Coon",
        "Neva Masquerade",
        "Norwegian Forest Cat",
        "Siberian",
        "Turkish Angora",
    ]
    category_3 = [
        "Bengal",
        "British Longhair",
        "Burmilla",
        "British Shorthair",
        "Burmese",
        "Chartreux",
        "Cymric",
        "European",
        "Kurilean Bobtail Longhair",
        "Kurilean Bobtail Shorthair",
        "Korat",
        "Manx",
        "Egyptian Mau",
        "Ocicat",
        "Singapura",
        "Snowshoe",
        "Sokoke",
        "Selkirk Rex Longhair",
        "Selkirk Rex Shorthair",
    ]
    category_4 = [
        "Abyssinian",
        "Balinese",
        "Cornish Rex",
        "Devon Rex",
        "Don Sphynx",
        "German Rex",
        "Japanese Bobtail Shorthair",
        "Oriental Longhair",
        "Oriental Shorthair",
        "Peterbald",
        "Russian Blue",
        "Siamese",
        "Somali",
        "Sphynx",
        "Thai",
    ]
    preliminary = [
        "Bombay",  # BOM – preliminar (categoria 3)
        "Lykoi",   # LYO – preliminar (categoria 4)
    ]

    all_breeds = (
        category_1
        + category_2
        + category_3
        + category_4
        + preliminary  # inclua preliminares se quiser permitir cadastro desde já
    )

    with get_db() as db:
        for name in all_breeds:
            db.execute("INSERT OR IGNORE INTO breeds (name) VALUES (?)", (name,))
        db.commit()

# >>> Chame esta função dentro do seu seed() principal, por exemplo:
# def seed():
#     ...
#     seed_all_fife_breeds()
#     ...



def seed_colors_examples(get_db):
    samples = {
        "Ragdoll": [("Seal Point","RAG n"),("Blue Point","RAG a"),("Chocolate Point","RAG b"),("Lilac Point","RAG c")],
        "Persian": [("Black","PER n"),("Blue","PER a"),("Red","PER d"),("Chinchilla Silver","PER ns 12")],
        "Maine Coon": [("Brown Classic Tabby","MCO n 22"),("Blue Mackerel Tabby","MCO a 23"),("Black","MCO n")],
        "British Shorthair": [("Blue","BSH a"),("Black Silver Tabby","BSH ns 22"),("Golden Shaded","BSH ny 11")]
    }
    with get_db() as db:
        rows = db.execute("SELECT id, name FROM breeds").fetchall()
        bid = {r["name"]: r["id"] for r in rows}
        for breed, items in samples.items():
            if breed not in bid: 
                continue
            for cname, ems in items:
                db.execute("INSERT OR IGNORE INTO colors (breed_id, name, ems_code) VALUES (?, ?, ?)", (bid[breed], cname, ems))
        db.commit()

def seed_admin(get_db):
    with get_db() as db:
        admin = db.execute("SELECT id FROM users WHERE email = 'admin@catclube.test'").fetchone()
        if not admin:
            from werkzeug.security import generate_password_hash
            db.execute("""
                INSERT INTO users (name, email, password_hash, is_admin)
                VALUES (?, ?, ?, 1)
            """, ("Admin Demo", "admin@catclube.test", generate_password_hash("admin123")))
            db.commit()

def seed(get_db):
    seed_all_fife_breeds(get_db)
    seed_colors_examples(get_db)
    seed_admin(get_db)

seed(get_db)
