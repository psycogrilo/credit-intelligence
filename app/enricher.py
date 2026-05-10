import requests
import pandas as pd
import time
import json
import re
from datetime import datetime

CNJ_API_KEY = "APIKey cDZHYzlZa0JadVREZDJCendQbXY6SkJlTzNjLV9TRENyQk1RdnFKZGRQdw=="
CNJ_BASE_URL = "https://api-publica.datajud.cnj.jus.br"
CNPJA_BASE_URL = "https://open.cnpja.com/office"

CNJ_TRIBUNAIS = [
    "api_publica_tjmg", "api_publica_tjsp", "api_publica_tjrj",
    "api_publica_tjrs", "api_publica_tjpr", "api_publica_tjba",
    "api_publica_trf1", "api_publica_trf3",
]

def limpar_cnpj(cnpj) -> str:
    if pd.isna(cnpj): return ""
    raw = str(cnpj).strip()
    if 'e' in raw.lower() or ('.' in raw and 'e' in raw.lower()):
        try: raw = str(int(float(raw)))
        except: pass
    return re.sub(r'\D', '', raw).zfill(14)

def detectar_tipo(documento) -> str:
    raw = str(documento).strip()
    if 'e' in raw.lower():
        try: raw = str(int(float(raw)))
        except: pass
    doc = re.sub(r'\D', '', raw)
    if len(doc) == 11: return "CPF"
    if len(doc) == 14: return "CNPJ"
    return "DESCONHECIDO"

def consultar_cnpj(cnpj: str) -> dict:
    cnpj_limpo = limpar_cnpj(cnpj)
    if not cnpj_limpo or len(cnpj_limpo) != 14:
        return {"erro": "CNPJ inválido", "cnpj": cnpj}
    try:
        r = requests.get(f"{CNPJA_BASE_URL}/{cnpj_limpo}", timeout=15)
        if r.status_code == 200:
            d = r.json()
            return {
                "cnpj": cnpj_limpo, "tipo_doc": "CNPJ",
                "razao_social": d.get("company", {}).get("name", ""),
                "nome_fantasia": d.get("alias", ""),
                "situacao_cadastral": d.get("status", {}).get("text", ""),
                "situacao_ativa": str(d.get("status", {}).get("id", "")).upper() in ["ACTIVE","ATIVA","2","02"],
                "data_abertura": d.get("founded", ""),
                "natureza_juridica": d.get("company", {}).get("nature", {}).get("text", ""),
                "porte": d.get("company", {}).get("size", {}).get("text", ""),
                "capital_social": d.get("company", {}).get("equity", 0),
                "cnae_principal": d.get("mainActivity", {}).get("text", "") if d.get("mainActivity") else "",
                "municipio": d.get("address", {}).get("municipality", ""),
                "uf": d.get("address", {}).get("state", ""),
                "qtd_socios": len(d.get("company", {}).get("members", [])),
                "socios": [m.get("person", {}).get("name", "") for m in d.get("company", {}).get("members", [])[:3]],
                "simples_nacional": d.get("company", {}).get("simples", {}).get("optant", False) if d.get("company", {}).get("simples") else False,
                "fonte_cnpj": "CNPJá/ReceitaFederal",
                "data_consulta": datetime.now().strftime("%Y-%m-%d"),
            }
        elif r.status_code == 429:
            time.sleep(60)
            return consultar_cnpj(cnpj)
        else:
            return {"cnpj": cnpj_limpo, "tipo_doc": "CNPJ", "erro": f"HTTP {r.status_code}"}
    except Exception as e:
        return {"cnpj": cnpj_limpo, "tipo_doc": "CNPJ", "erro": str(e)}

def consultar_cpf(cpf: str) -> dict:
    return {
        "cnpj": re.sub(r'\D','',str(cpf)), "tipo_doc": "CPF",
        "razao_social": "", "situacao_cadastral": "CPF - API paga necessária",
        "situacao_ativa": None, "capital_social": 0, "qtd_socios": 0,
        "fonte_cnpj": "N/A", "data_consulta": datetime.now().strftime("%Y-%m-%d"),
    }

