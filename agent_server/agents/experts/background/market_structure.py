from agno.agent import Agent
from agno.models.openai import OpenAILike
from agent_server.configs.source import get_agent_config
import os
from agent_server.configs.prompts.market_structure import prompt
from agno.models.message import Message
import json
import asyncio
from agent_server.utils.redis_client import RedisClient
import time
from agent_server.agents.experts.utils import (
    _extract_json_from_text,
    _ensure_json_serializable,
    _json_dumps_safe,
)


class MarketStructureExpert:
    name = "market_structure"

    async def run(self, query: dict, exchange: str, symbol: str) -> str:

        cfg = get_agent_config(self.name)

        model_id = cfg.get("model_id", "deepseek-ai/DeepSeek-V3")
        base_url = cfg.get("llm_base_url")
        api_key = cfg.get("llm_api_key")

        model = OpenAILike(id=model_id, base_url=base_url, api_key=api_key)

        agent = Agent(
            model=model,
            instructions=prompt,
        )

        run_output = await agent.arun(
            Message(role="user", content=json.dumps(query, ensure_ascii=False)),
            stream=False,
            debug_mode=True,
        )
        content = run_output.content
        if isinstance(content, str):
            try:
                final_result = json.loads(content)
            except json.JSONDecodeError:
                extracted = _extract_json_from_text(content)
                if extracted is not None:
                    final_result = extracted
                else:
                    final_result = {"raw": content}
        elif hasattr(content, "model_dump"):
            final_result = content.model_dump(exclude_none=True)
        else:
            final_result = content

        if isinstance(final_result, dict) and isinstance(final_result.get("raw"), str):
            extracted_raw = _extract_json_from_text(final_result["raw"])
            if extracted_raw is not None:
                final_result = extracted_raw

        ts = int(time.time() * 1000)
        if isinstance(final_result, dict):
            final_result["ts"] = ts
        else:
            final_result = {"data": final_result, "ts": ts}

        key = f"background:{exchange}:{symbol}:market_structure"
        value_to_store = _ensure_json_serializable(final_result)
        client = RedisClient()
        await client.set_json(key, value_to_store)

        output = _json_dumps_safe(final_result)
        print(output)
        return output


