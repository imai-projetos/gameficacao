import os
import pandas as pd
from dotenv import load_dotenv
import pg8000
import streamlit as st
from datetime import datetime, date

# =========================================================
# Conexão básica ao banco
# =========================================================
def _get_conn_info() -> dict:
    """
    Lê as variáveis de ambiente de conexão com o banco.
    Em ambiente local, carrega do .env se existir.
    Em produção (Streamlit Cloud), use Secrets / env vars.
    """

    # Carrega .env apenas se existir (evita erro/overhead em produção)
    if os.path.exists(".env"):
        load_dotenv()

    host = os.getenv("DB_HOST")
    port = os.getenv("DB_PORT")
    db_name = os.getenv("DB_NAME")
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")

    if not all([host, port, db_name, user, password]):
        # Em produção (Streamlit Cloud), isso ajuda a identificar se faltou configurar secrets
        raise ValueError(
            "Variáveis de ambiente de banco incompletas. "
            "Verifique DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD."
        )

    return {
        "host": host,
        "port": int(port),
        "database": db_name,  # pg8000 usa 'database'
        "user": user,
        "password": password,
    }


def load_data(filtro: str = "") -> pd.DataFrame:
    """
    Carrega dados da view vw_kardex_credito_produto_usuario com filtro opcional.
    Parâmetros:
        filtro (str): cláusula SQL opcional iniciando por
                      WHERE, ORDER BY, etc.
    Retorna:
        DataFrame com os dados consultados.
    """
    try:
        conn_info = _get_conn_info()
    except ValueError as e:
        # Mostra erro amigável no app Streamlit
        st.error(str(e))
        return pd.DataFrame()

    try:
        with pg8000.connect(**conn_info) as conn:
            query = f"""
                SELECT *
                FROM vw_kardex_credito_produto_usuario
                {filtro}
            """
            df = pd.read_sql_query(query, conn)
        return df
    except Exception as e:
        st.error(f"Erro ao conectar ao PostgreSQL ou executar query: {e}")
        return pd.DataFrame()

# =========================================================
# Carregar apenas o dia corrente
# =========================================================
def load_data_today() -> pd.DataFrame:
    """
    Carrega apenas os dados do dia corrente da view vw_kardex_credito_produto_usuario.
    Considera a coluna DtNow como referência de data/hora.
    """
    hoje = date.today().strftime("%Y-%m-%d")
    # Usa nome real da coluna da view (DtNow) no filtro SQL
    filtro = f"""WHERE "DtNow"::date = '{hoje}'"""
    return load_data(filtro=filtro)

# =========================================================
# Carregar período de datas (NOVO, para o histórico)
# =========================================================
def load_data_periodo(data_inicio: date, data_fim: date) -> pd.DataFrame:
    """
    Carrega dados da view vw_kardex_credito_produto_usuario para um período de datas.
    Considera a coluna DtNow como referência de data/hora.

    Essa função NÃO é usada pelo main.py (corrida),
    é pensada para o histórico (historico.py).
    """
    try:
        conn_info = _get_conn_info()
    except ValueError as e:
        st.error(str(e))
        return pd.DataFrame()

    try:
        with pg8000.connect(**conn_info) as conn:
            query = f"""
                SELECT *
                FROM vw_kardex_credito_produto_usuario
                WHERE "DtNow"::date BETWEEN '{data_inicio}' AND '{data_fim}'
            """
            df = pd.read_sql_query(query, conn)
        return df
    except Exception as e:
        st.error(f"Erro ao conectar ao PostgreSQL ou executar query (período): {e}")
        return pd.DataFrame()

# =========================================================
# Preparação de dados
# =========================================================
def prepare_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Padroniza e prepara os dados para uso no app de gamificação.
    Ajustado para a estrutura da view vw_kardex_credito_produto_usuario.
    """
    df = df.copy()

    # Renomear colunas da view para nomes usados no restante da aplicação
    rename_map = {
        "Tipo": "tipo",
        "Grupo": "grupo",
        "DtNow": "data_hora_mov",
        "Curva": "curva",
        "IdUsuario": "id_conferente",
        "Marca": "marca",
        "Qtd": "qtd",
        "Produto": "produto",
        "Empresa": "local",
        "Nome": "conferente",
        "IdProduto": "id_produto",
        "Movimentacoes": "movimentacoes",
    }

    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

    # Conversão de data/hora
    if "data_hora_mov" in df.columns:
        df["data_hora_mov"] = pd.to_datetime(df["data_hora_mov"], errors="coerce")
        df["data"] = df["data_hora_mov"].dt.date
        df["ano"] = df["data_hora_mov"].dt.year
        df["mes"] = df["data_hora_mov"].dt.month

    # Colunas numéricas
    colunas_numericas = [
        "qtd",
        "movimentacoes",
    ]
    for col in colunas_numericas:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # Fator multiplicador: se não existir na view, assume 1
    if "fator_multiplicador" not in df.columns:
        df["fator_multiplicador"] = 1.0
    else:
        df["fator_multiplicador"] = pd.to_numeric(
            df["fator_multiplicador"], errors="coerce"
        ).fillna(1.0)

    # Colunas de texto
    colunas_texto = [
        "tipo",
        "grupo",
        "local",
        "conferente",
        "produto",
        "marca",
        "curva",
        "operacao",  # pode não existir, mas mantemos por compatibilidade com pesos
    ]
    for col in colunas_texto:
        if col in df.columns:
            df[col] = (
                df[col]
                .astype(str)
                .str.strip()
                .str.upper()
            )

    return df

# =========================================================
# Cache de dados para o dashboard de corrida (TTL e retorno de linhas)
# =========================================================
@st.cache_data(ttl=60, show_spinner="Carregando dados mais recentes do dia corrente...")
def load_data_cached_incremental(
    current_time: datetime = None,
) -> tuple[pd.DataFrame, int]:
    """
    Carrega apenas os dados do dia corrente da view vw_kardex_credito_produto_usuario,
    aplicando cache com TTL de 60s.
    Retorna:
        tuple[pd.DataFrame, int]: O DataFrame preparado e o número de linhas lidas.
    """
    df = load_data_today()  # Somente dia corrente
    linhas_lidas = len(df)

    if not df.empty:
        df = prepare_data(df)

    return df, linhas_lidas