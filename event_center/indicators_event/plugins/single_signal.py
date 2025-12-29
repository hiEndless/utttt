from event_center.indicators_event.plugins.base import Plugin
import time


class SingleSignal(Plugin):
    name = "single_signal"

    tf_scope = ["1m", "5m", "15m", "30m", "1h", "2h"]
    indicators = ["rsi", "macd", "boll", "williams_r", "mfi", "ma"]
    requires_prev = True

    def generate(self, symbol: str, indicator_view: dict):
        res = []

        for tf in (self.tf_scope or list(indicator_view.keys())):
            vtf = indicator_view.get(tf, {}) or {}
            rsi = vtf.get("rsi") or {}
            macd = vtf.get("macd") or {}
            boll = vtf.get("boll") or {}
            wr = vtf.get("williams_r") or {}
            mfi = vtf.get("mfi") or {}

            rsi_val = rsi.get("rsi14") or rsi.get("value")
            if isinstance(rsi_val, (int, float)):
                if rsi_val < 30:
                    res.append({"plugin": self.name, "symbol": symbol, "tf": tf, "direction": "bullish", "strength": 1,
                                "ts": int(time.time())})
                elif rsi_val > 70:
                    res.append({"plugin": self.name, "symbol": symbol, "tf": tf, "direction": "bearish", "strength": 1,
                                "ts": int(time.time())})

            dif = macd.get("dif")
            dea = macd.get("dea")
            prev_dif = macd.get("prev_dif")
            prev_dea = macd.get("prev_dea")
            if all(isinstance(x, (int, float)) for x in [dif, dea, prev_dif, prev_dea]):
                if dif > dea and prev_dif <= prev_dea:
                    res.append({"plugin": self.name, "symbol": symbol, "tf": tf, "direction": "bullish", "strength": 2,
                                "ts": int(time.time())})
                elif dif < dea and prev_dif >= prev_dea:
                    res.append({"plugin": self.name, "symbol": symbol, "tf": tf, "direction": "bearish", "strength": 2,
                                "ts": int(time.time())})

            bbp = boll.get("percent_b") or boll.get("value")
            if isinstance(bbp, (int, float)):
                if bbp < 0.2:
                    res.append({"plugin": self.name, "symbol": symbol, "tf": tf, "direction": "bullish", "strength": 1,
                                "ts": int(time.time())})
                elif bbp > 0.8:
                    res.append({"plugin": self.name, "symbol": symbol, "tf": tf, "direction": "bearish", "strength": 1,
                                "ts": int(time.time())})

            wr_val = wr.get("williams_r") or wr.get("value")
            if isinstance(wr_val, (int, float)):
                if wr_val < -80:
                    res.append({"plugin": self.name, "symbol": symbol, "tf": tf, "direction": "bullish", "strength": 1,
                                "ts": int(time.time())})
                elif wr_val > -20:
                    res.append({"plugin": self.name, "symbol": symbol, "tf": tf, "direction": "bearish", "strength": 1,
                                "ts": int(time.time())})

            mfi_val = mfi.get("mfi") or mfi.get("value")
            if isinstance(mfi_val, (int, float)):
                if mfi_val < 20:
                    res.append({"plugin": self.name, "symbol": symbol, "tf": tf, "direction": "bullish", "strength": 1,
                                "ts": int(time.time())})
                elif mfi_val > 80:
                    res.append({"plugin": self.name, "symbol": symbol, "tf": tf, "direction": "bearish", "strength": 1,
                                "ts": int(time.time())})

            ma = vtf.get("ma") or {}
            prev_ma = ma.get("prev") or {}
            ma20 = ma.get("ma20")
            ma50 = ma.get("ma50")
            prev_ma20 = (prev_ma or {}).get("ma20")
            prev_ma50 = (prev_ma or {}).get("ma50")
            if all(isinstance(x, (int, float)) for x in [ma20, ma50, prev_ma20, prev_ma50]):
                if ma20 > ma50 and prev_ma20 <= prev_ma50:
                    res.append({"plugin": self.name, "symbol": symbol, "tf": tf, "direction": "bullish", "strength": 2,
                                "ts": int(time.time())})
                elif ma20 < ma50 and prev_ma20 >= prev_ma50:
                    res.append({"plugin": self.name, "symbol": symbol, "tf": tf, "direction": "bearish", "strength": 2,
                                "ts": int(time.time())})

        return res


