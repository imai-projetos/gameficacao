import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
import pytz

from analise_connect import (
    load_inventario,
    prepare_inventario,
    load_separacao,
    prepare_separacao,
)
from auxiliar import (
    inventario_metrics,
    inventario_ranking_usuarios,
    inventario_ranking_grupos,
    separacao_metrics,
    separacao_ranking_usuarios,
    separacao_ranking_produtos,
    format_minutes_hhmmss,
    format_int_thousand,
)

# =========================================================
# CONFIG DO APP
# =========================================================
br_tz = pytz.timezone("America/Sao_Paulo")

st.set_page_config(
    page_title="Painel Analítico Operacional",
    layout="wide",
    page_icon="📊",
    initial_sidebar_state="collapsed",
)


def render_card(col, titulo, valor, maximo, emoji=""):
    col.markdown(
        f"""
    <div style="
        background-color:#1239FF;
        border-radius:12px;
        padding:12px;
        text-align:center;
        box-shadow: 0 2px 4px rgba(0,0,0,0.2);
        color:white;
    ">
        <div style="font-size:20px;font-weight:600;">{emoji} {titulo}</div>
        <div style="font-size:35px;font-weight:bold;margin-top:6px;">{valor}</div>
        <div style="font-size:18px;margin-top:4px;">{maximo}</div>
    </div>
    """,
        unsafe_allow_html=True,
    )


# Título
st.markdown(
    '<div style="font-size:28px;font-weight:700;margin-bottom:4px;">📊 Painel Analítico – Separação & Inventário</div>',
    unsafe_allow_html=True,
)

# Texto "Atualizado em: <data e hora>"
agora = datetime.now(br_tz)
st.markdown(
    f'<div style="font-size:16px;color:#BBBBBB;margin-bottom:12px;">Atualizado em: '
    f'{agora.strftime("%d/%m/%Y %H:%M:%S")}</div>',
    unsafe_allow_html=True,
)

