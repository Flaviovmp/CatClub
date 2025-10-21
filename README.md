# Sistema Clube de Gatos (Flask + SQLite)

Projeto simples para cadastro de associados e registro de gatos com fluxo de aprovação do administrador.

## Rodar localmente
1. Instale Python 3.10+
2. Em um terminal, dentro da pasta do projeto, crie um ambiente virtual:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   python app.py
   ```
3. Acesse http://localhost:5000
4. Admin demo: `admin@riocatclub.test` / senha `admin123` (altere depois).

## Implantar online (Render.com - grátis)
1. Crie uma conta em https://render.com e conecte seu GitHub.
2. Faça o upload do projeto para um repositório no GitHub.
3. Em Render, crie um **Web Service**:
   - Runtime: *Python*
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python app.py`
   - Add Environment Variable: `SECRET_KEY` com um valor aleatório longo.
4. Deploy e abra a URL pública.

> Alternativas: Railway.app ou Replit também funcionam com o mesmo comando `python app.py`.

## Notas
- A tabela `colors` guarda a relação Raça → Cor → EMS (um EMS por cor). As listas são exemplos e devem ser substituídas pela tabela oficial do clube quando disponível.
- O endpoint `/api/colors?breed_id=ID` alimenta os combos de cores dinamicamente.
- Fluxo de aprovação: os gatos ficam `pending` até o admin aprovar/rejeitar em `/admin`.
- Para promover seu usuário a admin, use o formulário na página inicial (apenas para testes).


### Validações adicionadas
- **CPF**: validação de dígitos verificadores (aceita com ou sem máscara).
- **CEP**: aceita `00000-000` ou `00000000`.
- **UF**: seleção por dropdown com as 27 UFs brasileiras.
