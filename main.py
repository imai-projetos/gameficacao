import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import base64
import os
from connect import load_data_cached_incremental
from pontuacao import carregar_pesos, calcular_pontos
from streamlit_autorefresh import st_autorefresh
from datetime import datetime
import pytz

# CONFIGURAÇÃO DA PÁGINA
st.set_page_config(
    page_title="Corrida de Carrinhos Operacional",
    layout="wide",
    page_icon="🏎️",
    initial_sidebar_state="collapsed"
)

# CSS para reduzir margens/paddings
st.markdown("""
    <style>
        .block-container {
            padding-top: 1rem;
            padding-bottom: 1rem;
            padding-left: 1rem;
            padding-right: 1rem;
        }
        header[data-testid="stHeader"] {
            margin: 0;
        }
        div.block-container > div:first-child {
            padding-top: 0rem;
        }
        .st-emotion-cache-1ldf02d {
            padding-left: 0.5rem;
            padding-right: 0.5rem;
        }
        .st-emotion-cache-vk3305 {
            padding-left: 0.5rem;
            padding-right: 0.5rem;
        }
    </style>
""", unsafe_allow_html=True)

# Atualiza a cada 60s
st_autorefresh(interval=60 * 1000, key="car_race_refresh")

br_tz = pytz.timezone("America/Sao_Paulo")

st.title("🏎️ Corrida de Carrinhos Operacional")
status_placeholder = st.empty()
st.write("")