if __name__ == "__main__":
    expert = MarketStructureExpert()
    query = {
    "symbol": "BTCUSDT",
    "generated_at": 1765352700000,
    "ticker": {},
    "funding_rate": {
      "current": 0.00002777,
      "mean": 0.00002998349999999999,
      "delta": -0.00002666,
      "volatility": 0.000027280332471156616,
      "trend": "down",
      "stability": "stable",
      "bias": "bullish"
    },
    "participant_structure": {
      "globalLongShortAccountRatio": {
        "5m": {
          "current": {
            "long_pct": 0.6308,
            "short_pct": 0.3692,
            "ls_ratio": 1.7086
          },
          "stats": {
            "mean_ls_ratio": 1.7088600000000003,
            "delta_ls_ratio": 0.0014999999999998348,
            "vol_ls_ratio": 0.0023533427761850364
          },
          "trend": {
            "ls_trend": "up",
            "long_trend": "up",
            "short_trend": "down"
          },
          "labels": {
            "bias": "long",
            "strength": "strong",
            "stability": "stable"
          }
        },
        "15m": {
          "current": {
            "long_pct": 0.6308,
            "short_pct": 0.3692,
            "ls_ratio": 1.7086
          },
          "stats": {
            "mean_ls_ratio": 1.7020700000000002,
            "delta_ls_ratio": 0.0021999999999999797,
            "vol_ls_ratio": 0.006385060688826656
          },
          "trend": {
            "ls_trend": "up",
            "long_trend": "up",
            "short_trend": "down"
          },
          "labels": {
            "bias": "long",
            "strength": "strong",
            "stability": "stable"
          }
        },
        "30m": {
          "current": {
            "long_pct": 0.6305,
            "short_pct": 0.3695,
            "ls_ratio": 1.7064
          },
          "stats": {
            "mean_ls_ratio": 1.67328,
            "delta_ls_ratio": -0.0029000000000001247,
            "vol_ls_ratio": 0.03417467548411314
          },
          "trend": {
            "ls_trend": "down",
            "long_trend": "down",
            "short_trend": "up"
          },
          "labels": {
            "bias": "long",
            "strength": "strong",
            "stability": "medium"
          }
        },
        "1h": {
          "current": {
            "long_pct": 0.6309,
            "short_pct": 0.3691,
            "ls_ratio": 1.7093
          },
          "stats": {
            "mean_ls_ratio": 1.58494,
            "delta_ls_ratio": 0.010199999999999987,
            "vol_ls_ratio": 0.09963941879486142
          },
          "trend": {
            "ls_trend": "up",
            "long_trend": "up",
            "short_trend": "down"
          },
          "labels": {
            "bias": "long",
            "strength": "strong",
            "stability": "volatile"
          }
        },
        "2h": {
          "current": {
            "long_pct": 0.6295,
            "short_pct": 0.3705,
            "ls_ratio": 1.6991
          },
          "stats": {
            "mean_ls_ratio": 1.6697600000000001,
            "delta_ls_ratio": 0.058499999999999996,
            "vol_ls_ratio": 0.25306938091273623
          },
          "trend": {
            "ls_trend": "up",
            "long_trend": "up",
            "short_trend": "down"
          },
          "labels": {
            "bias": "long",
            "strength": "strong",
            "stability": "volatile"
          }
        },
        "4h": {
          "current": {
            "long_pct": 0.6213,
            "short_pct": 0.3787,
            "ls_ratio": 1.6406
          },
          "stats": {
            "mean_ls_ratio": 1.9002399999999997,
            "delta_ls_ratio": 0.1443000000000001,
            "vol_ls_ratio": 0.28631634485885243
          },
          "trend": {
            "ls_trend": "up",
            "long_trend": "up",
            "short_trend": "down"
          },
          "labels": {
            "bias": "long",
            "strength": "strong",
            "stability": "volatile"
          }
        },
        "1d": {
          "current": {
            "long_pct": 0.5994,
            "short_pct": 0.4006,
            "ls_ratio": 1.4963
          },
          "stats": {
            "mean_ls_ratio": 1.7691500000000002,
            "delta_ls_ratio": -0.6102999999999998,
            "vol_ls_ratio": 0.2926549665466903
          },
          "trend": {
            "ls_trend": "down",
            "long_trend": "down",
            "short_trend": "up"
          },
          "labels": {
            "bias": "long",
            "strength": "strong",
            "stability": "volatile"
          }
        }
      },
      "takerLongShortRatio": {
        "5m": {
          "current": {
            "long_pct": 0.48889126397776916,
            "short_pct": 0.5111087360222308,
            "ls_ratio": 0.9565
          },
          "stats": {
            "mean_ls_ratio": 0.98977,
            "delta_ls_ratio": -0.6331999999999999,
            "vol_ls_ratio": 0.4722123017127877
          },
          "trend": {
            "ls_trend": "down",
            "long_trend": "flat",
            "short_trend": "flat"
          },
          "labels": {
            "bias": "neutral",
            "strength": "weak",
            "stability": "volatile"
          }
        },
        "15m": {
          "current": {
            "long_pct": 0.3951928316864152,
            "short_pct": 0.6048071683135848,
            "ls_ratio": 0.6534
          },
          "stats": {
            "mean_ls_ratio": 0.93943,
            "delta_ls_ratio": -0.13980000000000004,
            "vol_ls_ratio": 0.2108035422957699
          },
          "trend": {
            "ls_trend": "down",
            "long_trend": "flat",
            "short_trend": "flat"
          },
          "labels": {
            "bias": "short",
            "strength": "strong",
            "stability": "volatile"
          }
        },
        "30m": {
          "current": {
            "long_pct": 0.4275003170268877,
            "short_pct": 0.5724996829731123,
            "ls_ratio": 0.7467
          },
          "stats": {
            "mean_ls_ratio": 1.0067599999999999,
            "delta_ls_ratio": -0.396,
            "vol_ls_ratio": 0.17658880800070856
          },
          "trend": {
            "ls_trend": "down",
            "long_trend": "flat",
            "short_trend": "flat"
          },
          "labels": {
            "bias": "short",
            "strength": "strong",
            "stability": "volatile"
          }
        },
        "1h": {
          "current": {
            "long_pct": 0.5116451386717171,
            "short_pct": 0.488354861328283,
            "ls_ratio": 1.0477
          },
          "stats": {
            "mean_ls_ratio": 1.0226400000000002,
            "delta_ls_ratio": 0.0898000000000001,
            "vol_ls_ratio": 0.15922529949728464
          },
          "trend": {
            "ls_trend": "up",
            "long_trend": "flat",
            "short_trend": "flat"
          },
          "labels": {
            "bias": "neutral",
            "strength": "weak",
            "stability": "volatile"
          }
        },
        "2h": {
          "current": {
            "long_pct": 0.5260043073569318,
            "short_pct": 0.4739956926430681,
            "ls_ratio": 1.1097
          },
          "stats": {
            "mean_ls_ratio": 1.0313199999999998,
            "delta_ls_ratio": 0.05459999999999998,
            "vol_ls_ratio": 0.11617639653178741
          },
          "trend": {
            "ls_trend": "up",
            "long_trend": "flat",
            "short_trend": "flat"
          },
          "labels": {
            "bias": "long",
            "strength": "medium",
            "stability": "volatile"
          }
        },
        "4h": {
          "current": {
            "long_pct": 0.47795084930113163,
            "short_pct": 0.5220491506988685,
            "ls_ratio": 0.9155
          },
          "stats": {
            "mean_ls_ratio": 0.9761799999999999,
            "delta_ls_ratio": -0.06040000000000001,
            "vol_ls_ratio": 0.07377881056840703
          },
          "trend": {
            "ls_trend": "down",
            "long_trend": "flat",
            "short_trend": "flat"
          },
          "labels": {
            "bias": "short",
            "strength": "medium",
            "stability": "volatile"
          }
        },
        "1d": {
          "current": {
            "long_pct": 0.5034648857681931,
            "short_pct": 0.49653511423180685,
            "ls_ratio": 1.014
          },
          "stats": {
            "mean_ls_ratio": 0.9973299999999998,
            "delta_ls_ratio": 0.03159999999999996,
            "vol_ls_ratio": 0.032196481864397025
          },
          "trend": {
            "ls_trend": "up",
            "long_trend": "flat",
            "short_trend": "flat"
          },
          "labels": {
            "bias": "neutral",
            "strength": "weak",
            "stability": "medium"
          }
        }
      },
      "topLongShortPositionRatio": {
        "5m": {
          "current": {
            "long_pct": 0.6964,
            "short_pct": 0.3036,
            "ls_ratio": 2.2936
          },
          "stats": {
            "mean_ls_ratio": 2.29446,
            "delta_ls_ratio": 0.0011999999999998678,
            "vol_ls_ratio": 0.004598357194573867
          },
          "trend": {
            "ls_trend": "up",
            "long_trend": "up",
            "short_trend": "down"
          },
          "labels": {
            "bias": "long",
            "strength": "strong",
            "stability": "stable"
          }
        },
        "15m": {
          "current": {
            "long_pct": 0.6962,
            "short_pct": 0.3038,
            "ls_ratio": 2.2914
          },
          "stats": {
            "mean_ls_ratio": 2.30126,
            "delta_ls_ratio": -0.00019999999999997797,
            "vol_ls_ratio": 0.006368882685893016
          },
          "trend": {
            "ls_trend": "down",
            "long_trend": "flat",
            "short_trend": "flat"
          },
          "labels": {
            "bias": "long",
            "strength": "strong",
            "stability": "stable"
          }
        },
        "30m": {
          "current": {
            "long_pct": 0.6962,
            "short_pct": 0.3038,
            "ls_ratio": 2.2914
          },
          "stats": {
            "mean_ls_ratio": 2.30889,
            "delta_ls_ratio": -0.0041999999999999815,
            "vol_ls_ratio": 0.011257140943517745
          },
          "trend": {
            "ls_trend": "down",
            "long_trend": "down",
            "short_trend": "up"
          },
          "labels": {
            "bias": "long",
            "strength": "strong",
            "stability": "stable"
          }
        },
        "1h": {
          "current": {
            "long_pct": 0.6966,
            "short_pct": 0.3034,
            "ls_ratio": 2.2956
          },
          "stats": {
            "mean_ls_ratio": 2.30721,
            "delta_ls_ratio": -0.00690000000000035,
            "vol_ls_ratio": 0.010750757079284166
          },
          "trend": {
            "ls_trend": "down",
            "long_trend": "down",
            "short_trend": "up"
          },
          "labels": {
            "bias": "long",
            "strength": "strong",
            "stability": "stable"
          }
        },
        "2h": {
          "current": {
            "long_pct": 0.6972,
            "short_pct": 0.3028,
            "ls_ratio": 2.3025
          },
          "stats": {
            "mean_ls_ratio": 2.28861,
            "delta_ls_ratio": -0.013599999999999834,
            "vol_ls_ratio": 0.036625171975326186
          },
          "trend": {
            "ls_trend": "down",
            "long_trend": "down",
            "short_trend": "up"
          },
          "labels": {
            "bias": "long",
            "strength": "strong",
            "stability": "medium"
          }
        },
        "4h": {
          "current": {
            "long_pct": 0.6984,
            "short_pct": 0.3016,
            "ls_ratio": 2.3161
          },
          "stats": {
            "mean_ls_ratio": 2.30422,
            "delta_ls_ratio": 0.022400000000000198,
            "vol_ls_ratio": 0.031756672089849426
          },
          "trend": {
            "ls_trend": "up",
            "long_trend": "up",
            "short_trend": "down"
          },
          "labels": {
            "bias": "long",
            "strength": "strong",
            "stability": "medium"
          }
        },
        "1d": {
          "current": {
            "long_pct": 0.6964,
            "short_pct": 0.3036,
            "ls_ratio": 2.2937
          },
          "stats": {
            "mean_ls_ratio": 2.2099800000000003,
            "delta_ls_ratio": -0.05259999999999998,
            "vol_ls_ratio": 0.08337563992757915
          },
          "trend": {
            "ls_trend": "down",
            "long_trend": "down",
            "short_trend": "up"
          },
          "labels": {
            "bias": "long",
            "strength": "strong",
            "stability": "volatile"
          }
        }
      },
      "topLongShortAccountRatio": {
        "5m": {
          "current": {
            "long_pct": 0.6738,
            "short_pct": 0.3262,
            "ls_ratio": 2.0656
          },
          "stats": {
            "mean_ls_ratio": 2.0657900000000002,
            "delta_ls_ratio": 0.0008999999999996788,
            "vol_ls_ratio": 0.0024232439231556997
          },
          "trend": {
            "ls_trend": "up",
            "long_trend": "up",
            "short_trend": "down"
          },
          "labels": {
            "bias": "long",
            "strength": "strong",
            "stability": "stable"
          }
        },
        "15m": {
          "current": {
            "long_pct": 0.6738,
            "short_pct": 0.3262,
            "ls_ratio": 2.0656
          },
          "stats": {
            "mean_ls_ratio": 2.0601700000000003,
            "delta_ls_ratio": 0.0027999999999996916,
            "vol_ls_ratio": 0.005197659729788637
          },
          "trend": {
            "ls_trend": "up",
            "long_trend": "up",
            "short_trend": "down"
          },
          "labels": {
            "bias": "long",
            "strength": "strong",
            "stability": "stable"
          }
        },
        "30m": {
          "current": {
            "long_pct": 0.6735,
            "short_pct": 0.3265,
            "ls_ratio": 2.0628
          },
          "stats": {
            "mean_ls_ratio": 2.03355,
            "delta_ls_ratio": -0.0027999999999996916,
            "vol_ls_ratio": 0.03157031833859138
          },
          "trend": {
            "ls_trend": "down",
            "long_trend": "down",
            "short_trend": "up"
          },
          "labels": {
            "bias": "long",
            "strength": "strong",
            "stability": "medium"
          }
        },
        "1h": {
          "current": {
            "long_pct": 0.6738,
            "short_pct": 0.3262,
            "ls_ratio": 2.0656
          },
          "stats": {
            "mean_ls_ratio": 1.92668,
            "delta_ls_ratio": 0.008399999999999963,
            "vol_ls_ratio": 0.12111599398923328
          },
          "trend": {
            "ls_trend": "up",
            "long_trend": "up",
            "short_trend": "down"
          },
          "labels": {
            "bias": "long",
            "strength": "strong",
            "stability": "volatile"
          }
        },
        "2h": {
          "current": {
            "long_pct": 0.6729,
            "short_pct": 0.3271,
            "ls_ratio": 2.0572
          },
          "stats": {
            "mean_ls_ratio": 1.99495,
            "delta_ls_ratio": 0.054199999999999804,
            "vol_ls_ratio": 0.28240457680427206
          },
          "trend": {
            "ls_trend": "up",
            "long_trend": "up",
            "short_trend": "down"
          },
          "labels": {
            "bias": "long",
            "strength": "strong",
            "stability": "volatile"
          }
        },
        "4h": {
          "current": {
            "long_pct": 0.667,
            "short_pct": 0.333,
            "ls_ratio": 2.003
          },
          "stats": {
            "mean_ls_ratio": 2.25554,
            "delta_ls_ratio": 0.19160000000000021,
            "vol_ls_ratio": 0.32504796979317785
          },
          "trend": {
            "ls_trend": "up",
            "long_trend": "up",
            "short_trend": "down"
          },
          "labels": {
            "bias": "long",
            "strength": "strong",
            "stability": "volatile"
          }
        },
        "1d": {
          "current": {
            "long_pct": 0.6443,
            "short_pct": 0.3557,
            "ls_ratio": 1.8114
          },
          "stats": {
            "mean_ls_ratio": 2.1195399999999998,
            "delta_ls_ratio": -0.6693000000000002,
            "vol_ls_ratio": 0.3488560677414111
          },
          "trend": {
            "ls_trend": "down",
            "long_trend": "down",
            "short_trend": "up"
          },
          "labels": {
            "bias": "long",
            "strength": "strong",
            "stability": "volatile"
          }
        }
      }
    },
    "summary": {
      "cross_period_bias": "long",
      "cross_period_stability": "volatile",
      "funding_bias": "bullish",
      "funding_stability": "stable",
      "price_trend_24h": "flat",
      "market_context": "bullish_sentiment",
      "alignment_score": 0.79,
      "notes": "跨周期加权判断为 long，一致性评分 0.79，结构稳定性 volatile。 平均波动 0.125604。"
    }
  }
    asyncio.run(expert.run(query, "binance", query.get("symbol", "")))
