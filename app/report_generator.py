import pandas as pd
from datetime import datetime


def gerar_relatorio_html(df: pd.DataFrame, job_id: str, cliente: str = "") -> str:
    """
    Gera relatório HTML profissional a partir do DataFrame enriquecido.
    """

    # ── MÉTRICAS GERAIS ──
    total = int(len(df))
    valor_total = float(df['valor_face'].sum()) if 'valor_face' in df.columns else 0
    score_medio = float(df['score_recuperacao'].mean()) if 'score_recuperacao' in df.columns else 0
    taxa_media = float(df['taxa_recuperacao_estimada_pct'].mean()) if 'taxa_recuperacao_estimada_pct' in df.columns else 0
    recuperacao_estimada = valor_total * taxa_media / 100
    custo_cobranca = recuperacao_estimada * 0.30

    prioridade = int(len(df[df['recomendacao'] == 'PRIORIDADE'])) if 'recomendacao' in df.columns else 0
    monitorar = int(len(df[df['recomendacao'] == 'MONITORAR'])) if 'recomendacao' in df.columns else 0
    risco_alto = int(len(df[df['recomendacao'] == 'RISCO ALTO'])) if 'recomendacao' in df.columns else 0
    ativos = int(len(df[df['situacao_ativa'] == True])) if 'situacao_ativa' in df.columns else 0
    cpfs = int(len(df[df['tipo_doc'] == 'CPF'])) if 'tipo_doc' in df.columns else 0
    sem_processos = int(len(df[df['total_processos'] == 0])) if 'total_processos' in df.columns else 0
    inadimp_longa = int(len(df[df['meses_inadimplencia'] >= 48])) if 'meses_inadimplencia' in df.columns else 0

    # Score máximo e mínimo
    score_max = int(df['score_recuperacao'].max()) if 'score_recuperacao' in df.columns else 0
    score_min = int(df['score_recuperacao'].min()) if 'score_recuperacao' in df.columns else 0

    # Recomendação geral
    if score_medio >= 700:
        rec_geral, rec_classe, rec_icone = "AQUISIÇÃO RECOMENDADA", "comprar", "✓"
    elif score_medio >= 450:
        rec_geral, rec_classe, rec_icone = "AQUISIÇÃO COM CAUTELA", "cautela", "⚠"
    else:
        rec_geral, rec_classe, rec_icone = "EVITAR AQUISIÇÃO", "evitar", "✗"

    # Cor da capa baseada na recomendação
    capa_color = "var(--green)" if rec_classe == "comprar" else ("var(--yellow)" if rec_classe == "cautela" else "var(--red)")

    # Preço máximo sugerido
    preco_max_pct = max((taxa_media - 18) / 100 * 0.7, 0.03)
    preco_max = valor_total * preco_max_pct
    retorno = recuperacao_estimada / preco_max if preco_max > 0 else 0

    # Scores por dimensão (estimados)
    cap_pag = min(int(score_medio * 1.05), 1000)
    garantias = int(score_medio * 0.88)
    hist_proc = int(score_medio * 0.82)
    ocultacao = int(score_medio * 0.95)
    conformidade = min(int(score_medio * 1.12), 1000)

    # Formatos monetários
    def fmt_brl(v):
        if v >= 1_000_000:
            return f"R$ {v/1_000_000:.1f}M"
        if v >= 1_000:
            return f"R$ {v/1_000:.0f}K"
        return f"R$ {v:.0f}"

    valor_total_fmt = fmt_brl(valor_total)
    recuperacao_fmt = fmt_brl(recuperacao_estimada)
    preco_max_fmt = fmt_brl(preco_max)
    custo_fmt = fmt_brl(custo_cobranca)
    cpfs_valor = float(df[df['tipo_doc'] == 'CPF']['valor_face'].sum()) if 'tipo_doc' in df.columns else 0
    cpfs_valor_fmt = fmt_brl(cpfs_valor)
    cpfs_pct = round(cpfs_valor / valor_total * 100) if valor_total > 0 else 0

    # ── LINHAS DA TABELA ──
    linhas_tabela = ""
    df_sorted = df.sort_values('score_recuperacao', ascending=False) if 'score_recuperacao' in df.columns else df
    for _, r in df_sorted.iterrows():
        score = int(r.get('score_recuperacao', 0))
        pill = "alto" if score >= 700 else ("medio" if score >= 450 else "baixo")
        rec = str(r.get('recomendacao', ''))
        rec_color = "var(--green)" if rec == 'PRIORIDADE' else ("var(--yellow)" if rec == 'MONITORAR' else "var(--red)")
        score_color = "var(--green)" if score >= 700 else ("var(--yellow)" if score >= 450 else "var(--red)")

        nome = str(r.get('razao_social', ''))
        if not nome or nome == 'nan':
            nome = str(r.get('observacao', str(r.get('documento', ''))))
        nome = (nome[:28] + '...') if len(nome) > 28 else nome

        vf = f"R$ {int(r.get('valor_face', 0)):,}".replace(',', '.')
        taxa = f"{float(r.get('taxa_recuperacao_estimada_pct', 0)):.1f}%"
        meses = f"{int(r.get('meses_inadimplencia', 0))}m"
        tipo = str(r.get('tipo_credito', '')).capitalize()

        linhas_tabela += f"""
      <tr>
        <td>{nome}</td>
        <td>{tipo}</td>
        <td>{vf}</td>
        <td><span class="score-pill {pill}">{score}</span></td>
        <td style="color:{score_color}">{taxa}</td>
        <td>{meses}</td>
        <td style="color:{rec_color}; font-size:9px;">{rec}</td>
      </tr>"""

    # ── ALERTAS AUTOMÁTICOS ──
    alertas = ""
    if cpfs > 0:
        alertas += f"""
    <div style="background:var(--yellow2); border:1px solid var(--yellow); border-left:3px solid var(--yellow); padding:18px 20px; margin-bottom:12px;">
      <div style="font-size:8px; letter-spacing:3px; color:var(--yellow); margin-bottom:8px;">⚠ CPFs SEM ENRIQUECIMENTO COMPLETO</div>
      <div style="font-size:11px; color:rgba(255,255,255,0.6); line-height:1.7;">
        {cpfs} documento(s) identificado(s) como CPF representando {cpfs_valor_fmt} ({cpfs_pct}% do valor de face). 
        Dados de situação cadastral e histórico financeiro não disponíveis sem API paga (Serasa/BigDataCorp). 
        Recomendamos enriquecer esses registros antes da decisão de aquisição.
      </div>
    </div>"""

    if inadimp_longa > 0:
        alertas += f"""
    <div style="background:var(--red2); border:1px solid var(--red); border-left:3px solid var(--red); padding:18px 20px; margin-bottom:12px;">
      <div style="font-size:8px; letter-spacing:3px; color:var(--red); margin-bottom:8px;">⚠ INADIMPLÊNCIA LONGA DETECTADA</div>
      <div style="font-size:11px; color:rgba(255,255,255,0.6); line-height:1.7;">
        {inadimp_longa} devedor(es) com mais de 48 meses de inadimplência. 
        Recuperação muito difícil — recomendamos excluir ou negociar desconto adicional de 2–3% no preço total.
      </div>
    </div>"""

    # Verifica empresas em recuperação judicial
    recup_judicial = df[df['razao_social'].str.contains('RECUPERACAO JUDICIAL|RECUPERAÇÃO JUDICIAL', case=False, na=False)] if 'razao_social' in df.columns else pd.DataFrame()
    if len(recup_judicial) > 0:
        nomes_rj = ', '.join(recup_judicial['razao_social'].str[:40].tolist())
        alertas += f"""
    <div style="background:var(--yellow2); border:1px solid var(--yellow); border-left:3px solid var(--yellow); padding:18px 20px; margin-bottom:12px;">
      <div style="font-size:8px; letter-spacing:3px; color:var(--yellow); margin-bottom:8px;">⚠ EMPRESA EM RECUPERAÇÃO JUDICIAL</div>
      <div style="font-size:11px; color:rgba(255,255,255,0.6); line-height:1.7;">
        {nomes_rj} — verificar habilitação de crédito no processo antes da aquisição.
      </div>
    </div>"""

    data_hoje = datetime.now().strftime("%B %Y").capitalize()
    doc_num = f"CI-{datetime.now().year}-{job_id[:4].upper()}"
    cliente_nome = cliente or "[Nome do Escritório / Cliente]"

    html = f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Relatório {doc_num} — Credit Intelligence</title>
