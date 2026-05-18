from fastapi import FastAPI, UploadFile, File, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
import pandas as pd
import uuid
import os
import json
from datetime import datetime
from app.enricher import processar_linha, detectar_tipo
from app.report_generator import gerar_relatorio_html

app = FastAPI(
    title="Credit Intelligence API",
    description="Análise de carteiras de crédito com IA",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Armazena status dos jobs em memória
# Em produção: usar Redis ou banco de dados
jobs = {}

# ── API KEY ──
import secrets
API_KEY = "ci-2026-ricardo-secret-key"  # Troque por uma chave sua

def verificar_api_key(x_api_key: str = None):
    from fastapi import Header
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="API Key inválida ou ausente")
    return x_api_key

UPLOAD_DIR = "uploads"
OUTPUT_DIR = "outputs"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ─────────────────────────────────────────────
# HEALTH CHECK
# ─────────────────────────────────────────────

@app.get("/")
def root():
    return {
        "status": "online",
        "sistema": "Credit Intelligence API",
        "versao": "1.0.0",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/health")
def health():
    return {"status": "ok"}


# ─────────────────────────────────────────────
# ANÁLISE DE CARTEIRA — UPLOAD
# ─────────────────────────────────────────────

@app.post("/analisar")
async def analisar_carteira(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    x_api_key: str = None
):
    verificar_api_key(x_api_key)
    """
    Recebe um arquivo Excel (.xlsx) com a carteira.
    Colunas esperadas: documento, valor_face, tipo_credito, meses_inadimplencia
    Retorna um job_id para acompanhar o processamento.
    """
    # Valida extensão
    if not file.filename.endswith((".xlsx", ".xls", ".csv")):
        raise HTTPException(400, "Formato inválido. Use .xlsx, .xls ou .csv")

    # Gera ID único para este job
    job_id = str(uuid.uuid4())[:8]

    # Salva arquivo
    caminho = f"{UPLOAD_DIR}/{job_id}_{file.filename}"
    content = await file.read()
    with open(caminho, "wb") as f:
        f.write(content)

    # Registra job
    jobs[job_id] = {
        "id": job_id,
        "status": "processando",
        "arquivo": file.filename,
        "criado_em": datetime.now().isoformat(),
        "total": 0,
        "processados": 0,
        "resultado_path": None,
        "sumario": None,
        "erro": None,
    }

    # Processa em background para não bloquear a resposta
    background_tasks.add_task(processar_carteira_job, job_id, caminho)

    return {
        "job_id": job_id,
        "status": "processando",
        "mensagem": "Carteira recebida. Use GET /status/{job_id} para acompanhar.",
        "status_url": f"/status/{job_id}"
    }


# ─────────────────────────────────────────────
# STATUS DO JOB
# ─────────────────────────────────────────────

@app.get("/status/{job_id}")
def status_job(job_id: str):
    """Retorna o status atual do processamento."""
    if job_id not in jobs:
        raise HTTPException(404, "Job não encontrado")

    job = jobs[job_id]
    resposta = {
        "job_id": job_id,
        "status": job["status"],
        "arquivo": job["arquivo"],
        "criado_em": job["criado_em"],
        "progresso": f"{job['processados']}/{job['total']}",
    }

    if job["status"] == "concluido":
        resposta["sumario"] = job["sumario"]
        resposta["download_url"] = f"/resultado/{job_id}"

    if job["status"] == "erro":
        resposta["erro"] = job["erro"]

    return resposta


# ─────────────────────────────────────────────
# DOWNLOAD DO RESULTADO
# ─────────────────────────────────────────────

@app.get("/resultado/{job_id}")
def download_resultado(job_id: str):
    """Baixa o Excel com a carteira enriquecida e os scores."""
    if job_id not in jobs:
        raise HTTPException(404, "Job não encontrado")

    job = jobs[job_id]
    if job["status"] != "concluido":
        raise HTTPException(400, f"Processamento ainda não concluído. Status: {job['status']}")

    path = job["resultado_path"]
    if not path or not os.path.exists(path):
        raise HTTPException(404, "Arquivo de resultado não encontrado")

    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"resultado_{job_id}.xlsx"
    )


# ─────────────────────────────────────────────
# ANÁLISE RÁPIDA — 1 CNPJ/CPF
# ─────────────────────────────────────────────

