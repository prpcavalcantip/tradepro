import streamlit as st
from iqoptionapi.stable_api import IQ_Option
import logging
import time
import os
from dotenv import load_dotenv
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

# --- Configurações Iniciais ---
st.set_page_config(page_title="Broker10 Signals Pro", page_icon="📈", layout="centered")

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')

# Carregar credenciais do .env
load_dotenv()
EMAIL = os.getenv("IQ_OPTION_EMAIL")
PASSWORD = os.getenv("IQ_OPTION_PASSWORD")

# Inicializar o estado da sessão para armazenar o sinal
if 'signal_data' not in st.session_state:
    st.session_state.signal_data = None

# --- Conexão e Funções de Análise (Otimizadas) ---

@st.cache_resource
def get_iq_connection(email, password):
    """Conecta-se à IQ Option e armazena a conexão em cache."""
    logging.info("Tentando conectar à IQ Option...")
    iq_api = IQ_Option(email, password)
    check, reason = iq_api.connect()
    if not check:
        logging.error(f"Falha na conexão: {reason}")
        st.error(f"Falha na conexão com a IQ Option: {reason}")
        return None
    logging.info("Conexão com a IQ Option estabelecida.")
    st.success("Conexão com a IQ Option estabelecida!")
    return iq_api

def calculate_rsi(candles, period=14):
    """Calcula o RSI corretamente usando Pandas."""
    df = pd.DataFrame([{'close': c['close']} for c in candles])
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1] if not rsi.empty else 50 # Retorna 50 se não houver dados

def calculate_sma(candles, period=20):
    """Calcula a SMA para o último ponto."""
    closes = [c['close'] for c in candles[-period:]]
    return sum(closes) / len(closes) if closes else 0

def detect_candle_pattern(candles):
    """Detecta padrões de engolfo de alta ou baixa."""
    if len(candles) < 2:
        return 'none'
    last_candle = candles[-1]
    prev_candle = candles[-2]
    # Engolfo de Alta
    if last_candle['close'] > prev_candle['open'] and last_candle['open'] < prev_candle['close'] and \
       last_candle['close'] > last_candle['open'] and prev_candle['close'] < prev_candle['open']:
        return 'bullish_engulfing'
    # Engolfo de Baixa
    elif last_candle['close'] < prev_candle['open'] and last_candle['open'] > prev_candle['close'] and \
         last_candle['close'] < last_candle['open'] and prev_candle['close'] > prev_candle['open']:
        return 'bearish_engulfing'
    return 'none'

def generate_signal(analysis_data):
    """Gera um sinal com base nos dados de análise."""
    rsi = analysis_data['rsi']
    sma = analysis_data['sma']
    pattern = analysis_data['pattern']
    last_close = analysis_data['lastClose']
    
    probability = 50
    action = 'hold'
    
    if rsi > 70 and pattern == 'bearish_engulfing':
        action = 'put'
        probability = 75
    elif rsi < 30 and pattern == 'bullish_engulfing':
        action = 'call'
        probability = 75
    elif rsi > 50 and last_close > sma:
        action = 'call'
        probability = 65
    elif rsi < 50 and last_close < sma:
        action = 'put'
        probability = 65
        
    return {'action': action, 'probability': probability}

# --- Interface do Streamlit ---
st.title("Broker10 Signals Pro 📈")
st.markdown("Selecione um ativo e timeframe para prever o movimento da próxima vela.")

# Tenta conectar e obter o objeto da API
Iq = get_iq_connection(EMAIL, PASSWORD)

# Se a conexão falhar, desabilita a interface
is_disabled = Iq is None

st.markdown("""
    <style>
    .stButton>button { background-color: #2563eb; color: white; font-weight: bold; padding: 10px; border-radius: 8px; }
    .stButton>button:hover { background-color: #1e40af; }
    .metric-card { background-color: #1e293b; padding: 15px; border-radius: 8px; text-align: center; }
    </style>
""", unsafe_allow_html=True)

