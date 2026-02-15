"""
核心交易哲学 - 拼接到 trade_decision prompt 前
基于多周期结构数据，不做模糊假设
"""

CORE_TRADING_PHILOSOPHY = """
【核心交易哲学：结构驱动，周期共振】

1. **多周期结构优先（Pre-Decision Structure）**：
   - 所有决策必须基于 pre_decision_structure 中的 short_term / mid_term / long_term 数据
   - dominant_cycle、cycle_weights、audit_breakdown 来自 SignalValidation，具有最高参考权重
   - long_term.structural_weight == "veto_only" 时，leverage_extreme 或 crowding 极端可一票否决开仓

2. **执行约束硬门控（Execution Constraint）**：
   - execution_constraint.forbidden_actions 中的动作绝对禁止输出
   - audit_confidence.structural_clarity == "DOMINANT_CONFLICT" 时，禁止 open / aggressive_add / scale_in_small
   - risk_exposure_flags 含 crowding_risk_high 时，禁止 aggressive_add

3. **实战格言**：
   - "结构清晰时顺势，结构冲突时观望。"
   - "执行约束是硬边界，不得以任何理由突破。"
"""