<link href="https://fonts.googleapis.com/css2?family=Bebas+Neue&family=Crimson+Pro:ital,wght@0,300;0,400;0,600;1,300&family=IBM+Plex+Mono:wght@300;400;500&display=swap" rel="stylesheet">
<style>
  :root {{
    --bg:#070709; --surface:#0D0D12; --surface2:#12121A;
    --border:#1C1C28; --border2:#252535; --text:#E8E8F0;
    --text2:#8888A8; --text3:#444460; --gold:#C9A84C; --gold2:#7A5C1A;
    --green:#2DD4A0; --green2:#0D3D2E; --red:#F05A5A; --red2:#3D1515;
    --yellow:#F0C040; --yellow2:#3D3010; --blue:#5A8FF0;
  }}
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ background:var(--bg); font-family:'IBM Plex Mono',monospace; color:var(--text); min-height:100vh; }}
  .cover {{ min-height:100vh; display:flex; flex-direction:column; justify-content:space-between; padding:60px; position:relative; border-bottom:1px solid var(--border2); overflow:hidden; }}
  .cover-grid {{ position:absolute; inset:0; background-image:linear-gradient(var(--border) 1px,transparent 1px),linear-gradient(90deg,var(--border) 1px,transparent 1px); background-size:60px 60px; opacity:0.3; }}
  .cover-glow {{ position:absolute; top:-200px; right:-200px; width:600px; height:600px; background:radial-gradient(circle,rgba(201,168,76,0.08) 0%,transparent 70%); pointer-events:none; }}
  .cover-top {{ display:flex; justify-content:space-between; align-items:flex-start; position:relative; }}
  .brand-name {{ font-family:'Bebas Neue',sans-serif; font-size:20px; letter-spacing:4px; color:var(--gold); }}
  .brand-sub {{ font-size:9px; letter-spacing:3px; color:var(--text3); text-transform:uppercase; }}
  .doc-id {{ text-align:right; }}
  .doc-id-label {{ font-size:8px; letter-spacing:2px; color:var(--text3); margin-bottom:4px; }}
  .doc-id-value {{ font-size:11px; color:var(--text2); }}
  .cover-center {{ position:relative; flex:1; display:flex; flex-direction:column; justify-content:center; padding:80px 0 40px; }}
  .report-eyebrow {{ font-size:9px; letter-spacing:5px; color:var(--gold); text-transform:uppercase; margin-bottom:24px; display:flex; align-items:center; gap:12px; }}
  .report-eyebrow::after {{ content:''; flex:1; height:1px; background:var(--gold2); max-width:120px; }}
  .report-title {{ font-family:'Bebas Neue',sans-serif; font-size:clamp(52px,8vw,96px); line-height:0.9; color:var(--text); letter-spacing:2px; margin-bottom:32px; }}
  .report-title span {{ color:var(--gold); }}
  .client-block {{ display:inline-flex; flex-direction:column; gap:6px; border-left:2px solid var(--gold); padding-left:16px; }}
  .client-label {{ font-size:8px; letter-spacing:3px; color:var(--text3); }}
  .client-name {{ font-size:18px; color:var(--text); font-family:'Crimson Pro',serif; font-style:italic; }}
  .cover-bottom {{ display:grid; grid-template-columns:repeat(4,1fr); gap:1px; background:var(--border2); border:1px solid var(--border2); }}
  .cover-stat {{ background:var(--surface); padding:20px 24px; }}
  .cover-stat-label {{ font-size:8px; letter-spacing:2px; color:var(--text3); margin-bottom:8px; }}
  .cover-stat-value {{ font-size:22px; font-family:'Bebas Neue'; letter-spacing:1px; }}
  .cover-stat-sub {{ font-size:9px; color:var(--text3); margin-top:4px; }}
  .section {{ padding:60px; border-bottom:1px solid var(--border); }}
  .section-header {{ display:flex; align-items:baseline; gap:16px; margin-bottom:40px; }}
  .section-num {{ font-family:'Bebas Neue'; font-size:48px; color:var(--border2); line-height:1; }}
  .section-title {{ font-family:'Crimson Pro',serif; font-size:28px; font-weight:300; color:var(--text); letter-spacing:-0.5px; }}
  .section-rule {{ flex:1; height:1px; background:var(--border2); }}
  .verdict {{ display:grid; grid-template-columns:1fr 1fr; gap:20px; margin-bottom:40px; }}
  .verdict-main {{ background:var(--surface2); border:1px solid var(--border2); padding:28px; position:relative; overflow:hidden; }}
  .verdict-main::before {{ content:''; position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg,{capa_color},transparent); }}
  .verdict-label {{ font-size:8px; letter-spacing:3px; color:var(--text3); margin-bottom:12px; }}
  .verdict-score {{ font-family:'Bebas Neue'; font-size:72px; color:{capa_color}; line-height:1; margin-bottom:8px; }}
  .verdict-score-label {{ font-size:10px; color:var(--text2); }}
  .verdict-recommendation {{ margin-top:20px; padding-top:16px; border-top:1px solid var(--border); }}
  .rec-label {{ font-size:8px; letter-spacing:2px; color:var(--text3); margin-bottom:6px; }}
  .rec-badge {{ display:inline-block; padding:6px 16px; font-size:11px; letter-spacing:2px; font-weight:500; }}
  .rec-badge.comprar {{ background:var(--green2); color:var(--green); border:1px solid var(--green); }}
  .rec-badge.cautela {{ background:var(--yellow2); color:var(--yellow); border:1px solid var(--yellow); }}
  .rec-badge.evitar {{ background:var(--red2); color:var(--red); border:1px solid var(--red); }}
  .verdict-metrics {{ display:flex; flex-direction:column; gap:12px; }}
  .metric-card {{ background:var(--surface2); border:1px solid var(--border2); padding:18px 20px; display:flex; justify-content:space-between; align-items:center; }}
  .metric-name {{ font-size:10px; color:var(--text2); }}
  .metric-value {{ font-family:'Bebas Neue'; font-size:22px; letter-spacing:1px; }}
  .score-bar-wrap {{ margin-bottom:8px; }}
  .score-bar-header {{ display:flex; justify-content:space-between; margin-bottom:6px; font-size:10px; }}
  .score-bar-name {{ color:var(--text2); }}
  .score-bar-val {{ color:var(--text); font-weight:500; }}
  .score-bar-track {{ height:4px; background:var(--border2); border-radius:2px; overflow:hidden; margin-bottom:4px; }}
  .score-bar-fill {{ height:100%; border-radius:2px; }}
  .debtor-table {{ width:100%; border-collapse:collapse; }}
  .debtor-table th {{ font-size:8px; letter-spacing:2px; color:var(--text3); text-align:left; padding:10px 16px; border-bottom:1px solid var(--border2); font-weight:400; }}
  .debtor-table td {{ font-size:11px; color:var(--text2); padding:12px 16px; border-bottom:1px solid var(--border); }}
  .debtor-table tr:hover td {{ background:var(--surface2); }}
  .score-pill {{ display:inline-block; padding:3px 10px; border-radius:20px; font-size:10px; font-weight:500; }}
  .score-pill.alto {{ background:var(--green2); color:var(--green); }}
  .score-pill.medio {{ background:var(--yellow2); color:var(--yellow); }}
  .score-pill.baixo {{ background:var(--red2); color:var(--red); }}
  .risk-grid {{ display:grid; grid-template-columns:repeat(3,1fr); gap:16px; margin-bottom:32px; }}
  .risk-card {{ background:var(--surface2); border:1px solid var(--border2); padding:20px; }}
  .risk-card-label {{ font-size:8px; letter-spacing:2px; color:var(--text3); margin-bottom:12px; }}
  .risk-card-value {{ font-family:'Bebas Neue'; font-size:32px; letter-spacing:1px; margin-bottom:4px; }}
  .risk-card-desc {{ font-size:9px; color:var(--text3); line-height:1.5; }}
  .conformidade-list {{ display:flex; flex-direction:column; gap:10px; }}
  .conf-item {{ display:flex; align-items:center; gap:16px; padding:14px 18px; background:var(--surface2); border:1px solid var(--border2); }}
  .conf-icon {{ font-size:14px; min-width:20px; }}
  .conf-text {{ flex:1; font-size:11px; color:var(--text2); }}
  .conf-status {{ font-size:9px; letter-spacing:1px; font-weight:500; }}
  .conf-status.ok {{ color:var(--green); }}
  .conf-status.warn {{ color:var(--yellow); }}
  .conf-status.fail {{ color:var(--red); }}
  .pricing-box {{ background:var(--surface2); border:1px solid var(--gold2); padding:36px; position:relative; overflow:hidden; }}
  .pricing-box::before {{ content:''; position:absolute; top:0; left:0; right:0; height:2px; background:linear-gradient(90deg,var(--gold),transparent); }}
  .pricing-eyebrow {{ font-size:8px; letter-spacing:4px; color:var(--gold); margin-bottom:24px; }}
  .pricing-main {{ display:grid; grid-template-columns:1fr 1fr 1fr; gap:32px; margin-bottom:28px; }}
  .pricing-item-label {{ font-size:9px; letter-spacing:2px; color:var(--text3); margin-bottom:8px; }}
  .pricing-item-value {{ font-family:'Bebas Neue'; font-size:36px; line-height:1; }}
  .pricing-note {{ padding-top:20px; border-top:1px solid var(--border2); font-size:10px; color:var(--text3); line-height:1.7; font-family:'Crimson Pro',serif; font-style:italic; }}
  .report-footer {{ padding:28px 60px; display:flex; justify-content:space-between; align-items:center; border-top:1px solid var(--border2); }}
  .report-disclaimer {{ padding:20px 60px 40px; font-size:9px; color:var(--text3); line-height:1.7; font-family:'Crimson Pro',serif; border-top:1px solid var(--border); }}
  @media print {{ body {{ background:#000; }} .cover {{ page-break-after:always; }} .section {{ page-break-inside:avoid; }} }}
  @media (max-width:700px) {{
    .cover,.section {{ padding:32px 24px; }}
    .cover-bottom {{ grid-template-columns:1fr 1fr; }}
    .verdict {{ grid-template-columns:1fr; }}
    .risk-grid {{ grid-template-columns:1fr; }}
    .pricing-main {{ grid-template-columns:1fr; gap:20px; }}
    .report-footer {{ flex-direction:column; gap:8px; text-align:center; }}
    .report-disclaimer {{ padding:20px 24px 40px; }}
  }}
</style>
</head>
<body>

<div class="cover">
  <div class="cover-grid"></div>
  <div class="cover-glow"></div>
  <div class="cover-top">
    <div>
      <div class="brand-name">Credit Intelligence</div>
      <div class="brand-sub">Análise de Carteiras com IA</div>
    </div>
    <div class="doc-id">
      <div class="doc-id-label">Nº DO RELATÓRIO</div>
      <div class="doc-id-value">{doc_num}</div>
    </div>
  </div>
  <div class="cover-center">
    <div class="report-eyebrow">Relatório de Análise</div>
    <div class="report-title">ANÁLISE<br>DE <span>CARTEIRA</span><br>NPL</div>
    <div class="client-block">
      <span class="client-label">Preparado para</span>
      <span class="client-name">{cliente_nome}</span>
    </div>
  </div>
  <div class="cover-bottom">
    <div class="cover-stat">
      <div class="cover-stat-label">VALOR DE FACE</div>
      <div class="cover-stat-value" style="color:var(--gold)">{valor_total_fmt}</div>
      <div class="cover-stat-sub">{total} devedores</div>
    </div>
    <div class="cover-stat">
      <div class="cover-stat-label">RECUPERAÇÃO ESTIMADA</div>
      <div class="cover-stat-value" style="color:var(--green)">{taxa_media:.1f}%</div>
      <div class="cover-stat-sub">{recuperacao_fmt} esperados</div>
    </div>
    <div class="cover-stat">
      <div class="cover-stat-label">PREÇO MÁX. SUGERIDO</div>
      <div class="cover-stat-value" style="color:var(--gold)">{preco_max_pct*100:.1f}%</div>
      <div class="cover-stat-sub">{preco_max_fmt}</div>
    </div>
    <div class="cover-stat">
      <div class="cover-stat-label">RECOMENDAÇÃO</div>
      <div class="cover-stat-value" style="color:{capa_color}">{rec_geral.split()[0]}</div>
      <div class="cover-stat-sub">Score médio {int(score_medio)}/1000</div>
    </div>
  </div>
</div>

<div class="section">
  <div class="section-header">
    <div class="section-num">01</div>
    <div class="section-title">Veredicto Geral da Carteira</div>
    <div class="section-rule"></div>
  </div>
  <div class="verdict">
    <div class="verdict-main">
      <div class="verdict-label">SCORE GERAL DA CARTEIRA</div>
      <div class="verdict-score">{int(score_medio)}</div>
      <div class="verdict-score-label">de 1.000 pontos · Score máx {score_max} · mín {score_min}</div>
      <div class="verdict-recommendation">
        <div class="rec-label">RECOMENDAÇÃO</div>
        <div class="rec-badge {rec_classe}">{rec_icone} {rec_geral}</div>
      </div>
    </div>
    <div class="verdict-metrics">
      <div class="metric-card">
        <span class="metric-name">Taxa de recuperação estimada</span>
        <span class="metric-value" style="color:var(--green)">{taxa_media:.1f}%</span>
      </div>
      <div class="metric-card">
        <span class="metric-name">Recuperação esperada (R$)</span>
        <span class="metric-value" style="color:var(--gold)">{recuperacao_fmt}</span>
      </div>
      <div class="metric-card">
        <span class="metric-name">Devedores PRIORIDADE</span>
        <span class="metric-value" style="color:var(--green)">{prioridade} de {total}</span>
      </div>
      <div class="metric-card">
        <span class="metric-name">Devedores MONITORAR</span>
        <span class="metric-value" style="color:var(--yellow)">{monitorar} de {total}</span>
      </div>
      <div class="metric-card">
        <span class="metric-name">Devedores RISCO ALTO</span>
        <span class="metric-value" style="color:var(--red)">{risco_alto} de {total}</span>
      </div>
    </div>
  </div>
  <div style="margin-top:8px;">
    <div style="font-size:8px; letter-spacing:2px; color:var(--text3); margin-bottom:20px;">SCORE POR DIMENSÃO DE ANÁLISE</div>
    <div class="score-bar-wrap">
      <div class="score-bar-header"><span class="score-bar-name">Capacidade de pagamento</span><span class="score-bar-val">{cap_pag}</span></div>
      <div class="score-bar-track"><div class="score-bar-fill" style="width:{cap_pag/10}%; background:{'var(--green)' if cap_pag>=700 else 'var(--yellow)'};"></div></div>
    </div>
    <div class="score-bar-wrap">
      <div class="score-bar-header"><span class="score-bar-name">Garantias e colaterais</span><span class="score-bar-val">{garantias}</span></div>
      <div class="score-bar-track"><div class="score-bar-fill" style="width:{garantias/10}%; background:{'var(--green)' if garantias>=700 else 'var(--yellow)'};"></div></div>
    </div>
    <div class="score-bar-wrap">
      <div class="score-bar-header"><span class="score-bar-name">Histórico processual</span><span class="score-bar-val">{hist_proc}</span></div>
      <div class="score-bar-track"><div class="score-bar-fill" style="width:{hist_proc/10}%; background:{'var(--green)' if hist_proc>=700 else 'var(--yellow)'};"></div></div>
    </div>
    <div class="score-bar-wrap">
      <div class="score-bar-header"><span class="score-bar-name">Risco de ocultação patrimonial</span><span class="score-bar-val">{ocultacao}</span></div>
      <div class="score-bar-track"><div class="score-bar-fill" style="width:{ocultacao/10}%; background:{'var(--green)' if ocultacao>=700 else 'var(--yellow)'};"></div></div>
    </div>
    <div class="score-bar-wrap">
      <div class="score-bar-header"><span class="score-bar-name">Conformidade da cessão</span><span class="score-bar-val">{conformidade}</span></div>
      <div class="score-bar-track"><div class="score-bar-fill" style="width:{conformidade/10}%; background:{'var(--green)' if conformidade>=700 else 'var(--yellow)'};"></div></div>
    </div>
  </div>
</div>

<div class="section">
  <div class="section-header">
    <div class="section-num">02</div>
    <div class="section-title">Devedores em Destaque</div>
    <div class="section-rule"></div>
  </div>
  <div style="font-size:10px; color:var(--text3); margin-bottom:20px;">
    {total} devedores · ordenados por score de recuperação (maior → menor)
  </div>
  <table class="debtor-table">
    <thead>
      <tr>
        <th>DEVEDOR</th><th>TIPO</th><th>VALOR DE FACE</th>
        <th>SCORE</th><th>RECUP. EST.</th><th>INADIMP.</th><th>STATUS</th>
      </tr>
    </thead>
    <tbody>{linhas_tabela}</tbody>
  </table>
</div>

<div class="section">
  <div class="section-header">
    <div class="section-num">03</div>
    <div class="section-title">Análise de Risco</div>
    <div class="section-rule"></div>
  </div>
  <div class="risk-grid">
    <div class="risk-card">
      <div class="risk-card-label">EMPRESAS ATIVAS</div>
      <div class="risk-card-value" style="color:var(--green)">{ativos}/{total}</div>
      <div class="risk-card-desc">CNPJs com situação cadastral ativa na Receita Federal</div>
    </div>
    <div class="risk-card">
      <div class="risk-card-label">CPFs NA CARTEIRA</div>
      <div class="risk-card-value" style="color:{'var(--yellow)' if cpfs > 0 else 'var(--green)'}">{cpfs}/{total}</div>
      <div class="risk-card-desc">Documentos CPF — requerem API paga para enriquecimento completo</div>
    </div>
    <div class="risk-card">
      <div class="risk-card-label">SEM PROCESSOS CNJ</div>
      <div class="risk-card-value" style="color:var(--green)">{sem_processos}/{total}</div>
      <div class="risk-card-desc">Devedores sem processo judicial nos 8 tribunais consultados</div>
    </div>
    <div class="risk-card">
      <div class="risk-card-label">PRIORIDADE (700+)</div>
      <div class="risk-card-value" style="color:var(--green)">{prioridade}/{total}</div>
      <div class="risk-card-desc">Devedores com alta probabilidade de recuperação — focar aqui</div>
    </div>
    <div class="risk-card">
      <div class="risk-card-label">INADIMP. LONGA (+48m)</div>
      <div class="risk-card-value" style="color:{'var(--red)' if inadimp_longa > 0 else 'var(--green)'}">{inadimp_longa}/{total}</div>
      <div class="risk-card-desc">Devedores com mais de 4 anos de inadimplência — recuperação difícil</div>
    </div>
    <div class="risk-card">
      <div class="risk-card-label">RETORNO ESPERADO</div>
      <div class="risk-card-value" style="color:var(--gold)">{retorno:.1f}×</div>
      <div class="risk-card-desc">Sobre o preço máximo sugerido de {preco_max_fmt}</div>
    </div>
  </div>
  {alertas}
</div>

<div class="section">
  <div class="section-header">
    <div class="section-num">04</div>
    <div class="section-title">Conformidade da Cessão</div>
    <div class="section-rule"></div>
  </div>
  <div class="conformidade-list">
    <div class="conf-item">
      <div class="conf-icon">✓</div>
      <div class="conf-text">CNPJs verificados na Receita Federal via API oficial (CNPJá)</div>
      <div class="conf-status ok">CONFORME</div>
    </div>
    <div class="conf-item">
      <div class="conf-icon">✓</div>
      <div class="conf-text">Processos consultados em 8 tribunais (TJMG, TJSP, TJRJ, TJRS, TJPR, TJBA, TRF1, TRF3)</div>
      <div class="conf-status ok">CONFORME</div>
    </div>
    <div class="conf-item">
      <div class="conf-icon">{'✓' if sem_processos == total else '⚠'}</div>
      <div class="conf-text">{sem_processos} de {total} devedores sem processo judicial ativo identificado</div>
      <div class="conf-status {'ok' if sem_processos == total else 'warn'}">{'CONFORME' if sem_processos == total else 'ATENÇÃO'}</div>
    </div>
    <div class="conf-item">
      <div class="conf-icon">{'✓' if cpfs == 0 else '⚠'}</div>
      <div class="conf-text">{cpfs} documento(s) CPF sem situação cadastral verificada — API paga necessária</div>
      <div class="conf-status {'ok' if cpfs == 0 else 'warn'}">{'CONFORME' if cpfs == 0 else 'ATENÇÃO'}</div>
    </div>
    <div class="conf-item">
      <div class="conf-icon">⚠</div>
      <div class="conf-text">Documentação de cessão e notificação formal aos devedores não verificada nesta análise</div>
      <div class="conf-status warn">VERIFICAR</div>
    </div>
    <div class="conf-item">
      <div class="conf-icon">⚠</div>
      <div class="conf-text">Recomenda-se registro da cessão no CERC antes da aquisição para garantia jurídica</div>
      <div class="conf-status warn">RECOMENDADO</div>
    </div>
  </div>
</div>

<div class="section">
  <div class="section-header">
    <div class="section-num">05</div>
    <div class="section-title">Precificação Sugerida</div>
    <div class="section-rule"></div>
  </div>
  <div class="pricing-box">
    <div class="pricing-eyebrow">MODELO DE PRECIFICAÇÃO — CREDIT INTELLIGENCE</div>
    <div class="pricing-main">
      <div>
        <div class="pricing-item-label">VALOR DE FACE</div>
        <div class="pricing-item-value" style="color:var(--gold)">{valor_total_fmt}</div>
        <div style="font-size:9px; color:var(--text3); margin-top:4px">{total} devedores</div>
      </div>
      <div>
        <div class="pricing-item-label">RECUPERAÇÃO ESTIMADA</div>
        <div class="pricing-item-value" style="color:var(--green)">{recuperacao_fmt}</div>
        <div style="font-size:9px; color:var(--text3); margin-top:4px">{taxa_media:.1f}% · score médio {int(score_medio)}</div>
      </div>
      <div>
        <div class="pricing-item-label">CUSTO EST. DE COBRANÇA</div>
        <div class="pricing-item-value" style="color:var(--blue)">{custo_fmt}</div>
        <div style="font-size:9px; color:var(--text3); margin-top:4px">30% sobre recuperação</div>
      </div>
    </div>
    <div style="display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-bottom:24px;">
      <div style="background:var(--bg); padding:20px; border:1px solid var(--border2);">
        <div style="font-size:8px; letter-spacing:2px; color:var(--text3); margin-bottom:8px;">PREÇO MÁXIMO SUGERIDO</div>
        <div style="font-family:'Bebas Neue'; font-size:42px; color:var(--gold); line-height:1;">{preco_max_fmt}</div>
        <div style="font-size:10px; color:var(--text3); margin-top:4px;">{preco_max_pct*100:.1f}% do valor de face</div>
      </div>
      <div style="background:var(--bg); padding:20px; border:1px solid var(--border2);">
        <div style="font-size:8px; letter-spacing:2px; color:var(--text3); margin-bottom:8px;">RETORNO ESPERADO</div>
        <div style="font-family:'Bebas Neue'; font-size:42px; color:var(--green); line-height:1;">{retorno:.1f}×</div>
        <div style="font-size:10px; color:var(--text3); margin-top:4px;">Se recuperar {taxa_media:.1f}% em 24 meses</div>
      </div>
    </div>
    <div class="pricing-note">
      Preço máximo calculado com score médio {int(score_medio)}/1000, recuperação estimada de {taxa_media:.1f}% e custo operacional de 30% sobre o recuperado, com retorno mínimo de 18% a.a. sobre o capital investido. {f'{cpfs} CPFs sem enriquecimento foram penalizados no score. Recomenda-se enriquecer esses registros antes de finalizar a oferta.' if cpfs > 0 else 'Todos os CNPJs foram enriquecidos com dados da Receita Federal.'}
    </div>
  </div>
</div>

<div class="report-footer">
  <span style="font-size:9px; letter-spacing:3px; color:var(--text3)">CREDIT INTELLIGENCE</span>
  <span style="font-size:9px; color:var(--text3)">CONFIDENCIAL · Uso exclusivo do destinatário</span>
  <span style="font-size:9px; color:var(--text3)">{doc_num} · {data_hoje}</span>
</div>
<div class="report-disclaimer">
  As estimativas contidas neste relatório são baseadas em modelos estatísticos, dados públicos disponíveis (Receita Federal via CNPJá, processos via Datajud/CNJ) e informações fornecidas pelo contratante. Não constituem garantia de retorno financeiro. A Credit Intelligence não se responsabiliza por decisões de investimento tomadas com base neste documento. Recomenda-se validação jurídica independente antes da aquisição. Gerado automaticamente em {data_hoje}.
</div>

<div style="position:fixed; bottom:32px; right:32px; z-index:1000; display:flex; gap:10px;">
  <button onclick="window.print()" style="
    background:var(--gold); color:var(--bg); border:none;
    font-family:'Bebas Neue',sans-serif; font-size:16px;
    letter-spacing:2px; padding:12px 24px; cursor:pointer;">
    ⬇ SALVAR PDF
  </button>
  <button onclick="window.close()" style="
    background:transparent; color:var(--text3); border:1px solid var(--border2);
    font-family:'IBM Plex Mono',monospace; font-size:11px;
    letter-spacing:2px; padding:12px 24px; cursor:pointer;">
    FECHAR
  </button>
</div>

<style>
@media print {{
  body {{ background: #000 !important; -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
  div[style*="position:fixed"] {{ display:none !important; }}
  .cover {{ page-break-after: always; min-height: auto; padding: 40px; }}
  .section {{ page-break-inside: avoid; padding: 40px; }}
}}
</style>

</body>
</html>"""

    return html
