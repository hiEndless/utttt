from .ema import EMA
from .ma import MA
from .macd import MACD
from .rsi import RSI
from .bollingerband import BollingerBandSignal
from .kdj import KDJ
from .volatility import VolatilitySignal
from .support_resistance import SupportResistance
from .williams import WilliamsR
from .mfi import MFI

def compute_all_indicators(kline_data):
    out = {}
    # EMA
    ema = EMA(kline_data).calculate()
    out["ema"] = ema
    # MA (SMA)
    ma = MA(kline_data).calculate()
    out["ma"] = ma
    # MACD
    macd = MACD(kline_data).calculate()
    out["macd"] = macd
    # RSI
    rsi = RSI(kline_data).calculate()
    out["rsi"] = rsi
    # Bollinger Bands
    boll = BollingerBandSignal(kline_data).calculate()
    out["boll"] = boll
    # KDJ
    kdj = KDJ(kline_data).calculate()
    out["kdj"] = kdj
    # Volatility: ATR / DMI / ADX
    vol = VolatilitySignal(kline_data).calculate()
    out["volatility"] = vol
    # Support/Resistance
    sr = SupportResistance(kline_data).calculate()
    out["support_resistance"] = sr
    # Williams %R
    wr = WilliamsR(kline_data).calculate()
    out["williams_r"] = wr
    # MFI
    mfi = MFI(kline_data).calculate()
    out["mfi"] = mfi
    return out
