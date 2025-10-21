def seed_all_fife_breeds():
    # Lista de RAÇAS conforme página oficial “Breeds” da FIFe (reconhecidas + preliminares).
    # Referência: FIFe Breeds page. Atualize aqui caso a FIFe altere a lista. 
    breeds = [
        # Categoria 1
        "Exotic", "Persian", "Ragdoll", "Sacred Birman", "Turkish Van",
        # Categoria 2
        "American Curl Longhair", "American Curl Shorthair", "LaPerm Longhair", "LaPerm Shorthair",
        "Maine Coon", "Neva Masquerade", "Norwegian Forest Cat", "Siberian", "Turkish Angora",
        # Categoria 3
        "Bengal", "British Longhair", "Burmilla", "British Shorthair", "Burmese", "Chartreux",
        "Cymric", "European", "Kurilean Bobtail Longhair", "Kurilean Bobtail Shorthair",
        "Korat", "Manx", "Egyptian Mau", "Ocicat", "Singapura", "Snowshoe",
        "Sokoke", "Selkirk Rex Longhair", "Selkirk Rex Shorthair",
        # Categoria 4
        "Abyssinian", "Balinese", "Cornish Rex", "Devon Rex", "Don Sphynx", "German Rex",
        "Japanese Bobtail Shorthair", "Oriental Longhair", "Oriental Shorthair",
        "Peterbald", "Russian Blue", "Siamese", "Somali", "Sphynx", "Thai",
        # Preliminares
        "Bombay", "Lykoi"
    ]

    with get_db() as db:
        for name in breeds:
            db.execute("INSERT OR IGNORE INTO breeds (name) VALUES (?)", (name,))
        db.commit()
