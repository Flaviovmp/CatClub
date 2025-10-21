# Sistema Clube de Gatos (Flask + SQLite) — Admin UI melhorada

- Navbar mostra **Painel Admin** quando `is_admin = 1`.
- Banner “**Modo Administrador**” com botão para `/admin` quando admin logado.
- Botão “**Ir para o Painel Admin**” no dashboard para admins.
- Validações: **CPF**, **CEP** e dropdown de **UF**.

## Rodar localmente
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```
Acesse: http://localhost:5000

Admin demo: `admin@riocatclub.test` / senha `admin123`

## Deploy no Render
- Build: `pip install -r requirements.txt`
- Start: `python app.py`
- Env: `SECRET_KEY` com valor longo. O app usa `PORT` automaticamente.
```