# CSS para tabelas centradas com fonte branca
st.markdown(
    """
    <style>
    .centered-table td, .centered-table th {
        text-align: center !important;
        color: white !important;
        background-color: #1f2937 !important;
        border-color: #374151 !important;
    }
    .centered-table thead th {
        background-color: #111827 !important;
        font-weight: 600 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# =========================================================
# CARREGAMENTO BASE
# =========================================================
df_inv_raw_all = load_inventario()
df_sep_raw_all = load_separacao()

df_inv_all = prepare_inventario(df_inv_raw_all)
df_sep_all = prepare_separacao(df_sep_raw_all)

# =========================================================
# SIDEBAR – Filtros e ações
# =========================================================
with st.sidebar:
    st.header("Filtros")

    # Botões de ação
    if st.button("🔄 Atualizar dados do banco"):
        st.rerun()

    if st.button("🧹 Limpar filtros"):
        st.rerun()

    st.markdown("---")

    # Mês corrente como padrão
    hoje = date.today()
    primeiro_dia_mes = hoje.replace(day=1)
    if primeiro_dia_mes.month == 12:
        primeiro_dia_proximo_mes = primeiro_dia_mes.replace(
            year=primeiro_dia_mes.year + 1, month=1, day=1
        )
    else:
        primeiro_dia_proximo_mes = primeiro_dia_mes.replace(
            month=primeiro_dia_mes.month + 1, day=1
        )
    ultimo_dia_mes = (pd.Timestamp(primeiro_dia_proximo_mes) - pd.Timedelta(days=1)).date()

    # Intervalo global com base nos dados
    min_data_inv = (
        df_inv_all["data"].min()
        if "data" in df_inv_all.columns and not df_inv_all.empty
        else primeiro_dia_mes
    )
    max_data_inv = (
        df_inv_all["data"].max()
        if "data" in df_inv_all.columns and not df_inv_all.empty
        else ultimo_dia_mes
    )

    min_data_sep = (
        df_sep_all["data"].min()
        if "data" in df_sep_all.columns and not df_sep_all.empty
        else primeiro_dia_mes
    )
    max_data_sep = (
        df_sep_all["data"].max()
        if "data" in df_sep_all.columns and not df_sep_all.empty
        else ultimo_dia_mes
    )

    min_data_global = min(min_data_inv, min_data_sep)
    max_data_global = max(max_data_inv, max_data_sep)

    data_inicial_default = max(min_data_global, primeiro_dia_mes)
    data_final_default = min(max_data_global, ultimo_dia_mes)

    data_inicial = st.date_input(
        "Data inicial",
        value=data_inicial_default,
        min_value=min_data_global,
        max_value=max_data_global,
    )
    data_final = st.date_input(
        "Data final",
        value=data_final_default,
        min_value=data_inicial,
        max_value=max_data_global,
    )

    st.markdown("---")

    # Colaborador
    todos_usuarios = sorted(
        set(
            list(df_inv_all.get("usuario", []))
            + list(df_sep_all.get("usuario", []))
        )
    )
    colaborador = st.selectbox(
        "Colaborador",
        options=["[Todos]"] + todos_usuarios,
        index=0,
    )

    st.markdown("---")

    # Filtro de filial (quando existir coluna 'filial' nos DFs)
    filiais_inv = (
        sorted(df_inv_all["filial"].unique()) if "filial" in df_inv_all.columns else []
    )
    filiais_sep = (
        sorted(df_sep_all["filial"].unique()) if "filial" in df_sep_all.columns else []
    )
    todas_filiais = sorted(set(filiais_inv + filiais_sep))

    if todas_filiais:
        filial = st.selectbox(
            "Filial",
            options=["[Todas]"] + todas_filiais,
            index=0,
        )
    else:
        filial = "[Todas]"

    st.markdown("---")

    # Tempo de separação
    uso_tempo_sep = st.radio(
        "Tempo de separação",
        options=[
            "Processo completo (DtInicioSeparacao → DtFimColetor)",
            "Somente coletor (DtInicioColetor → DtFimColetor)",
        ],
        index=0,
    )
    uso_tempo_flag = "separacao" if "Processo completo" in uso_tempo_sep else "coletor"

    st.markdown("---")

    # Top N produtos
    top_n_produtos = st.number_input(
        "Quantidade de produtos no ranking",
        min_value=1,
        max_value=200,
        value=20,
        step=1,
    )

# =========================================================
# FILTROS EM MEMÓRIA
# =========================================================
def aplicar_filtros(df: pd.DataFrame, data_col: str = "data") -> pd.DataFrame:
    if df.empty or data_col not in df.columns:
        return df

    df_f = df[(df[data_col] >= data_inicial) & (df[data_col] <= data_final)].copy()

    if colaborador != "[Todos]" and "usuario" in df_f.columns:
        df_f = df_f[df_f["usuario"] == colaborador].copy()

    if filial != "[Todas]" and "filial" in df_f.columns:
        df_f = df_f[df_f["filial"] == filial].copy()

    return df_f


df_inv = aplicar_filtros(df_inv_all, data_col="data")
df_sep = aplicar_filtros(df_sep_all, data_col="data")

# =========================================================
# PERÍODO ANTERIOR – CHAVE DE COMPARAÇÃO
# =========================================================
duracao = (data_final - data_inicial).days + 1
inicio_anterior = data_inicial - timedelta(days=duracao)
fim_anterior = data_inicial - timedelta(days=1)

def aplicar_filtros_periodo(df: pd.DataFrame, inicio: date, fim: date, data_col: str = "data") -> pd.DataFrame:
    if df.empty or data_col not in df.columns:
        return df

    df_f = df[(df[data_col] >= inicio) & (df[data_col] <= fim)].copy()

    if colaborador != "[Todos]" and "usuario" in df_f.columns:
        df_f = df_f[df_f["usuario"] == colaborador].copy()

    if filial != "[Todas]" and "filial" in df_f.columns:
        df_f = df_f[df_f["filial"] == filial].copy()

    return df_f

df_inv_prev = aplicar_filtros_periodo(df_inv_all, inicio_anterior, fim_anterior, data_col="data")
df_sep_prev = aplicar_filtros_periodo(df_sep_all, inicio_anterior, fim_anterior, data_col="data")

# =========================================================
# FUNÇÕES AUXILIARES
# =========================================================
def calc_metricas_diarias(df: pd.DataFrame, tempo_col: str):
    if df.empty or tempo_col not in df.columns:
        return 0.0, 0.0, 0.0, 0.0

    df_valid = df.dropna(subset=[tempo_col])
    if df_valid.empty or "data" not in df_valid.columns:
        return 0.0, 0.0, 0.0, 0.0

    grp = df_valid.groupby("data")[tempo_col]

    max_por_dia = grp.max()
    tempo_max_abs = max_por_dia.max() if not max_por_dia.empty else 0.0
    media_max_diario = max_por_dia.mean() if not max_por_dia.empty else 0.0

    min_por_dia = grp.min()
    tempo_min_abs = min_por_dia.min() if not min_por_dia.empty else 0.0
    media_min_diario = min_por_dia.mean() if not min_por_dia.empty else 0.0

    return tempo_max_abs, media_max_diario, tempo_min_abs, media_min_diario

def calc_itens_distintos_por_dia(df: pd.DataFrame, col_item: str):
    if df.empty or col_item not in df.columns or "data" not in df.columns:
        return 0, 0

    distintos_por_dia = df.groupby("data")[col_item].nunique()
    if distintos_por_dia.empty:
        return 0, 0

    media = distintos_por_dia.mean()
    maximo = distintos_por_dia.max()
    return media, maximo

def calc_variacao_percentual(valor_atual, valor_anterior):
    if valor_anterior in (0, None):
        return None
    return (valor_atual - valor_anterior) / valor_anterior * 100.0

def format_var_percent(pct):
    if pct is None:
        return ""
    sinal = "+" if pct >= 0 else ""
    return f"{sinal}{pct:.1f}% vs período anterior"

def add_itens_distintos_por_colaborador_sep(df: pd.DataFrame, ranking: pd.DataFrame) -> pd.DataFrame:
    if df.empty or ranking.empty or "usuario" not in df.columns or "produto" not in df.columns:
        return ranking
    m = (
        df.groupby("usuario")["produto"]
        .nunique()
        .rename("itens_distintos")
        .reset_index()
    )
    r = ranking.merge(m, how="left", left_on="usuario", right_on="usuario")
    r["itens_distintos"] = r["itens_distintos"].fillna(0).astype(int)
    return r

def add_itens_distintos_por_colaborador_inv(df: pd.DataFrame, ranking: pd.DataFrame) -> pd.DataFrame:
    if df.empty or ranking.empty or "usuario" not in df.columns or "codigo" not in df.columns:
        return ranking
    m = (
        df.groupby("usuario")["codigo"]
        .nunique()
        .rename("itens_distintos")
        .reset_index()
    )
    r = ranking.merge(m, how="left", left_on="usuario", right_on="usuario")
    r["itens_distintos"] = r["itens_distintos"].fillna(0).astype(int)
    return r

def add_itens_distintos_por_grupo_inv(df: pd.DataFrame, ranking: pd.DataFrame) -> pd.DataFrame:
    if df.empty or ranking.empty or "descricao_grupo" not in df.columns or "codigo" not in df.columns:
        return ranking
    m = (
        df.groupby("descricao_grupo")["codigo"]
        .nunique()
        .rename("itens_distintos")
        .reset_index()
    )
    r = ranking.merge(m, how="left", left_on="descricao_grupo", right_on="descricao_grupo")
    r["itens_distintos"] = r["itens_distintos"].fillna(0).astype(int)
    return r

# Ordem das abas: Separação primeiro
tab_sep, tab_inv = st.tabs(["🚚 Separação", "📦 Inventário"])

# =========================================================
# SEPARAÇÃO
# =========================================================
with tab_sep:
    st.subheader("Separação – Visão geral")

    if df_sep.empty:
        st.info("Nenhum dado de separação para os filtros selecionados.")
    else:
        tempo_col_sep = (
            "tempo_separacao_minutos"
            if uso_tempo_flag == "separacao" and "tempo_separacao_minutos" in df_sep.columns
            else "tempo_coletor_minutos"
        )

        # Métricas atuais
        m_sep = separacao_metrics(df_sep, uso_tempo=uso_tempo_flag)
        tempo_max_abs, media_max_diario, tempo_min_abs, media_min_diario = calc_metricas_diarias(
            df_sep, tempo_col_sep
        )

        # Métricas do período anterior
        m_sep_prev = separacao_metrics(df_sep_prev, uso_tempo=uso_tempo_flag)

        # Variações
        var_vol_sep = calc_variacao_percentual(len(df_sep), len(df_sep_prev))
        var_tempo_medio_sep = calc_variacao_percentual(
            m_sep["tempo_medio_minutos"], m_sep_prev["tempo_medio_minutos"]
        )

        # Totais por dia
        df_sep_dia = df_sep.copy()
        if "data" in df_sep_dia.columns:
            sep_por_dia = df_sep_dia.groupby("data").size()
            total_sep_periodo = int(sep_por_dia.sum())
            max_sep_dia = int(sep_por_dia.max())
            dias_no_periodo = sep_por_dia.shape[0]
            media_sep_dia = total_sep_periodo / dias_no_periodo if dias_no_periodo > 0 else 0
        else:
            total_sep_periodo = len(df_sep_dia)
            max_sep_dia = total_sep_periodo
            dias_no_periodo = 1
            media_sep_dia = total_sep_periodo

        # Itens distintos por separação (produto)
        media_itens_sep, max_itens_sep = calc_itens_distintos_por_dia(df_sep, "produto")

        c1, c2, c3, c4 = st.columns(4)

        # Tempo médio por separação + máximo do período + comparação (com quebra de linha)
        render_card(
            c1,
            "Tempo médio por separação",
            format_minutes_hhmmss(m_sep["tempo_medio_minutos"]),
            f"Máx no período: {format_minutes_hhmmss(tempo_max_abs)}<br>{format_var_percent(var_tempo_medio_sep)}",
            emoji="⏱️",
        )

        # Total de separações com comparação e quebra de linha
        render_card(
            c2,
            "Total de separações por período",
            format_int_thousand(total_sep_periodo),
            f"Máx/dia: {format_int_thousand(max_sep_dia)}<br>{format_var_percent(var_vol_sep)}",
            emoji="🔢",
        )

        # Média de separações por dia + linha extra em branco
        render_card(
            c3,
            "Média de separações por dia",
            format_int_thousand(int(round(media_sep_dia))),
            f"Dias: {format_int_thousand(dias_no_periodo)}<br>&nbsp;",
            emoji="📆",
        )

        # Itens distintos/dia com comparação vs período anterior
        media_itens_sep_prev, _ = calc_itens_distintos_por_dia(df_sep_prev, "produto")
        var_itens_sep = calc_variacao_percentual(media_itens_sep, media_itens_sep_prev)

        render_card(
            c4,
            "Itens distintos/dia (Separação)",
            format_int_thousand(int(round(media_itens_sep))),
            f"Máx/dia: {format_int_thousand(int(max_itens_sep))}<br>{format_var_percent(var_itens_sep)}",
            emoji="📦",
        )

    st.markdown("---")

    # Tabelas lado a lado
    col_sep_left, col_sep_right = st.columns(2)

    with col_sep_left:
        st.markdown("#### Ranking de colaboradores (Separação)")
        rank_usuarios_sep = (
            separacao_ranking_usuarios(df_sep, uso_tempo=uso_tempo_flag)
            if not df_sep.empty
            else pd.DataFrame()
        )
        if rank_usuarios_sep.empty:
            st.info("Sem dados para o ranking de colaboradores com os filtros atuais.")
        else:
            r = add_itens_distintos_por_colaborador_sep(df_sep, rank_usuarios_sep.copy())
            r["Colaborador"] = r["usuario"]
            r["Processos"] = r["processos"].apply(format_int_thousand)
            r["Itens distintos"] = r["itens_distintos"].apply(format_int_thousand)
            r["Tempo médio"] = r["tempo_medio_minutos"].apply(format_minutes_hhmmss)
            r["Tempo total"] = r["tempo_total_minutos"].apply(format_minutes_hhmmss)

            tabela = r[["Colaborador", "Processos", "Itens distintos", "Tempo médio", "Tempo total"]]
            html = tabela.to_html(index=False, classes="centered-table")
            st.markdown(html, unsafe_allow_html=True)

    with col_sep_right:
        st.markdown("#### Ranking de produtos (Separação)")
        rank_produtos_sep = (
            separacao_ranking_produtos(
                df_sep,
                uso_tempo=uso_tempo_flag,
                top_n=int(top_n_produtos),
            )
            if not df_sep.empty
            else pd.DataFrame()
        )

        if rank_produtos_sep.empty:
            st.info("Sem dados para o ranking de produtos com os filtros atuais.")
        else:
            r = rank_produtos_sep.copy()
            r["Produto"] = r["produto"]
            r["Processos"] = r["processos"].apply(format_int_thousand)
            r["Tempo médio"] = r["tempo_medio_minutos"].apply(format_minutes_hhmmss)

            tabela = r[["Produto", "Processos", "Tempo médio"]]
            html = tabela.to_html(index=False, classes="centered-table")
            st.markdown(html, unsafe_allow_html=True)

# =========================================================
# INVENTÁRIO
# =========================================================
with tab_inv:
    st.subheader("Inventário – Visão geral")

    if df_inv.empty:
        st.info("Nenhum dado de inventário para os filtros selecionados.")
    else:
        m_inv = inventario_metrics(df_inv)

        tempo_max_abs_inv, media_max_diario_inv, tempo_min_abs_inv, media_min_diario_inv = calc_metricas_diarias(
            df_inv, "tempo_minutos"
        )

        m_inv_prev = inventario_metrics(df_inv_prev)
        var_vol_inv = calc_variacao_percentual(len(df_inv), len(df_inv_prev))
        var_tempo_medio_inv = calc_variacao_percentual(
            m_inv["tempo_medio_minutos"], m_inv_prev["tempo_medio_minutos"]
        )

        media_itens_inv, max_itens_inv = calc_itens_distintos_por_dia(df_inv, "codigo")
        media_itens_inv_prev, _ = calc_itens_distintos_por_dia(df_inv_prev, "codigo")
        var_itens_inv = calc_variacao_percentual(media_itens_inv, media_itens_inv_prev)

        c1, c2, c3, c4 = st.columns(4)
        render_card(
            c1,
            "Tempo médio por inventário",
            format_minutes_hhmmss(m_inv["tempo_medio_minutos"]),
            f"Máx no período: {format_minutes_hhmmss(tempo_max_abs_inv)}<br>{format_var_percent(var_tempo_medio_inv)}",
            emoji="⏱️",
        )
        render_card(
            c2,
            "Total de inventários",
            format_int_thousand(m_inv["total_processos"]),
            format_var_percent(var_vol_inv),
            emoji="🔢",
        )
        render_card(
            c3,
            "Itens distintos/dia (Inventário)",
            format_int_thousand(int(round(media_itens_inv))),
            f"Máx/dia: {format_int_thousand(int(max_itens_inv))}<br>{format_var_percent(var_itens_inv)}",
            emoji="📦",
        )
        render_card(
            c4,
            "Tempo médio máx/dia (informativo)",
            format_minutes_hhmmss(media_max_diario_inv),
            "",
            emoji="ℹ️",
        )

    st.markdown("---")

    # Tabelas lado a lado
    col_inv_left, col_inv_right = st.columns(2)

    with col_inv_left:
        st.markdown("#### Ranking de colaboradores (Inventário)")
        rank_usuarios_inv = (
            inventario_ranking_usuarios(df_inv) if not df_inv.empty else pd.DataFrame()
        )
        if rank_usuarios_inv.empty:
            st.info("Sem dados para o ranking de colaboradores com os filtros atuais.")
        else:
            r = add_itens_distintos_por_colaborador_inv(df_inv, rank_usuarios_inv.copy())
            r["Colaborador"] = r["usuario"]
            r["Processos"] = r["processos"].apply(format_int_thousand)
            r["Itens distintos"] = r["itens_distintos"].apply(format_int_thousand)
            r["Tempo médio"] = r["tempo_medio_minutos"].apply(format_minutes_hhmmss)
            r["Tempo total"] = r["tempo_total_minutos"].apply(format_minutes_hhmmss)

            tabela = r[["Colaborador", "Processos", "Itens distintos", "Tempo médio", "Tempo total"]]
            html = tabela.to_html(index=False, classes="centered-table")
            st.markdown(html, unsafe_allow_html=True)

    with col_inv_right:
        st.markdown("#### Ranking de grupos (Inventário)")
        rank_grupos_inv = (
            inventario_ranking_grupos(df_inv) if not df_inv.empty else pd.DataFrame()
        )
        if rank_grupos_inv.empty:
            st.info("Sem dados para o ranking de grupos com os filtros atuais.")
        else:
            r = add_itens_distintos_por_grupo_inv(df_inv, rank_grupos_inv.copy())
            r["Grupo de inventário"] = r["descricao_grupo"]
            r["Processos"] = r["processos"].apply(format_int_thousand)
            r["Itens distintos"] = r["itens_distintos"].apply(format_int_thousand)
            r["Tempo médio"] = r["tempo_medio_minutos"].apply(format_minutes_hhmmss)

            tabela = r[["Grupo de inventário", "Processos", "Itens distintos", "Tempo médio"]]
            html = tabela.to_html(index=False, classes="centered-table")
            st.markdown(html, unsafe_allow_html=True)