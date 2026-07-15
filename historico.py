import pandas as pd
import streamlit as st
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from connect import prepare_data, load_data_periodo
from pontuacao import carregar_pesos, calcular_pontos

# ---------------------------------------------------------
# Configuração da página
# ---------------------------------------------------------
st.set_page_config(
    page_title="Histórico de Pontuação por Colaborador",
    layout="wide",
    page_icon="📈",
    initial_sidebar_state="collapsed",
)

st.title("📈 Histórico de Pontuação por Colaborador")

# Placeholder para status (última atualização)
status_placeholder = st.empty()

# =========================================================
# Helper para tornar DataFrame amigável ao Arrow/Streamlit
# =========================================================
def make_arrow_friendly(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ajusta tipos de colunas para evitar erros na conversão para Arrow/Streamlit.
    - Garante que 'data' seja datetime64[ns] ou string.
    - Converte colunas object para string.
    """
    df = df.copy()

    # Tratar coluna 'data' explicitamente
    if "data" in df.columns:
        # Se já for datetime, mantemos
        if not pd.api.types.is_datetime64_any_dtype(df["data"]):
            # Tentar converter para datetime
            df["data"] = pd.to_datetime(df["data"], errors="coerce")

        # Para evitar problemas de timezone, garantir que seja "naive" (sem tz)
        if pd.api.types.is_datetime64_any_dtype(df["data"]):
            # Remove qualquer informação de timezone
            df["data"] = df["data"].dt.tz_localize(None)

    # Converter todas as colunas object para string
    for col in df.select_dtypes(include=["object"]).columns:
        df[col] = df[col].astype("string")

    return df


# =========================================================
# Funções auxiliares
# =========================================================
@st.cache_data
def carregar_dados_com_pontos_periodo(
    data_inicio: date,
    data_fim: date
) -> pd.DataFrame:
    """
    Carrega dados da view para o período selecionado e aplica pontuação.
    Retorna dados detalhados (linha a linha) já com 'pontos'.
    """
    df_hist = load_data_periodo(data_inicio, data_fim)

    if df_hist.empty:
        return pd.DataFrame()

    df_hist = prepare_data(df_hist)

    # Garante que 'data' exista e esteja em formato de datetime
    if "data" in df_hist.columns:
        df_hist["data"] = pd.to_datetime(df_hist["data"], errors="coerce")
    elif "data_hora_mov" in df_hist.columns:
        df_hist["data"] = pd.to_datetime(df_hist["data_hora_mov"], errors="coerce")
    else:
        # Em vez de st.error aqui (que pode ser chamado dentro de cache_data),
        # retornamos DF vazio e tratamos fora.
        return pd.DataFrame()

    # Garantir que 'data' seja apenas a data (sem horário) para agregação
    df_hist["data"] = df_hist["data"].dt.date

    pesos = carregar_pesos()
    df_hist = calcular_pontos(df_hist, pesos, fator_escala_pontos=10.0)

    return df_hist


def agregar_por_dia_e_colaborador(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    # Garantir colunas necessárias
    for col in ["data", "conferente", "movimentacoes", "pontos",
                "local", "grupo", "marca", "curva"]:
        if col not in df.columns:
            if col in ["movimentacoes", "pontos"]:
                df[col] = 0
            else:
                df[col] = ""

    # Converter 'data' para datetime novamente (com hora 00:00),
    # para facilitar ordenação e exibição
    if not pd.api.types.is_datetime64_any_dtype(df["data"]):
        df["data"] = pd.to_datetime(df["data"], errors="coerce")

    def join_unicos(series: pd.Series) -> str:
        valores = sorted(
            {str(v) for v in series if pd.notna(v) and str(v).strip() != ""}
        )
        return ", ".join(valores)

    agregados = (
        df
        .groupby(["data", "conferente"], as_index=False)
        .agg(
            movimentacoes=("movimentacoes", "sum"),
            pontos_dia=("pontos", "sum"),
            local=("local", join_unicos),
            grupo=("grupo", join_unicos),
            marca=("marca", join_unicos),
            curva=("curva", join_unicos),
        )
    )

    agregados["pontos_dia"] = agregados["pontos_dia"].round(2)

    agregados = agregados[
        ["data", "conferente", "movimentacoes", "pontos_dia",
         "local", "grupo", "marca", "curva"]
    ].sort_values(["conferente", "data"])

    return agregados


def criar_matriz_pontos(df_agregado: pd.DataFrame) -> pd.DataFrame:
    if df_agregado.empty:
        return df_agregado

    # Garantir que 'data' seja datetime para pivot
    if not pd.api.types.is_datetime64_any_dtype(df_agregado["data"]):
        df_agregado["data"] = pd.to_datetime(df_agregado["data"], errors="coerce")

    matriz = (
        df_agregado
        .pivot_table(
            index="data",
            columns="conferente",
            values="pontos_dia",
            aggfunc="sum",
            fill_value=0,
        )
        .sort_index()
    )

    matriz = matriz.reindex(sorted(matriz.columns), axis=1)
    matriz = matriz.reset_index()

    return matriz


def adicionar_linha_total_matriz(df_matriz: pd.DataFrame) -> pd.DataFrame:
    if df_matriz.empty:
        return df_matriz

    df = df_matriz.copy()

    cols_pontos = [c for c in df.columns if c != "data"]
    totais = {c: df[c].sum() for c in cols_pontos}

    # Para evitar mistura de tipos na coluna 'data',
    # vamos transformar a coluna em string antes de adicionar TOTAL.
    df["data"] = df["data"].dt.strftime("%d/%m/%Y")

    totais["data"] = "TOTAL"
    linha_total = pd.DataFrame([totais])

    df_matriz_total = pd.concat([df, linha_total], ignore_index=True)

    return df_matriz_total


# =========================================================
# Sidebar - filtros
# =========================================================
st.sidebar.header("🔎 Filtros de Histórico")

hoje = date.today()
default_inicio = date(hoje.year, hoje.month, max(1, hoje.day - 7))

data_inicio = st.sidebar.date_input("Data inicial", value=default_inicio)
data_fim = st.sidebar.date_input("Data final", value=hoje)

if data_inicio > data_fim:
    st.sidebar.error("Data inicial não pode ser maior que a data final.")
    st.stop()

atualizar = st.sidebar.button("🔄 Atualizar dados")

if atualizar:
    st.cache_data.clear()
    st.rerun()

# =========================================================
# Carrega dados com pontos para o período
# =========================================================
df_periodo = carregar_dados_com_pontos_periodo(data_inicio, data_fim)

if df_periodo.empty:
    st.warning("Nenhum dado encontrado para o período selecionado "
               "ou coluna de data não identificada.")
    st.stop()

# Atualiza status de última atualização com fuso horário correto
utc_now = datetime.now(timezone.utc)
br_tz = ZoneInfo("America/Sao_Paulo")
agora = utc_now.astimezone(br_tz)

status_placeholder.caption(
    f"🕒 Última atualização: **{agora.strftime('%d/%m/%Y %H:%M:%S')}** | "
    f"📊 Registros no período: **{len(df_periodo):,}**"
)

# Filtro de filial (local)
st.sidebar.subheader("🏢 Filial")

if "local" in df_periodo.columns:
    filiais = sorted(df_periodo["local"].dropna().astype(str).unique())
else:
    filiais = []

if filiais:
    filial_sel = st.sidebar.multiselect(
        "Selecione filiais",
        options=filiais,
        default=filiais,
    )
    df_periodo = df_periodo[df_periodo["local"].astype(str).isin(filial_sel)]
else:
    st.sidebar.warning("Nenhuma filial encontrada nos dados.")
    st.stop()

if df_periodo.empty:
    st.warning("Nenhum dado após aplicar o filtro de filial.")
    st.stop()

# Filtro de colaborador
st.sidebar.subheader("👤 Colaboradores")

if "conferente" in df_periodo.columns:
    colaboradores = sorted(df_periodo["conferente"].dropna().astype(str).unique())
else:
    colaboradores = []

if colaboradores:
    colaborador_sel = st.sidebar.multiselect(
        "Selecione colaboradores",
        options=colaboradores,
        default=colaboradores,
    )
    df_periodo = df_periodo[df_periodo["conferente"].astype(str).isin(colaborador_sel)]
else:
    st.sidebar.warning("Nenhum colaborador encontrado nos dados.")
    st.stop()

if df_periodo.empty:
    st.warning("Nenhum dado após aplicar os filtros de filial/colaborador.")
    st.stop()

# =========================================================
# Tabela 1: dia a dia por colaborador
# =========================================================
df_agregado = agregar_por_dia_e_colaborador(df_periodo)

st.subheader("📅 Pontuação diária por colaborador")

df_agregado_arrow = make_arrow_friendly(df_agregado)

st.dataframe(
    df_agregado_arrow,
    use_container_width=True,
    hide_index=True,
)

# =========================================================
# Tabela 2: matriz de pontuação (dias x colaboradores, com total)
# =========================================================
st.subheader("🧮 Matriz de pontuação")

df_matriz = criar_matriz_pontos(df_agregado)
df_matriz_total = adicionar_linha_total_matriz(df_matriz)

if df_matriz_total.empty:
    st.info("Nenhum dado para montar a matriz de pontuação.")
else:
    df_matriz_total_arrow = make_arrow_friendly(df_matriz_total)
    st.dataframe(
        df_matriz_total_arrow,
        use_container_width=True,
        hide_index=True,
    )

# =========================================================
# Exportar para Excel (histórico detalhado)
# =========================================================
def to_excel_bytes(df: pd.DataFrame) -> bytes:
    from io import BytesIO
    import xlsxwriter

    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False, sheet_name="Historico")
    return output.getvalue()


st.subheader("📤 Exportar histórico")

excel_bytes = to_excel_bytes(df_agregado)

st.download_button(
    label="📥 Baixar tabela em Excel",
    data=excel_bytes,
    file_name=f"historico_pontuacao_{data_inicio}_a_{data_fim}.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)