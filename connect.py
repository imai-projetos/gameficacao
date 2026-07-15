import os
import pandas as pd
from dotenv import load_dotenv
import streamlit as st
from datetime import datetime, date
from sqlalchemy import create_engine

# =========================================================
# Conexão básica ao banco (via SQLAlchemy + pg8000)
# =========================================================
def _get_conn_info() -> dict:
    """
    Lê as variáveis de ambiente de conexão com o banco.
    Em ambiente local, carrega do .env se existir.
    Em produção, use env vars/secrets da plataforma.
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
        # Aqui não levantamos uma Exception crua sem contexto
        raise ValueError(
            "Variáveis de ambiente de banco incompletas. "
            "Verifique: DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD."
        )

    return {
        "host": host,
        "port": int(port),
        "database": db_name,
        "user": user,
        "password": password,
    }


def _get_engine():
    """
    Cria um SQLAlchemy Engine usando pg8000 como driver.
    Exemplo de URL: postgresql+pg8000://user:password@host:port/dbname
    """
    info = _get_conn_info()
    user = info["user"]
    password = info["password"]
    host = info["host"]
    port = info["port"]
    db_name = info["database"]

    # Obs: se a senha tiver caracteres especiais, pode ser necessário urlencode,
    # mas assumimos aqui um caso padrão.
    url = f"postgresql+pg8000://{user}:{password}@{host}:{port}/{db_name}"

    # Podem ser passados args extras se a plataforma exigir (pool_pre_ping, etc.)
    engine = create_engine(url)
    return engine


# =========================================================
# Função genérica de carga
# =========================================================
def load_data(filtro: str = "") -> pd.DataFrame:
    """
    Carrega dados da view vw_kardex_credito_produto_usuario com filtro opcional.
    Parâmetros:
        filtro (str): cláusula SQL opcional (WHERE, ORDER BY, etc.).
    Retorna:
        DataFrame com os dados consultados.
    """
    try:
        engine = _get_engine()
    except ValueError as e:
        # Erro de configuração de conexão
        st.error(str(e))
        return pd.DataFrame()

    try:
        base_query = """
            SELECT *
            FROM vw_kardex_credito_produto_usuario
        """
        query = base_query + "\n" + filtro if filtro else base_query
        df = pd.read_sql_query(query, con=engine)
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
    filtro = f"""WHERE "DtNow"::date = '{hoje}'"""
    return load_data(filtro=filtro)


# =========================================================
# Carregar período de datas (para histórico)
# =========================================================
def load_data_periodo(data_inicio: date, data_fim: date) -> pd.DataFrame:
    """
    Carrega dados da view vw_kardex_credito_produto_usuario para um período de datas.
    Considera a coluna DtNow como referência de data/hora.
    Usado pelo histórico (historico.py).
    """
    # Normalização das datas para string YYYY-MM-DD
    di = pd.to_datetime(data_inicio).strftime("%Y-%m-%d")
    df = pd.to_datetime(data_fim).strftime("%Y-%m-%d")

    filtro = f"""
        WHERE "DtNow"::date BETWEEN '{di}' AND '{df}'
    """
    return load_data(filtro=filtro)


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

        # Cria coluna 'data' a partir de data_hora_mov (somente a data)
        df["data"] = df["data_hora_mov"].dt.date

        # Garante que 'data' vire datetime64[ns], amigável para Arrow/Streamlit
        df["data"] = pd.to_datetime(df["data"], errors="coerce")

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
        df["fator_multiplicador"] = (
            pd.to_numeric(df["fator_multiplicador"], errors="coerce")
            .fillna(1.0)
        )

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
# Função de debug/averiguação do DataFrame (opcional)
# =========================================================
def debug_dataframe(df: pd.DataFrame, titulo: str = "Debug DataFrame"):
    """
    Mostra informações úteis sobre o DataFrame dentro do Streamlit,
    para averiguar problemas de tipos/valores antes de st.dataframe.
    """
    st.subheader(titulo)
    st.write("Tipos das colunas:")
    st.write(df.dtypes)

    st.write("Primeiras linhas:")
    st.write(df.head())

    if "data" in df.columns:
        st.write("Coluna 'data' - amostra de valores:")
        st.write(df["data"].head(20))


# =========================================================
# Cache de dados para o dashboard de corrida
# =========================================================
@st.cache_data(ttl=60, show_spinner="Carregando dados mais recentes do dia corrente...")
def load_data_cached_incremental(
    current_time: datetime = None,
) -> tuple[pd.DataFrame, int]:
    """
    Carrega apenas os dados do dia corrente da view vw_kardex_credito_produto_usuario,
    aplicando cache com TTL de 60s.
    Retorna:
        (DataFrame preparado, número de linhas lidas).
    """
    df = load_data_today()  # Somente dia corrente
    linhas_lidas = len(df)

    if df.empty:
        return df, linhas_lidas

    try:
        df = prepare_data(df)
    except Exception as e:
        st.error(f"Erro ao preparar dados: {e}")
        # Retorna DataFrame original para inspeção, se necessário
        return df, linhas_lidas

    return df, linhas_lidas