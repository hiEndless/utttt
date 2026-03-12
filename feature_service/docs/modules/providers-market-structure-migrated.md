# providers/market_structure_migrated 模块说明

## 路径

- canonical：`services/feature_service/src/providers/market_structure_migrated/`
- 兼容壳：已在 Batch C 下线


## 功能作用

`market_structure_migrated/` 是结构计算核心目录，承载从旧链路迁移的领域算法实现。

主要子模块：

- `orderbook/`
  - 深度快照读取、滚动窗口统计、风险旗标输出
- `open_interest/`
  - OI 历史分析、参与者推断、结构共识
- `horizons/`
  - 多周期融合、参与者/价格/资金费率背景聚合、趋势语境标签
- `behavioral/`
  - aggTrade 行为聚合，输出行为结构摘要
- `io/`
  - 读取 market_raw / kline 背景数据
- `utils/redis_client.py`
  - Redis 客户端访问入口
- `horizon_schema.py`
  - horizon 配置（interval、weights、window 等）

## 输入输出

- 输入：Redis 中的 market raw 数据、aggtrade 流、kline 背景数据
- 输出：orderbook/open_interest/horizons/behavioral 的结构化结果

## 关键价值

- 将核心结构推断能力在 feature_service 内本地化
- 降低运行时对旧服务包路径依赖

## 当前边界与风险

- 算法复杂度高，规则与阈值较多，维护成本较高。
- 部分模块仍偏“脚本迁移形态”，需要进一步工程化（配置、测试、可观测性）。

## 迭代方向建议

1. 先做“稳定性工程化”：超时、重试、指标、错误分层，不先改算法语义。
2. 将阈值和权重外置配置化，并建立回测/离线评估流程。
3. 按子域补测试：
   - orderbook：窗口边界和异常深度数据
   - open_interest：无数据/跳点/冲突信号
   - horizons：跨周期冲突和低证据场景
   - behavioral：流数据缺口与延迟
4. 拆分纯函数与 IO，提升可测试性和性能分析可见性。