@st.cache_data
def get_image_as_base64(path):
    try:
        with open(path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode()
        if path.lower().endswith(".png"):
            return f"data:image/png;base64,{encoded_string}"
        elif path.lower().endswith(".jpg") or path.lower().endswith(".jpeg"):
            return f"data:image/jpeg;base64,{encoded_string}"
        else:
            return f"data:image/base64,{encoded_string}"
    except FileNotFoundError:
        st.error(f"Erro: A imagem '{path}' não foi encontrada. Por favor, verifique o caminho do arquivo.")
        st.stop()
    except Exception as e:
        st.error(f"Erro ao carregar a imagem: {e}")
        st.stop()

# Função para carregar dados + pontos
def carregar_dados_com_pontos(fator_escala: float = 1.0, current_time: datetime = None) -> tuple[pd.DataFrame, int]:
    """
    Carrega dados (apenas do dia corrente) e aplica os pesos/pontuação.
    Retorna:
        tuple[pd.DataFrame, int]: O DataFrame com os dados e o número de linhas lidas do banco.
    """
    df_raw, linhas_lidas = load_data_cached_incremental(current_time=current_time)
    pesos = carregar_pesos()
    df_processed = calcular_pontos(df_raw, pesos, fator_escala_pontos=fator_escala)
    return df_processed, linhas_lidas

# Fator de escala da pontuação
fator_escala_pontos_dashboard = 10.0

now_minute = datetime.now(br_tz).replace(second=0, microsecond=0)

df, linhas_lidas_da_base = carregar_dados_com_pontos(
    fator_escala=fator_escala_pontos_dashboard,
    current_time=now_minute
)

status_placeholder.caption(
    f" 🕒 Última atualização: **{datetime.now(br_tz).strftime('%d/%m/%Y %H:%M:%S')}** "
    f"| 📊 Linhas lidas da base (dia corrente): **{linhas_lidas_da_base:,}**"
)

# TRATAMENTO DE DATAS
if "data_hora_mov" in df.columns:
    df["data"] = pd.to_datetime(df["data_hora_mov"])
    df["dia"] = df["data"].dt.date
else:
    df["dia"] = datetime.now(br_tz).date()

# FILTROS LATERAIS (filial / empresa)
st.sidebar.header("🏁 Pista de Corrida")
if "local" in df.columns:
    filiais = sorted(df["local"].dropna().unique())
else:
    filiais = []

if filiais:
    filial_sel = st.sidebar.multiselect("Selecione a Filial", filiais, default=filiais)
    df_filtro = df[df["local"].isin(filial_sel)]
else:
    st.sidebar.write("Nenhuma filial encontrada.")
    df_filtro = df.copy()

if df_filtro.empty:
    st.warning("Nenhum dado encontrado para a filial selecionada no dia de hoje. Tente outra filial!")
    st.stop()

# RANKING GERAL (Pódio)
st.subheader("🏆 Pódio da Corrida")
ranking = (
    df_filtro
    .groupby("conferente", as_index=False)
    .agg(
        pontos_totais=("pontos", "sum"),
        movimentacoes=("pontos", "count"),  # mantendo a lógica original (contagem de linhas)
        quantidade=("qtd", "sum")
    )
    .sort_values("pontos_totais", ascending=False)
)
ranking["pontos_totais"] = ranking["pontos_totais"].round(0)

col_podium_2, col_podium_1, col_podium_3 = st.columns([1, 1.5, 1])

pos1 = ranking.iloc[0] if len(ranking) > 0 else None
pos2 = ranking.iloc[1] if len(ranking) > 1 else None
pos3 = ranking.iloc[2] if len(ranking) > 2 else None

# --- 2º Lugar ---
with col_podium_2:
    if pos2 is not None:
        st.markdown(f"""
            <div style='background-color:#c0c0c0; padding: 10px; border-radius: 5px; text-align: center; margin-top: 30px; height: 120px; display: flex; flex-direction: column; justify-content: center; color: black;'>
                <span style='font-size: 1.5em;'>🥈</span>
                <p style='margin: 0; font-weight: bold;'>{pos2['conferente']}</p>
                <p style='margin: 0; font-size: 1.2em;'>{int(pos2['pontos_totais']):,} pts</p>
                <p style='margin: 0; font-size: 0.9em;'>{pos2['movimentacoes']} mov.</p>
            </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
            <div style='background-color:#f0f0f0; padding: 10px; border-radius: 5px; text-align: center; margin-top: 30px; height: 120px; display: flex; flex-direction: column; justify-content: center; color: #888;'>
                <span style='font-size: 1.5em;'>🥈</span>
                <p style='margin: 0;'>N/A</p>
            </div>
        """, unsafe_allow_html=True)

# --- 1º Lugar ---
with col_podium_1:
    if pos1 is not None:
        st.markdown(f"""
            <div style='background-color:#ffd700; padding: 10px; border-radius: 5px; text-align: center; height: 150px; display: flex; flex-direction: column; justify-content: center; color: black;'>
                <span style='font-size: 1.8em;'>🥇</span>
                <p style='margin: 0; font-weight: bold;'>{pos1['conferente']}</p>
                <p style='margin: 0; font-size: 1.4em;'>{int(pos1['pontos_totais']):,} pts</p>
                <p style='margin: 0; font-size: 1.0em;'>{pos1['movimentacoes']} mov.</p>
            </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
            <div style='background-color:#f0f0f0; padding: 10px; border-radius: 5px; text-align: center; height: 150px; display: flex; flex-direction: column; justify-content: center; color: #888;'>
                <span style='font-size: 1.8em;'>🥇</span>
                <p style='margin: 0;'>N/A</p>
            </div>
        """, unsafe_allow_html=True)

# --- 3º Lugar ---
with col_podium_3:
    if pos3 is not None:
        st.markdown(f"""
            <div style='background-color:#cd7f32; padding: 10px; border-radius: 5px; text-align: center; margin-top: 50px; height: 100px; display: flex; flex-direction: column; justify-content: center; color: black;'>
                <span style='font-size: 1.3em;'>🥉</span>
                <p style='margin: 0; font-weight: bold;'>{pos3['conferente']}</p>
                <p style='margin: 0; font-size: 1.1em;'>{int(pos3['pontos_totais']):,} pts</p>
                <p style='margin: 0; font-size: 0.8em;'>{pos3['movimentacoes']} mov.</p>
            </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
            <div style='background-color:#f0f0f0; padding: 10px; border-radius: 5px; text-align: center; margin-top: 50px; height: 100px; display: flex; flex-direction: column; justify-content: center; color: #888;'>
                <span style='font-size: 1.3em;'>🥉</span>
                <p style='margin: 0;'>N/A</p>
            </div>
        """, unsafe_allow_html=True)

# GRÁFICO DE CORRIDA DE CARRINHOS
if not ranking.empty:
    ranking_sorted = ranking.sort_values("pontos_totais", ascending=True).reset_index(drop=True)
    ranking_sorted["y_pos"] = ranking_sorted.index + 1

    fig = go.Figure()

    # CONFIGURAÇÃO DAS IMAGENS DOS CARROS
    default_car_image_path = "carro_corrida.png"
    car_image_paths_list = [
        "carro_azul.png",
        "carro_verde.png",
        "carro_laranja.png",
        "carro_vermelho.png",
        "carro_amarelo.png",
    ]

    valid_car_image_paths = [path for path in car_image_paths_list if os.path.exists(path)]
    if not valid_car_image_paths:
        st.warning(f"Nenhuma imagem de carro encontrada nos caminhos especificados. Usando '{default_car_image_path}' como fallback.")
        if not os.path.exists(default_car_image_path):
            st.error(f"Erro: A imagem padrão '{default_car_image_path}' também não foi encontrada. Por favor, verifique os arquivos de imagem.")
            st.stop()
        valid_car_image_paths = [default_car_image_path]

    car_images_base64 = []
    for path in valid_car_image_paths:
        car_images_base64.append(get_image_as_base64(path))

    # Trace invisível, só para hover e estrutura
    fig.add_trace(go.Scatter(
        x=ranking_sorted["pontos_totais"],
        y=ranking_sorted["y_pos"],
        mode="markers",
        marker=dict(symbol="circle", size=1, opacity=0),
        text=[
            f"<b>{row['conferente']}</b> - Pontos: {int(row['pontos_totais']):,} - Mov.: {int(row['movimentacoes']):,}"
            for _, row in ranking_sorted.iterrows()
        ],
        hoverinfo="text",
        hovertext=[
            f"Conferente: {row['conferente']}<br>Pontos: {int(row['pontos_totais']):,}<br>Voltas: {row['movimentacoes']}"
            for _, row in ranking_sorted.iterrows()
        ],
        showlegend=False
    ))

    images = []
    annotations = []

    fixed_car_width_ratio = 0.08
    fixed_car_height_ratio = 0.8

    max_x_value = ranking_sorted["pontos_totais"].max() if not ranking_sorted.empty else 100

    fixed_car_width_in_x_units = max_x_value * fixed_car_width_ratio
    fixed_car_height_in_y_units = fixed_car_height_ratio

    text_x_offset = fixed_car_width_in_x_units / 2 + (max_x_value * 0.01)

    for index, row in ranking_sorted.iterrows():
        images.append(
            dict(
                source=car_images_base64[index % len(car_images_base64)],
                xref="x",
                yref="y",
                x=row["pontos_totais"],
                y=row["y_pos"],
                sizex=fixed_car_width_in_x_units,
                sizey=fixed_car_height_in_y_units,
                xanchor="right",
                yanchor="middle",
                layer="above",
                sizing="contain",
                opacity=1
            )
        )

        # RÓTULO IGUAL AO ORIGINAL
        annotations.append(
            dict(
                x=row["pontos_totais"],
                y=row["y_pos"],
                text=f"<b>{row['conferente']}</b> - Pontos: {int(row['pontos_totais']):,} - Mov.: {int(row['movimentacoes']):,}",
                showarrow=False,
                xanchor="left",
                yanchor="bottom",
                font=dict(size=10, color="white"),
                xref="x",
                yref="y",
                xshift=text_x_offset,
                yshift=5
            )
        )

    fig.update_layout(
        title="Pista de Corrida (Pontos Acumulados - Dia Corrente)",
        xaxis_title="Pontos Acumulados",
        yaxis_title="",
        showlegend=False,
        plot_bgcolor="rgba(30,30,30,1)",
        paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(
            showgrid=False,
            zeroline=False,
            range=[-10, max_x_value * 1.25] if not ranking_sorted.empty else [-50, 100]
        ),
        yaxis=dict(
            showgrid=True,
            gridcolor="gray",
            tickmode="array",
            tickvals=ranking_sorted["y_pos"],
            ticktext=ranking_sorted["conferente"],
            tickfont=dict(color="white"),
            range=[0.5, ranking_sorted["y_pos"].max() + 0.5] if not ranking_sorted.empty else [0, 1]
        ),
        height=max(400, len(ranking_sorted) * 60),
        images=images,
        annotations=annotations
    )

    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Nenhum conferente na pista ainda para esta filial no dia de hoje.")