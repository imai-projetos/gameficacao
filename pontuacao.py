import os
import pandas as pd

# Por padrão, procura pesos.xlsx na raiz do projeto,
# mas pode ser sobrescrito por variável de ambiente.
CAMINHO_PESOS = os.getenv(
    "CAMINHO_PESOS",
    os.path.join(os.getcwd(), "pesos.xlsx")
)

def carregar_pesos() -> dict:
    """
    Carrega e prepara os pesos a partir do arquivo Excel.
    Retorna:
        dict com dataframes para 'local', 'operacao' e 'grupo'.
    """
    if not os.path.exists(CAMINHO_PESOS):
        raise FileNotFoundError(f"Arquivo pesos.xlsx não encontrado em: {CAMINHO_PESOS}")

    pesos = {
        "local": pd.read_excel(CAMINHO_PESOS, sheet_name="local", engine="openpyxl"),
        "operacao": pd.read_excel(CAMINHO_PESOS, sheet_name="operacao", engine="openpyxl"),
        "grupo": pd.read_excel(CAMINHO_PESOS, sheet_name="grupo", engine="openpyxl"),
    }

    # Normalização + garantia de unicidade
    pesos["local"]["local"] = pesos["local"]["local"].astype(str).str.strip().str.upper()
    pesos["operacao"]["operacao"] = pesos["operacao"]["operacao"].astype(str).str.strip().str.upper()
    pesos["grupo"]["grupo"] = pesos["grupo"]["grupo"].astype(str).str.strip().str.upper()

    pesos["local"] = pesos["local"].drop_duplicates(subset=["local"])
    pesos["operacao"] = pesos["operacao"].drop_duplicates(subset=["operacao"])
    pesos["grupo"] = pesos["grupo"].drop_duplicates(subset=["grupo"])

    return pesos

def calcular_pontos(df: pd.DataFrame, pesos: dict, fator_escala_pontos: float = 1.0) -> pd.DataFrame:
    """
    Aplica os pesos e calcula a coluna 'pontos'.
    Em seguida, aplica um fator de escala para reduzir a pontuação, se necessário.
    """
    df = df.copy()

    # Normalização do dataframe principal
    if "local" in df.columns:
        df["local"] = df["local"].astype(str).str.strip().str.upper()
    if "operacao" in df.columns:
        df["operacao"] = df["operacao"].astype(str).str.strip().str.upper()
    else:
        # Caso a nova view não tenha 'operacao', criamos uma coluna default
        df["operacao"] = "PADRAO"

    if "grupo" in df.columns:
        df["grupo"] = df["grupo"].astype(str).str.strip().str.upper()

    # Merge com pesos
    df = df.merge(
        pesos["local"],
        on="local",
        how="left"
    )
    df = df.merge(
        pesos["operacao"],
        on="operacao",
        how="left",
        suffixes=("", "_operacao")
    )
    df = df.merge(
        pesos["grupo"],
        on="grupo",
        how="left",
        suffixes=("", "_grupo")
    )

    # Renomear fatores para clareza
    df = df.rename(columns={
        "fator": "fator_local",
        "fator_operacao": "fator_operacao",
        "fator_grupo": "fator_grupo"
    })

    # Fatores padrão (caso não exista no Excel)
    df["fator_local"] = df["fator_local"].fillna(1)
    df["fator_operacao"] = df["fator_operacao"].fillna(1)
    df["fator_grupo"] = df["fator_grupo"].fillna(1)

    # Garante que qtd e fator_multiplicador existam
    if "qtd" not in df.columns:
        df["qtd"] = 0
    if "fator_multiplicador" not in df.columns:
        df["fator_multiplicador"] = 1.0

    # Cálculo final de pontos
    df["pontos"] = (
        df["qtd"]
        * df["fator_multiplicador"]
        * df["fator_local"]
        * df["fator_operacao"]
        * df["fator_grupo"]
    )

    # Aplicar o fator de escala
    if fator_escala_pontos != 1.0 and fator_escala_pontos != 0:
        df["pontos"] = df["pontos"] / fator_escala_pontos
    elif fator_escala_pontos == 0:
        df["pontos"] = 0

    return df