if __name__ == "__main__":
    indicator_view = {
        "1m": {
            "rsi": {
                "rsi6": 44.38353273122635,
                "rsi12": 45.326485330025456,
                "rsi14": 45.603122774315736,
                "rsi24": 47.14534549313919,
                "prev": {
                    "rsi6": 52.63857881015576,
                    "rsi12": 50.05137422996967,
                    "rsi14": 49.76302180940369,
                    "rsi24": 49.725668837531344
                }
            },
            "macd": {
                "dif": -13.854437824324123,
                "dea": -12.182101316820203,
                "macd": -3.3446730150078388,
                "hist": -1.6723365075039194,
                "prev_dif": -12.320823291447596,
                "prev_dea": -11.764017189944223,
                "prev_macd": -1.1136122030067455,
                "prev_hist": -0.5568061015033727
            },
            "boll": {
                "upper_band": 87324.46917528089,
                "middle_band": 87239.275,
                "lower_band": 87154.0808247191,
                "bandwidth": 0.1953115160136132,
                "percent_b": 0.2736054144968714,
                "prev": {
                    "upper_band": 87326.20107347709,
                    "middle_band": 87242.36,
                    "lower_band": 87158.51892652291,
                    "bandwidth": 0.19220267190637158,
                    "percent_b": 0.4984494473340336
                }
            },
            "williams_r": {
                "williams_r": -78.11831789023773,
                "prev": {
                    "williams_r": -48.61012116892065
                }
            },
            "mfi": {
                "mfi": 41.11497382990592,
                "prev": {
                    "mfi": 44.57908560695001
                }
            },
            "ma": {
                "ma5": 87215.94,
                "ma10": 87227.76999999999,
                "ma20": 87239.275,
                "ma50": 87258.50200000001,
                "ma200": 87146.2085,
                "prev": {
                    "ma5": 87230.98,
                    "ma10": 87226.61000000002,
                    "ma20": 87242.36,
                    "ma50": 87260.81,
                    "ma200": 87144.58299999998
                }
            }
        },
        "5m": {
            "rsi": {
                "rsi6": 41.103455413809655,
                "rsi12": 46.58709001990272,
                "rsi14": 46.4148524276881,
                "rsi24": 44.13227098565042,
                "prev": {
                    "rsi6": 49.063974278972076,
                    "rsi12": 49.89777941251886,
                    "rsi14": 49.06516060311428,
                    "rsi24": 45.381317171031654
                }
            },
            "macd": {
                "dif": -12.403145720891189,
                "dea": -22.123527140067466,
                "macd": 19.440762838352555,
                "hist": 9.720381419176277,
                "prev_dif": -8.926712197106099,
                "prev_dea": -24.553622494861532,
                "prev_macd": 31.253820595510867,
                "prev_hist": 15.626910297755433
            },
            "boll": {
                "upper_band": 87456.2638716551,
                "middle_band": 87212.09,
                "lower_band": 86967.91612834489,
                "bandwidth": 0.5599541798736952,
                "percent_b": 0.4609090033454498,
                "prev": {
                    "upper_band": 87466.63890473676,
                    "middle_band": 87201.075,
                    "lower_band": 86935.51109526324,
                    "bandwidth": 0.6090840158490215,
                    "percent_b": 0.5772412953497482
                }
            },
            "williams_r": {
                "williams_r": -89.9116347569974,
                "prev": {
                    "williams_r": -71.83357879234077
                }
            },
            "mfi": {
                "mfi": 46.057143722475445,
                "prev": {
                    "mfi": 62.69918187327466
                }
            },
            "ma": {
                "ma5": 87234.66,
                "ma10": 87252.61,
                "ma20": 87212.09,
                "ma50": 87217.68,
                "ma200": 88408.9855,
                "prev": {
                    "ma5": 87258.7,
                    "ma10": 87262.31,
                    "ma20": 87201.075,
                    "ma50": 87249.464,
                    "ma200": 88410.343
                }
            }
        },
        "15m": {
            "rsi": {
                "rsi6": 44.315308036289366,
                "rsi12": 39.66779775333194,
                "rsi14": 39.27977408266494,
                "rsi24": 40.07596902474047,
                "prev": {
                    "rsi6": 42.97096671557325,
                    "rsi12": 39.08528346687534,
                    "rsi14": 38.78352229280986,
                    "rsi24": 39.78698191634954
                }
            },
            "macd": {
                "dif": -323.9319488086767,
                "dea": -364.15331487434264,
                "macd": 80.44273213133192,
                "hist": 40.22136606566596,
                "prev_dif": -340.60337190167047,
                "prev_dea": -374.20865639075913,
                "prev_macd": 67.21056897817732,
                "prev_hist": 33.60528448908866
            },
            "boll": {
                "upper_band": 88851.32379628827,
                "middle_band": 87454.39499999999,
                "lower_band": 86057.46620371171,
                "bandwidth": 3.1946451548564965,
                "percent_b": 0.4064393973785454,
                "prev": {
                    "upper_band": 89060.70912781177,
                    "middle_band": 87538.79,
                    "lower_band": 86016.87087218821,
                    "bandwidth": 3.47713083037081,
                    "percent_b": 0.380581696702039
                }
            },
            "williams_r": {
                "williams_r": -29.87886944818258,
                "prev": {
                    "williams_r": -32.044536889758135
                }
            },
            "mfi": {
                "mfi": 46.622133628332826,
                "prev": {
                    "mfi": 32.703696732026884
                }
            },
            "ma": {
                "ma5": 87259.46,
                "ma10": 87177.49,
                "ma20": 87454.39499999999,
                "ma50": 88245.808,
                "ma200": 87912.6745,
                "prev": {
                    "ma5": 87272.36000000002,
                    "ma10": 87156.19,
                    "ma20": 87538.79,
                    "ma50": 88282.94,
                    "ma200": 87914.13650000001
                }
            }
        },
        "30m": {
            "rsi": {
                "rsi6": 40.029689373804196,
                "rsi12": 38.48416125377454,
                "rsi14": 39.13737093137752,
                "rsi24": 42.33711464939956,
                "prev": {
                    "rsi6": 35.76291013230677,
                    "rsi12": 36.43187645649226,
                    "rsi14": 37.38530393330398,
                    "rsi24": 41.30467552158048
                }
            },
            "macd": {
                "dif": -363.8034696263203,
                "dea": -248.17341041367004,
                "macd": -231.2601184253005,
                "hist": -115.63005921265025,
                "prev_dif": -365.93438468524255,
                "prev_dea": -219.26589561050744,
                "prev_macd": -293.3369781494702,
                "prev_hist": -146.6684890747351
            },
            "boll": {
                "upper_band": 89613.70313984348,
                "middle_band": 88024.53,
                "lower_band": 86435.35686015652,
                "bandwidth": 3.61075063926721,
                "percent_b": 0.26080957419313266,
                "prev": {
                    "upper_band": 89672.2224476984,
                    "middle_band": 88096.685,
                    "lower_band": 86521.1475523016,
                    "bandwidth": 3.57683708007492,
                    "percent_b": 0.20759660414737008
                }
            },
            "williams_r": {
                "williams_r": -73.3399528360429,
                "prev": {
                    "williams_r": -77.02205121840191
                }
            },
            "mfi": {
                "mfi": 36.001337753094084,
                "prev": {
                    "mfi": 35.4369829467868
                }
            },
            "ma": {
                "ma5": 87161.48000000001,
                "ma10": 87338.6,
                "ma20": 88024.53,
                "ma50": 88155.416,
                "ma200": 87822.5025,
                "prev": {
                    "ma5": 87152.08,
                    "ma10": 87508.08,
                    "ma20": 88096.685,
                    "ma50": 88172.054,
                    "ma200": 87836.623
                }
            }
        },
        "1h": {
            "rsi": {
                "rsi6": 34.96067939387606,
                "rsi12": 39.88818801221469,
                "rsi14": 41.0739416591037,
                "rsi24": 44.49850746235958,
                "prev": {
                    "rsi6": 36.50089049374643,
                    "rsi12": 40.82094353613109,
                    "rsi14": 41.921793816244225,
                    "rsi24": 45.10198882301848
                }
            },
            "macd": {
                "dif": -170.48846590553876,
                "dea": 39.08181413796546,
                "macd": -419.14056008700845,
                "hist": -209.57028004350423,
                "prev_dif": -124.45728058088571,
                "prev_dea": 91.47438414884151,
                "prev_macd": -431.86332945945446,
                "prev_hist": -215.93166472972723
            },
            "boll": {
                "upper_band": 89797.67729893497,
                "middle_band": 88153.79000000001,
                "lower_band": 86509.90270106505,
                "bandwidth": 3.7295896159086563,
                "percent_b": 0.20874219886594042,
                "prev": {
                    "upper_band": 89779.6394453484,
                    "middle_band": 88174.375,
                    "lower_band": 86569.1105546516,
                    "bandwidth": 3.641113294760287,
                    "percent_b": 0.22410309012738652
                }
            },
            "williams_r": {
                "williams_r": -80.38261224767673,
                "prev": {
                    "williams_r": -77.23729448207752
                }
            },
            "mfi": {
                "mfi": 22.808104708311177,
                "prev": {
                    "mfi": 20.65904441526655
                }
            },
            "ma": {
                "ma5": 87150.18000000001,
                "ma10": 87936.78,
                "ma20": 88153.79000000001,
                "ma50": 87895.716,
                "ma200": 87896.201,
                "prev": {
                    "ma5": 87502.76,
                    "ma10": 88087.9,
                    "ma20": 88174.375,
                    "ma50": 87896.80399999999,
                    "ma200": 87896.756
                }
            }
        },
        "2h": {
            "rsi": {
                "rsi6": 37.11494787840363,
                "rsi12": 43.21986318661578,
                "rsi14": 44.11219634853664,
                "rsi24": 46.332075896824435,
                "prev": {
                    "rsi6": 37.16055941906857,
                    "rsi12": 43.250472835605834,
                    "rsi14": 44.14007926968009,
                    "rsi24": 46.351295756949824
                }
            },
            "macd": {
                "dif": 13.90175758030091,
                "dea": 117.46243783808119,
                "macd": -207.12136051556055,
                "hist": -103.56068025778028,
                "prev_dif": 78.31472559501708,
                "prev_dea": 143.35260790252624,
                "prev_macd": -130.07576461501833,
                "prev_hist": -65.03788230750916
            },
            "boll": {
                "upper_band": 89169.1088007582,
                "middle_band": 87957.625,
                "lower_band": 86746.1411992418,
                "bandwidth": 2.754698755811563,
                "percent_b": 0.22243747725760005,
                "prev": {
                    "upper_band": 89158.14234454987,
                    "middle_band": 87983.95,
                    "lower_band": 86809.75765545013,
                    "bandwidth": 2.6691057733822334,
                    "percent_b": 0.203902855768253
                }
            },
            "williams_r": {
                "williams_r": -77.35643530653202,
                "prev": {
                    "williams_r": -77.23729448207752
                }
            },
            "mfi": {
                "mfi": 31.994836890724216,
                "prev": {
                    "mfi": 36.620116260560906
                }
            },
            "ma": {
                "ma5": 87828.06000000001,
                "ma10": 88149.4,
                "ma20": 87957.625,
                "ma50": 87757.25000000001,
                "ma200": 88562.14100000002,
                "prev": {
                    "ma5": 88127.68000000001,
                    "ma10": 88139.17000000001,
                    "ma20": 87983.95,
                    "ma50": 87805.31800000001,
                    "ma200": 88587.54550000001
                }
            }
        }
    }
    res = SingleSignal().generate("BTCUSDT", indicator_view)
    print(res)