def buscar_processos_cnj(documento: str) -> dict:
    doc = re.sub(r'\D','',str(documento))
    headers = {"Authorization": CNJ_API_KEY, "Content-Type": "application/json"}
    query = {
        "query": {"bool": {"should": [
            {"match": {"partes.documento": doc}},
            {"match": {"partes.numeroDocumento": doc}}
        ], "minimum_should_match": 1}},
        "_source": ["numeroProcesso","classe.nome","dataAjuizamento"],
        "size": 10
    }
    total = 0
    tribunais = []
    processos = []
    for tribunal in CNJ_TRIBUNAIS:
        try:
            r = requests.post(f"{CNJ_BASE_URL}/{tribunal}/_search", headers=headers, json=query, timeout=10)
            if r.status_code == 200:
                hits = r.json().get("hits", {})
                t = hits.get("total", {}).get("value", 0)
                if t > 0:
                    total += t
                    tribunais.append(tribunal.replace("api_publica_","").upper())
                    for hit in hits.get("hits", [])[:2]:
                        s = hit.get("_source", {})
                        processos.append({
                            "numero": s.get("numeroProcesso",""),
                            "classe": s.get("classe",{}).get("nome",""),
                            "tribunal": tribunal.replace("api_publica_","").upper()
                        })
            time.sleep(0.2)
        except:
            continue
    risco = "BAIXO" if total == 0 else ("MÉDIO" if total <= 3 else "ALTO")
    return {
        "total_processos": total,
        "tribunais_com_processo": ", ".join(tribunais),
        "risco_processual": risco,
        "processos_detalhes": json.dumps(processos[:5], ensure_ascii=False),
        "fonte_cnj": "Datajud/CNJ",
    }

def calcular_score(row: dict) -> dict:
    score = 0
    detalhes = []

    if row.get("situacao_ativa") == True:
        score += 250; detalhes.append("Empresa ativa: +250")
    elif str(row.get("situacao_cadastral","")).upper() in ["SUSPENSA","INAPTA"]:
        score += 80; detalhes.append("Suspensa/inapta: +80")
    else:
        detalhes.append("Baixada/inativa: +0")

    t = int(row.get("total_processos", 0) or 0)
    if t == 0: score += 200; detalhes.append("Sem processos: +200")
    elif t <= 2: score += 130; detalhes.append(f"{t} processo(s): +130")
    elif t <= 5: score += 70; detalhes.append(f"{t} processos: +70")
    else: score += 20; detalhes.append(f"{t}+ processos: +20")

    try: meses = int(row.get("meses_inadimplencia", 0) or 0)
    except: meses = 0
    if meses <= 6: score += 200; detalhes.append(f"Recente ({meses}m): +200")
    elif meses <= 12: score += 150; detalhes.append(f"{meses}m: +150")
    elif meses <= 24: score += 90; detalhes.append(f"{meses}m: +90")
    elif meses <= 48: score += 40; detalhes.append(f"{meses}m: +40")
    else: score += 10; detalhes.append(f"Longa ({meses}m): +10")

    tipo = str(row.get("tipo_credito","")).upper()
    if "CONSIGNADO" in tipo: score += 150; detalhes.append("Consignado: +150")
    elif "GARANTIA" in tipo: score += 130; detalhes.append("Com garantia: +130")
    elif any(x in tipo for x in ["EMPRESARIAL","PJ"]): score += 90; detalhes.append("Empresarial: +90")
    elif any(x in tipo for x in ["PESSOAL","PF"]): score += 70; detalhes.append("Pessoal: +70")
    else: score += 50; detalhes.append("Tipo N/A: +50")

    try: capital = float(row.get("capital_social", 0) or 0)
    except: capital = 0
    if capital >= 1_000_000: score += 100; detalhes.append("Capital alto: +100")
    elif capital >= 100_000: score += 70; detalhes.append("Capital médio: +70")
    elif capital >= 10_000: score += 40; detalhes.append("Capital baixo: +40")
    else: score += 10; detalhes.append("Capital mínimo: +10")

    try: socios = int(row.get("qtd_socios", 0) or 0)
    except: socios = 0
    if socios >= 2: score += 100; detalhes.append("Múltiplos sócios: +100")
    elif socios == 1: score += 60; detalhes.append("1 sócio: +60")
    else: score += 20; detalhes.append("Sem sócios: +20")

    if score >= 700: cls, rec = "ALTO", "PRIORIDADE"
    elif score >= 450: cls, rec = "MÉDIO", "MONITORAR"
    else: cls, rec = "BAIXO", "RISCO ALTO"

    return {
        "score_recuperacao": score,
        "classificacao_score": cls,
        "recomendacao": rec,
        "taxa_recuperacao_estimada_pct": round((score / 1000) * 35, 1),
        "detalhes_score": " | ".join(detalhes),
    }

def processar_linha(row: dict) -> dict:
    documento = str(row.get("documento", ""))
    tipo = detectar_tipo(documento)
    resultado = dict(row)
    if tipo == "CNPJ":
        resultado.update(consultar_cnpj(documento))
        time.sleep(12)
    else:
        resultado.update(consultar_cpf(documento))
    resultado.update(buscar_processos_cnj(documento))
    resultado.update(calcular_score(resultado))
    return resultado
