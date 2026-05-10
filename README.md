# Credit Intelligence — Backend API

API de análise de carteiras de crédito com IA.

## Stack
- Python 3.11+
- FastAPI
- Pandas
- APIs: CNPJá (Receita Federal) + Datajud (CNJ)

## Endpoints

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | / | Health check |
| POST | /analisar | Upload de carteira (.xlsx) |
| GET | /status/{job_id} | Status do processamento |
| GET | /resultado/{job_id} | Download do Excel com scores |
| POST | /analisar-documento | Análise rápida de 1 CNPJ/CPF |
| GET | /jobs | Lista todos os jobs |

## Rodar Localmente

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

Acesse: http://localhost:8000/docs

## Deploy no Railway

1. Cria repositório no GitHub
2. Push do código
3. Conecta no Railway → New Project → Deploy from GitHub
4. Railway detecta o Procfile automaticamente
5. URL pública gerada em ~2 minutos

## Formato da Carteira (Excel)

| documento | valor_face | tipo_credito | meses_inadimplencia |
|-----------|-----------|--------------|-------------------|
| 33000167000101 | 150000 | empresarial | 18 |
| 12345678901 | 85000 | pessoal | 36 |
