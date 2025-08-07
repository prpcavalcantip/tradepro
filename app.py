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
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')

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
    if len(closes) < period + 1:
        return 50  # Valor neutro caso haja poucos dados
    deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    gains = [d if d > 0 else 0 for d in deltas]
    losses = [-d if d < 0 else 0 for d in deltas]
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period or 1
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def calculate_sma(candles, period=20):
    closes = [c['close'] for c in candles[-period:]]
    return sum(closes) / len(closes)

def detect_candle_pattern(candles):
    if len(candles) < 2:
        return 'none'
    last = candles[-1]
    prev = candles[-2]
    if last['close'] > last['open'] and prev['close'] < prev['open']:
        return 'bullish_engulfing'
    elif last['close'] < last['open'] and prev['close'] > prev['open']:
        return 'bearish_engulfing'
    return 'none'

def generate_signal(data):
    rsi = data['rsi']
    sma = data['sma']
    pattern = data['pattern']
    close = data['lastClose']
    probability = 50
    action = 'hold'

    if rsi > 70 and pattern == 'bearish_engulfing':
        action, probability = 'put', 75
    elif rsi < 30 and pattern == 'bullish_engulfing':
        action, probability = 'call', 75
    elif rsi > 50 and close > sma:
        action, probability = 'call', 65
    elif rsi < 50 and close < sma:
        action, probability = 'put', 65

    return {'action': action, 'probability': probability}

# Interface
st.set_page_config(page_title="Broker10 Signals Pro", page_icon="📈")
st.title("Broker10 Signals Pro")

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

assets = ['EURUSD', 'BTCUSD', 'ETHUSD', 'GBPUSD']
timeframes = {'1 Minuto': '1m', '5 Minutos': '5m', '15 Minutos': '15m'}
selected_asset = st.selectbox("Ativo", assets)
selected_timeframe = st.selectbox("Timeframe", list(timeframes.keys()))
timeframe_str = timeframes[selected_timeframe]
timeframe_sec = {'1m': 60, '5m': 300, '15m': 900}[timeframe_str]

if st.button("Conectar à IQ Option"):
    connect_iqoption()

if st.button("Gerar Sinal"):
    if not Iq.check_connect():
        st.warning("Não conectado. Clique no botão de conectar acima.")
    else:
        with st.spinner("Analisando..."):
            try:
                candles = Iq.get_candles(selected_asset, timeframe_sec, 111, time.time())
                if not candles:
                    st.error("Nenhuma vela retornada")
                    st.stop()

                rsi = calculate_rsi(candles)
                sma = calculate_sma(candles)
                pattern = detect_candle_pattern(candles)
                last_close = candles[-1]['close']

                data = {'rsi': rsi, 'sma': sma, 'pattern': pattern, 'lastClose': last_close}
                signal = generate_signal(data)

                valid_until = datetime.fromtimestamp(time.time() + timeframe_sec).strftime('%H:%M')

                st.subheader("Resultado do Sinal")
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("<div class='metric-card'>", unsafe_allow_html=True)
                    st.metric("Ativo", selected_asset)
                    st.metric("Sinal", signal['action'].upper())
                    st.metric("Probabilidade", f"{signal['probability']}%")
                    st.markdown("</div>", unsafe_allow_html=True)
                with col2:
                    st.markdown("<div class='metric-card'>", unsafe_allow_html=True)
                    st.metric("Validade", valid_until)
                    st.metric("RSI", f"{rsi:.2f}")
                    st.metric("SMA", f"{sma:.4f}")
                    st.markdown("</div>", unsafe_allow_html=True)

                df = pd.DataFrame(candles[-20:])
                df['time'] = pd.to_datetime(df['from'], unit='s')
                fig = go.Figure()
                fig.add_trace(go.Candlestick(x=df['time'], open=df['open'], high=df['high'],
                                             low=df['low'], close=df['close'], name='Preço'))
                fig.add_trace(go.Scatter(x=df['time'], y=[sma] * len(df),
                                         mode='lines', name='SMA', line=dict(color='orange')))
                fig.update_layout(title=f"{selected_asset} - {selected_timeframe}",
                                  xaxis_title="Tempo", yaxis_title="Preço",
                                  template="plotly_dark", height=400)
                st.plotly_chart(fig, use_container_width=True)
            except Exception as e:
                st.error(f"Erro ao gerar sinal: {str(e)}")
                logging.error(f"Erro: {str(e)}")

if st.button("Executar Backtest"):
    if not Iq.check_connect():
        st.warning("Conecte-se antes de executar o backtest.")
    else:
        try:
            candles = Iq.get_candles(selected_asset, timeframe_sec, 1000, time.time())
            wins = losses = 0
            for i in range(20, len(candles)):
                window = candles[i - 20:i]
                rsi = calculate_rsi(window)
                sma = calculate_sma(window)
                pattern = detect_candle_pattern(window)
                last_close = window[-1]['close']
                signal = generate_signal({'rsi': rsi, 'sma': sma, 'pattern': pattern, 'lastClose': last_close})
                if signal['action'] in ['call', 'put']:
                    actual = 'call' if candles[i]['close'] > candles[i - 1]['close'] else 'put'
                    if signal['action'] == actual:
                        wins += 1
                    else:
                        losses += 1
            total = wins + losses
            accuracy = (wins / total) * 100 if total else 0
            st.success(f"Backtest finalizado: {wins} vitórias, {losses} derrotas ({accuracy:.2f}% de acerto)")
        except Exception as e:
            st.error(f"Erro no backtest: {str(e)}")
            logging.error(str(e))