@app.post("/analisar-documento")
def analisar_documento(body: dict, x_api_key: str = None):
    verificar_api_key(x_api_key)
    """
    Analisa um único CPF ou CNPJ.
    Body: { "documento": "33000167000101", "valor_face": 150000,
            "tipo_credito": "empresarial", "meses_inadimplencia": 18 }
    """
    documento = body.get("documento", "")
    if not documento:
        raise HTTPException(400, "Campo 'documento' é obrigatório")

    resultado = processar_linha({
        "documento": documento,
        "valor_face": body.get("valor_face", 0),
        "tipo_credito": body.get("tipo_credito", "empresarial"),
        "meses_inadimplencia": body.get("meses_inadimplencia", 12),
    })

    return resultado


# ─────────────────────────────────────────────
# LISTA DE JOBS
# ─────────────────────────────────────────────

@app.get("/jobs")
def listar_jobs():
    """Lista todos os jobs processados nesta sessão."""
    return {
        "total": len(jobs),
        "jobs": [
            {
                "job_id": jid,
                "status": j["status"],
                "arquivo": j["arquivo"],
                "criado_em": j["criado_em"],
                "progresso": f"{j['processados']}/{j['total']}"
            }
            for jid, j in sorted(jobs.items(), key=lambda x: x[1]["criado_em"], reverse=True)
        ]
    }




@app.get("/relatorio/{job_id}")
def relatorio_html(job_id: str, cliente: str = ""):
    from fastapi.responses import HTMLResponse
    if job_id not in jobs:
        raise HTTPException(404, "Job não encontrado")
    job = jobs[job_id]
    if job["status"] != "concluido":
        raise HTTPException(400, f"Status: {job['status']}")
    path = job["resultado_path"]
    if not path or not os.path.exists(path):
        raise HTTPException(404, "Arquivo não encontrado")
    df = pd.read_excel(path)
    html = gerar_relatorio_html(df, job_id, cliente)
    return HTMLResponse(content=html, status_code=200)

# ─────────────────────────────────────────────
# PROCESSAMENTO EM BACKGROUND
# ─────────────────────────────────────────────

def processar_carteira_job(job_id: str, caminho_arquivo: str):
    """Roda o enriquecimento em background e atualiza o job."""
    try:
        # Carrega arquivo
        if caminho_arquivo.endswith(".csv"):
            df = pd.read_csv(caminho_arquivo)
        else:
            df = pd.read_excel(caminho_arquivo)

        jobs[job_id]["total"] = len(df)

        # Valida colunas
        if "documento" not in df.columns:
            jobs[job_id]["status"] = "erro"
            jobs[job_id]["erro"] = "Coluna 'documento' não encontrada no arquivo"
            return

        # Processa linha a linha
        resultados = []
        for i, row in df.iterrows():
            resultado = processar_linha(row.to_dict())
            resultados.append(resultado)
            jobs[job_id]["processados"] = i + 1

        # Monta DataFrame e salva
        df_resultado = pd.DataFrame(resultados)
        if "score_recuperacao" in df_resultado.columns:
            df_resultado = df_resultado.sort_values("score_recuperacao", ascending=False)

        output_path = f"{OUTPUT_DIR}/resultado_{job_id}.xlsx"
        df_resultado.to_excel(output_path, index=False)

        # Calcula sumário
        total = len(df_resultado)
        sumario = {
            "total_devedores": total,
            "valor_total": float(df_resultado["valor_face"].sum()) if "valor_face" in df_resultado.columns else 0,
            "score_medio": round(float(df_resultado["score_recuperacao"].mean()), 0) if "score_recuperacao" in df_resultado.columns else 0,
            "taxa_recuperacao_media": round(float(df_resultado["taxa_recuperacao_estimada_pct"].mean()), 1) if "taxa_recuperacao_estimada_pct" in df_resultado.columns else 0,
            "prioridade": int(len(df_resultado[df_resultado["recomendacao"] == "PRIORIDADE"])) if "recomendacao" in df_resultado.columns else 0,
            "monitorar": int(len(df_resultado[df_resultado["recomendacao"] == "MONITORAR"])) if "recomendacao" in df_resultado.columns else 0,
            "risco_alto": int(len(df_resultado[df_resultado["recomendacao"] == "RISCO ALTO"])) if "recomendacao" in df_resultado.columns else 0,
        }
        sumario["recuperacao_estimada"] = round(sumario["valor_total"] * sumario["taxa_recuperacao_media"] / 100, 2)

        jobs[job_id]["status"] = "concluido"
        jobs[job_id]["resultado_path"] = output_path
        jobs[job_id]["sumario"] = sumario
        jobs[job_id]["processados"] = total

    except Exception as e:
        jobs[job_id]["status"] = "erro"
        jobs[job_id]["erro"] = str(e)
