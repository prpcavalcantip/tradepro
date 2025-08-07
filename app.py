import streamlit as st
from iqoptionapi.stable_api import IQ_Option
import logging
import time
import os
from dotenv import load_dotenv
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

# Configurar logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(message)s')

# Carregar credenciais do .env
load_dotenv()
email = os.getenv("IQ_OPTION_EMAIL")
password = os.getenv("IQ_OPTION_PASSWORD")

# Conectar à IQ Option
Iq = IQ_Option(email, password)

def connect_iqoption():
    check, reason = Iq.connect()
    if not check:
        st.error(f"Falha na conexão com a IQ Option: {reason}")
        return False
    st.success("Conexão com a IQ Option estabelecida")
    return True

# Funções de análise técnica
def calculate_rsi(candles, period=14):
    closes = [c['close'] for c in candles]
    gains = 0
    losses = 0
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        if diff >= 0:
            gains += diff
        else:
            losses -= diff
    avg_gain = gains / period
    avg_loss = losses / period if losses != 0 else 1
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calculate_sma(candles, period=20):
    closes = [c['close'] for c in candles[-period:]]
    return sum(closes) / len(closes)

def detect_candle_pattern(candles):
    last_candle = candles[-1]
    prev_candle = candles[-2]
    if last_candle['close'] > last_candle['open'] and prev_candle['close'] < prev_candle['open']:
        return 'bullish_engulfing'
    elif last_candle['close'] < last_candle['open'] and prev_candle['close'] > prev_candle['open']:
        return 'bearish_engulfing'
    return 'none'

def generate_signal(analysis_data):
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

# Interface do Streamlit
st.set_page_config(page_title="Broker10 Signals Pro", page_icon="📈", layout="centered")
st.title("Broker10 Signals Pro")
st.markdown("Selecione um ativo e timeframe para prever o movimento da próxima vela.")

# Estilização com CSS para aparência moderna
st.markdown("""
    <style>
    .stButton>button {
        background-color: #2563eb;
        color: white;
        font-weight: bold;
        padding: 10px;
        border-radius: 8px;
    }
    .stButton>button:hover {
        background-color: #1e40af;
    }
    .metric-card {
        background-color: #1e293b;
        padding: 10px;
        border-radius: 8px;
    }
    </style>
""", unsafe_allow_html=True)

# Seleção de ativo e timeframe
assets = ['EURUSD', 'BTCUSD', 'ETHUSD', 'GBPUSD']
timeframes = {'1 Minuto': '1m', '5 Minutos': '5m', '15 Minutos': '15m'}
selected_asset = st.selectbox("Ativo", assets)
selected_timeframe = st.selectbox("Timeframe", list(timeframes.keys()))
timeframe_seconds = {'1m': 60, '5m': 300, '15m': 900}[timeframes[selected_timeframe]]

# Botão para gerar sinal
if st.button("Gerar Sinal", disabled=not connect_iqoption()):
    with st.spinner("Analisando padrões..."):
        try:
            # Obter velas
            candles = Iq.get_candles(selected_asset, timeframe_seconds, 111, time.time())
            if not candles:
                st.error("Nenhuma vela retornada")
                st.stop()
            
            # Calcular indicadores
            rsi = calculate_rsi(candles)
            sma = calculate_sma(candles)
            pattern = detect_candle_pattern(candles)
            last_close = candles[-1]['close']
            analysis_data = {'rsi': rsi, 'sma': sma, 'pattern': pattern, 'lastClose': last_close}
            signal = generate_signal(analysis_data)
            
            # Calcular validade do sinal
            valid_until = datetime.fromtimestamp(time.time() + timeframe_seconds).strftime('%H:%M')
            
            # Exibir resultados
            st.subheader("Resultado do Sinal")
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("<div class='metric-card'>", unsafe_allow_html=True)
                st.metric("Ativo", selected_asset)
                st.metric("Sinal", signal['action'].upper(), delta="CALL" if signal['action'] == 'call' else "PUT" if signal['action'] == 'put' else "NEUTRO")
                st.metric("Probabilidade", f"{signal['probability']}%")
                st.markdown("</div>", unsafe_allow_html=True)
            with col2:
                st.markdown("<div class='metric-card'>", unsafe_allow_html=True)
                st.metric("Validade", valid_until)
                st.metric("RSI", f"{rsi:.2f}")
                st.metric("SMA", f"{sma:.4f}")
                st.markdown("</div>", unsafe_allow_html=True)
            
            # Gráfico de velas
            df = pd.DataFrame(candles[-20:])
            df['time'] = pd.to_datetime(df['from'], unit='s')
            fig = go.Figure()
            fig.add_trace(go.Candlestick(
                x=df['time'],
                open=df['open'],
                high=df['high'],
                low=df['low'],
                close=df['close'],
                name='Preço'
            ))
            fig.add_trace(go.Scatter(
                x=df['time'],
                y=[sma] * len(df),
                mode='lines',
                name='SMA',
                line=dict(color='orange')
            ))
            fig.update_layout(
                title=f"{selected_asset} - {selected_timeframe}",
                xaxis_title="Tempo",
                yaxis_title="Preço",
                template="plotly_dark",
                height=400
            )
            st.plotly_chart(fig, use_container_width=True)
            
        except Exception as e:
            st.error(f"Erro ao gerar sinal: {str(e)}")
            logging.error(f"Erro: {str(e)}")

# Botão para executar ordem (opcional, para conta demo)
if st.button("Executar Ordem (Demo)", disabled=not connect_iqoption()):
    amount = 1  # Valor fixo para demo
    expirations_mode = {'1m': 1, '5m': 5, '15m': 15}[timeframes[selected_timeframe]]
    try:
        check, order_id = Iq.buy(amount, selected_asset, signal['action'], expirations_mode)
        if check:
            st.success(f"Ordem executada: ID {order_id}")
            time.sleep(expirations_mode * 60)
            result = Iq.check_win_v2(order_id)
            st.metric("Resultado", f"{'Lucro' if result > 0 else 'Perda' if result < 0 else 'Neutro'}", delta=f"{result:.2f}")
        else:
            st.error("Falha ao executar ordem")
    except Exception as e:
        st.error(f"Erro ao executar ordem: {str(e)}")
