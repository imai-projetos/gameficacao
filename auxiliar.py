import pandas as pd
import math

# =========================================================
# Funções auxiliares de tempo/número
# =========================================================
def format_minutes_hhmmss(minutos: float) -> str:
    """
    Converte minutos em formato hh:mm:ss.
    """
    if minutos is None or (isinstance(minutos, float) and math.isnan(minutos)):
        return "-"

    total_seg = int(round(minutos * 60))
    horas = total_seg // 3600
    resto = total_seg % 3600
    mins = resto // 60
    segs = resto % 60
    return f"{horas:02d}:{mins:02d}:{segs:02d}"

def format_int_thousand(n: int) -> str:
    """
    Formata inteiros com ponto como separador de milhar.
    Ex.: 19958 -> '19.958'
    """
    if n is None:
        return "-"
    return f"{n:,}".replace(",", ".")

# =========================================================
# INVENTÁRIO – Métricas
# =========================================================
def inventario_metrics(df: pd.DataFrame) -> dict:
    """
    Métricas gerais de inventário:
    - tempo médio, máximo, mínimo (min)
    - total de processos
    """
    if "tempo_minutos" not in df.columns:
        return {
            "tempo_medio_minutos": 0.0,
            "tempo_max_minutos": 0.0,
            "tempo_min_minutos": 0.0,
            "total_processos": 0,
        }

    df_valid = df.dropna(subset=["tempo_minutos"])
    if df_valid.empty:
        return {
            "tempo_medio_minutos": 0.0,
            "tempo_max_minutos": 0.0,
            "tempo_min_minutos": 0.0,
            "total_processos": 0,
        }

    return {
        "tempo_medio_minutos": df_valid["tempo_minutos"].mean(),
        "tempo_max_minutos": df_valid["tempo_minutos"].max(),
        "tempo_min_minutos": df_valid["tempo_minutos"].min(),
        "total_processos": len(df_valid),
    }

def inventario_ranking_usuarios(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ranking de colaboradores no inventário:
    - processos
    - tempo médio (min)
    - tempo total (min)
    Ordenado por número de processos (mais processos primeiro).
    """
    if "usuario" not in df.columns or "tempo_minutos" not in df.columns:
        return pd.DataFrame()

    ranking = (
        df.dropna(subset=["tempo_minutos"])
        .groupby("usuario", as_index=False)
        .agg(
            processos=("tempo_minutos", "count"),
            tempo_medio_minutos=("tempo_minutos", "mean"),
            tempo_total_minutos=("tempo_minutos", "sum"),
        )
        .sort_values("processos", ascending=False)
    )

    ranking["tempo_medio_minutos"] = ranking["tempo_medio_minutos"].round(4)
    ranking["tempo_total_minutos"] = ranking["tempo_total_minutos"].round(4)
    return ranking

def inventario_ranking_grupos(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ranking de grupos de inventário:
    - processos
    - tempo médio (min)
    Ordenado por número de processos.
    """
    if "descricao_grupo" not in df.columns or "tempo_minutos" not in df.columns:
        return pd.DataFrame()

    ranking = (
        df.dropna(subset=["tempo_minutos"])
        .groupby("descricao_grupo", as_index=False)
        .agg(
            processos=("tempo_minutos", "count"),
            tempo_medio_minutos=("tempo_minutos", "mean"),
        )
        .sort_values("processos", ascending=False)
    )

    ranking["tempo_medio_minutos"] = ranking["tempo_medio_minutos"].round(4)
    return ranking

# =========================================================
# SEPARAÇÃO – Métricas
# =========================================================
def separacao_metrics(df: pd.DataFrame, uso_tempo: str = "separacao") -> dict:
    """
    Métricas gerais de separação:
    - tempo médio, máximo, mínimo (min)
    - total de processos
    uso_tempo:
        "separacao" -> tempo_separacao_minutos
        "coletor"   -> tempo_coletor_minutos
    """
    if uso_tempo == "separacao" and "tempo_separacao_minutos" in df.columns:
        tempo_col = "tempo_separacao_minutos"
    else:
        tempo_col = "tempo_coletor_minutos"

    if tempo_col not in df.columns:
        return {
            "tempo_medio_minutos": 0.0,
            "tempo_max_minutos": 0.0,
            "tempo_min_minutos": 0.0,
            "total_processos": 0,
        }

    df_valid = df.dropna(subset=[tempo_col])
    if df_valid.empty:
        return {
            "tempo_medio_minutos": 0.0,
            "tempo_max_minutos": 0.0,
            "tempo_min_minutos": 0.0,
            "total_processos": 0,
        }

    return {
        "tempo_medio_minutos": df_valid[tempo_col].mean(),
        "tempo_max_minutos": df_valid[tempo_col].max(),
        "tempo_min_minutos": df_valid[tempo_col].min(),
        "total_processos": len(df_valid),
    }

def separacao_ranking_usuarios(df: pd.DataFrame, uso_tempo: str = "separacao") -> pd.DataFrame:
    """
    Ranking de colaboradores na separação:
    - processos
    - tempo médio (min)
    - tempo total (min)
    Ordenado por número de processos.
    """
    if uso_tempo == "separacao" and "tempo_separacao_minutos" in df.columns:
        tempo_col = "tempo_separacao_minutos"
    else:
        tempo_col = "tempo_coletor_minutos"

    if "usuario" not in df.columns or tempo_col not in df.columns:
        return pd.DataFrame()

    ranking = (
        df.dropna(subset=[tempo_col])
        .groupby("usuario", as_index=False)
        .agg(
            processos=(tempo_col, "count"),
            tempo_medio_minutos=(tempo_col, "mean"),
            tempo_total_minutos=(tempo_col, "sum"),
        )
        .sort_values("processos", ascending=False)
    )

    ranking["tempo_medio_minutos"] = ranking["tempo_medio_minutos"].round(4)
    ranking["tempo_total_minutos"] = ranking["tempo_total_minutos"].round(4)
    return ranking

def separacao_ranking_produtos(
    df: pd.DataFrame,
    uso_tempo: str = "separacao",
    top_n: int = 20,
) -> pd.DataFrame:
    """
    Ranking de produtos na separação:
    - processos
    - tempo médio (min)
    Ordenado por número de processos (mais processados primeiro).
    Retorna apenas os 'top_n' primeiros produtos.
    """
    if uso_tempo == "separacao" and "tempo_separacao_minutos" in df.columns:
        tempo_col = "tempo_separacao_minutos"
    else:
        tempo_col = "tempo_coletor_minutos"

    if "produto" not in df.columns or tempo_col not in df.columns:
        return pd.DataFrame()

    ranking = (
        df.dropna(subset=[tempo_col])
        .groupby("produto", as_index=False)
        .agg(
            processos=(tempo_col, "count"),
            tempo_medio_minutos=(tempo_col, "mean"),
        )
        .sort_values("processos", ascending=False)
    )

    ranking["tempo_medio_minutos"] = ranking["tempo_medio_minutos"].round(4)

    # Limitamos ao top_n
    if top_n is not None and top_n > 0:
        ranking = ranking.head(top_n)

    return ranking