# Seleção de ativo e timeframe
col1, col2 = st.columns(2)
with col1:
    assets = ['EURUSD-OTC', 'BTCUSD', 'ETHUSD', 'GBPUSD']
    selected_asset = st.selectbox("Ativo", assets, disabled=is_disabled)
with col2:
    timeframes = {'1 Minuto': 60, '5 Minutos': 300, '15 Minutos': 900}
    selected_timeframe_label = st.selectbox("Timeframe", list(timeframes.keys()), disabled=is_disabled)
    timeframe_seconds = timeframes[selected_timeframe_label]

if st.button("Gerar Sinal", disabled=is_disabled, use_container_width=True):
    with st.spinner("Analisando mercado..."):
        try:
            candles = Iq.get_candles(selected_asset, timeframe_seconds, 100, time.time())
            if not candles or len(candles) < 20:
                st.error("Não foi possível obter dados suficientes dos candles para análise.")
                st.stop()
            
            # Cálculos
            rsi_val = calculate_rsi(candles)
            sma_val = calculate_sma(candles)
            pattern = detect_candle_pattern(candles)
            last_close = candles[-1]['close']
            
            analysis_data = {'rsi': rsi_val, 'sma': sma_val, 'pattern': pattern, 'lastClose': last_close}
            signal = generate_signal(analysis_data)
            
            # Armazenar sinal na sessão
            st.session_state.signal_data = signal
            
            # Exibir resultados
            st.subheader("Resultado da Análise")
            valid_until = datetime.fromtimestamp(time.time() + timeframe_seconds).strftime('%H:%M:%S')

            res1, res2 = st.columns(2)
            with res1:
                st.markdown("<div class='metric-card'>", unsafe_allow_html=True)
                st.metric("Sinal", signal['action'].upper())
                st.metric("Probabilidade", f"{signal['probability']}%")
                st.markdown("</div>", unsafe_allow_html=True)
            with res2:
                st.markdown("<div class='metric-card'>", unsafe_allow_html=True)
                st.metric("Válido até", valid_until)
                st.metric("RSI (14)", f"{rsi_val:.2f}")
                st.markdown("</div>", unsafe_allow_html=True)

            # Gráfico de velas com SMA correta
            df = pd.DataFrame(candles[-50:]) # Pegar mais dados para uma SMA mais limpa
            df['time'] = pd.to_datetime(df['from'], unit='s')
            df['sma'] = df['close'].rolling(window=20).mean() # SMA correta

            fig = go.Figure()
            fig.add_trace(go.Candlestick(x=df['time'], open=df['open'], high=df['high'], low=df['low'], close=df['close'], name='Preço'))
            fig.add_trace(go.Scatter(x=df['time'], y=df['sma'], mode='lines', name='SMA (20)', line=dict(color='orange')))
            fig.update_layout(title=f"Gráfico de {selected_asset} - {selected_timeframe_label}", template="plotly_dark", height=400, margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(fig, use_container_width=True)

        except Exception as e:
            st.error(f"Ocorreu um erro ao gerar o sinal: {e}")
            logging.error(f"Erro em 'Gerar Sinal': {e}")

if st.button("Executar Ordem (Demo)", disabled=is_disabled or st.session_state.signal_data is None, use_container_width=True):
    if st.session_state.signal_data['action'] == 'hold':
        st.warning("Nenhuma ação de compra ou venda foi recomendada. Ordem não executada.")
    else:
        with st.spinner("Executando ordem..."):
            try:
                amount = 1  # Valor fixo para demo
                action = st.session_state.signal_data['action']
                exp_mode = int(timeframe_seconds / 60)
                
                check, order_id = Iq.buy(amount, selected_asset, action, exp_mode)
                
                if check:
                    st.success(f"Ordem de {action.upper()} executada com sucesso! ID: {order_id}")
                    # A verificação do resultado pode ser implementada separadamente
                else:
                    st.error(f"Falha ao executar a ordem de {action.upper()}.")
            
            except Exception as e:
                st.error(f"Ocorreu um erro ao executar a ordem: {e}")
                logging.error(f"Erro em 'Executar Ordem': {e}")
