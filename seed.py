# Minimal seed for demo purposes
def seed():
    with get_db() as db:
        # Breeds (sample)
        breeds = ["Ragdoll", "Persian", "Maine Coon", "Sphynx", "Devon Rex", "Bengal", "British Shorthair", "Oriental Shorthair"]
        for b in breeds:
            db.execute("INSERT OR IGNORE INTO breeds (name) VALUES (?)", (b,))
        db.commit()

        # Colors & EMS (sample per breed)
        # NOTE: These EMS codes are illustrative examples. Adjust to your official tables later.
        color_sets = {
            "Ragdoll": [("Seal Point", "RAG n"), ("Blue Point", "RAG a"), ("Chocolate Point", "RAG b")],
            "Persian": [("Black", "PER n"), ("Blue", "PER a"), ("Red", "PER d")],
            "Maine Coon": [("Brown Tabby", "MCO n 22"), ("Blue Tabby", "MCO a 22")],
            "Sphynx": [("Black", "SPH n"), ("Blue", "SPH a")],
            "Devon Rex": [("Black", "DRX n"), ("Blue", "DRX a")],
            "Bengal": [("Brown Spotted", "BEN n 24"), ("Snow Lynx", "BEN n 33")],
            "British Shorthair": [("Blue", "BSH a"), ("Lilac", "BSH c")],
            "Oriental Shorthair": [("Black", "OSH n"), ("Chestnut", "OSH b")]
        }

        rows = db.execute("SELECT id, name FROM breeds").fetchall()
        name_to_id = {r["name"]: r["id"] for r in rows}
        for breed_name, colors in color_sets.items():
            bid = name_to_id[breed_name]
            for cname, ems in colors:
                db.execute("INSERT OR IGNORE INTO colors (breed_id, name, ems_code) VALUES (?, ?, ?)", (bid, cname, ems))
        db.commit()

        # Create a demo admin if none exists
        admin = db.execute("SELECT id FROM users WHERE email = 'admin@riocatclub.test'").fetchone()
        if not admin:
            from werkzeug.security import generate_password_hash
            db.execute("""
                INSERT INTO users (name, email, password_hash, is_admin)
                VALUES (?, ?, ?, 1)
            """, ("Admin Demo", "admin@riocatclub.test", generate_password_hash("admin123")))
            db.commit()

seed()
