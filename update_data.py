import os
import pandas as pd
import streamlit as st

from connect import load_data_today, prepare_data

CACHE_DIR = "data"
CACHE_FILE = f"{CACHE_DIR}/dados_logistica.parquet"


def atualizar_dados():
    print("🔄 Iniciando atualização de dados do dia corrente...")

    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)

    # =========================
    # CARREGA CACHE EXISTENTE (do dia corrente)
    # =========================
    if os.path.exists(CACHE_FILE) and os.path.getsize(CACHE_FILE) > 0:
        try:
            dados_atuais = pd.read_parquet(CACHE_FILE)
            dados_atuais = prepare_data(dados_atuais)
        except Exception as e:
            print("⚠️ Erro ao ler Parquet:", e)
            dados_atuais = pd.DataFrame()
    else:
        dados_atuais = pd.DataFrame()

    # =========================
    # CONSULTA DO DIA CORRENTE
    # =========================
    novos_dados = load_data_today()

    if novos_dados.empty:
        print("⚠️ Nenhum dado encontrado para o dia corrente.")
        return

    novos_dados = prepare_data(novos_dados)

    print(f"✅ Registros do dia corrente encontrados: {len(novos_dados)}")

    # =========================
    # CONCATENA E SALVA
    # =========================
    dados_atualizados = pd.concat(
        [dados_atuais, novos_dados],
        ignore_index=True
    )

    dados_atualizados.drop_duplicates(inplace=True)

    dados_atualizados.to_parquet(CACHE_FILE, index=False)

    print("✅ Parquet atualizado com sucesso!")


if __name__ == "__main__":
    atualizar_dados()