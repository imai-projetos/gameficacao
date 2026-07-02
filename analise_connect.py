import os
import pandas as pd
from dotenv import load_dotenv
import psycopg2

# =========================================================
# Conexão básica ao banco
# =========================================================
def _get_conn_info() -> dict:
    load_dotenv()
    return {
        "host": os.getenv("DB_HOST"),
        "port": int(os.getenv("DB_PORT")),
        "dbname": os.getenv("DB_NAME"),
        "user": os.getenv("DB_USER"),
        "password": os.getenv("DB_PASSWORD"),
    }

def _run_query(query: str) -> pd.DataFrame:
    conn_info = _get_conn_info()
    try:
        with psycopg2.connect(**conn_info) as conn:
            df = pd.read_sql_query(query, conn)
        return df
    except Exception as e:
        print(f"Erro ao conectar ao PostgreSQL ou executar query: {e}")
        return pd.DataFrame()

# =========================================================
# INVENTÁRIO
# =========================================================
def load_inventario() -> pd.DataFrame:
    """
    Lê todos os dados da view "vw_InventarioTempoContagem".
    """
    query = 'SELECT * FROM "vw_InventarioTempoContagem"'
    df = _run_query(query)
    print(f"[Inventário] Linhas lidas: {len(df)}")
    return df

def prepare_inventario(df: pd.DataFrame) -> pd.DataFrame:
    """
    Prepara dados de inventário:
    - renomeia colunas
    - converte datas
    - calcula tempo em minutos (DtFim - DtInicio)
    - deriva campo 'data' para filtros (data do início)
    """
    if df.empty:
        return df

    df = df.copy()

    rename_map = {
        "IdGrupoInventario": "id_grupo_inventario",
        "Descricao": "descricao_grupo",
        "DtInicio": "dt_inicio",
        "DtFim": "dt_fim",
        "IdUsuario": "id_usuario",
        "Codigo": "codigo",
        "CriacaoInventario": "criacao_inventario",
        "Usuario": "usuario",
        "CodigoFabricante": "codigo_fabricante",
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

    # Datas
    for col in ["dt_inicio", "dt_fim", "criacao_inventario"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    # Texto
    for col in ["descricao_grupo", "usuario", "codigo", "codigo_fabricante"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    # Tempo de inventário em minutos
    if "dt_inicio" in df.columns and "dt_fim" in df.columns:
        df["tempo_minutos"] = (df["dt_fim"] - df["dt_inicio"]).dt.total_seconds() / 60.0

    # Deriva data para filtros
    if "dt_inicio" in df.columns:
        df["data"] = df["dt_inicio"].dt.date

    print("[Inventário] Colunas após preparação:", df.columns.tolist())
    return df

# =========================================================
# SEPARAÇÃO
# =========================================================
def load_separacao() -> pd.DataFrame:
    """
    Lê todos os dados da view "vw_SeparacaoTempoColetor".
    """
    query = 'SELECT * FROM "vw_SeparacaoTempoColetor"'
    df = _run_query(query)
    print(f"[Separação] Linhas lidas: {len(df)}")
    return df

def prepare_separacao(df: pd.DataFrame) -> pd.DataFrame:
    """
    Prepara dados de separação:
    - renomeia colunas
    - converte datas
    - calcula tempos em minutos:
        tempo_coletor_minutos    = DtFimColetor - DtInicioColetor
        tempo_separacao_minutos  = DtFimColetor - DtInicioSeparacao
    - deriva 'data' para filtros (data do início do coletor)
    """
    if df.empty:
        return df

    df = df.copy()

    rename_map = {
        "IdSeparar": "id_separar",
        "IdUsuario": "id_usuario",
        "DtInicioColetor": "dt_inicio_coletor",
        "DtFimColetor": "dt_fim_coletor",
        "DtInicioSeparacao": "dt_inicio_separacao",
        "Codigo": "codigo",
        "Nome": "usuario",
        "Produto": "produto",
        "CodigoFabricante": "codigo_fabricante",
    }
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})

    # Datas
    for col in ["dt_inicio_coletor", "dt_fim_coletor", "dt_inicio_separacao"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    # Texto
    for col in ["codigo", "usuario", "produto", "codigo_fabricante"]:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    # Tempo coleta (coletor) em minutos
    if "dt_inicio_coletor" in df.columns and "dt_fim_coletor" in df.columns:
        df["tempo_coletor_minutos"] = (df["dt_fim_coletor"] - df["dt_inicio_coletor"]).dt.total_seconds() / 60.0

    # Tempo separação (processo completo) em minutos
    if "dt_inicio_separacao" in df.columns and "dt_fim_coletor" in df.columns:
        df["tempo_separacao_minutos"] = (df["dt_fim_coletor"] - df["dt_inicio_separacao"]).dt.total_seconds() / 60.0

    # Deriva data para filtros
    if "dt_inicio_coletor" in df.columns:
        df["data"] = df["dt_inicio_coletor"].dt.date

    print("[Separação] Colunas após preparação:", df.columns.tolist())
    return df