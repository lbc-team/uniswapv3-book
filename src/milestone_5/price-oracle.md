# 价格预言机

我们将要添加到 DEX 的最后一个机制是*价格预言机*。 即使它对于 DEX 来说不是必需的（有些 DEX 没有实现价格预言机），但它仍然是 Uniswap 的一个重要功能，并且学习起来很有趣。

## 什么是价格预言机？

价格预言机是一种向区块链提供资产价格的机制。 由于区块链是孤立的生态系统，因此无法直接查询外部数据，例如通过 API 从中心化交易所获取资产价格。 另一个非常棘手的问题是数据的有效性和真实性：从交易所获取价格时，你怎么知道它们是真实的？ 你必须信任来源。 但是互联网通常不安全，有时价格可能会被操纵，DNS 记录可能会被劫持，API 服务器可能会崩溃等等。所有这些困难都需要解决，以便我们可以拥有可靠且正确的链上价格。

[Chainlink](https://chain.link/) 是解决上述问题的最早的工作方案之一。 Chainlink 运行一个去中心化的预言机网络，通过 API 从中心化交易所获取资产价格，对其进行平均，并以防篡改的方式在链上提供它们。 Chainlink 是一组合约，其中一个状态变量（资产价格）可以被任何人写（任何其他合约或用户）都可以读取，但只能由预言机写入。

这是看待价格预言机的一种方式。 还有另一种。

如果我们有原生的链上交易所，为什么我们需要从外部获取价格？ 这就是 Uniswap 价格预言机的工作方式。 由于套利和高流动性，Uniswap 上的资产价格接近中心化交易所的价格。 因此，我们可以使用 Uniswap，而不是使用中心化交易所作为资产价格的来源，我们不需要解决与链上数据传输相关的问题（我们也不需要信任数据提供商）。

## Uniswap 价格预言机如何工作

Uniswap 只是保留了所有先前交换价格的记录。 仅此而已。 但是，Uniswap 不是跟踪实际价格，而是跟踪*累积价格*，它是池合约历史记录中每秒价格的总和。

$$a_{i} = \sum_{i=1}^t p_{i}$$

这种方法使我们能够通过简单地获取两个时间点（$t_1$ 和 $t_2$）的累积价格（$a_{t_1}$ 和 $a_{t_2}$），将一个时间点的累积价格减去另一个时间点的累积价格，然后除以两个时间点之间的秒数，来找到两个时间点之间的*时间加权平均价格*：

$$p_{t_1,t_2} = \frac{a_{t_2} - a_{t_1}}{t_2 - t_1}$$

这就是它在 Uniswap V2 中的工作方式。 在 V3 中，它略有不同。 累积价格是当前的 tick（它是价格的 $log_{1.0001}$）：

$$a_{i} = \sum_{i=1}^t log_{1.0001}P(i)$$

并且不是对价格求平均，而是取*几何平均数*：

$$ P_{t_1,t_2} = \left( \prod_{i=t_1}^{t_2} P_i \right) ^ \frac{1}{t_2-t_1} $$

为了找到两个时间点之间的时间加权几何平均价格，我们获取这些时间点的累积值，将一个时间点的累积值减去另一个时间点的累积值，除以这两个时间点之间的秒数，然后计算 $1.0001^{x}$：

$$ log_{1.0001}{(P_{t_1,t_2})} = \frac{\sum_{i=t_1}^{t_2} log_{1.0001}(P_i)}{t_2-t_1}$$
$$ = \frac{a_{t_2} - a_{t_1}}{t_2-t_1}$$

$$P_{t_1,t_2} = 1.0001^{\frac{a_{t_2} - a_{t_1}}{t_2-t_1}}$$

Uniswap V2 不存储历史累积价格，这需要参考第三方区块链数据索引服务才能在计算平均价格时找到历史价格。 另一方面，Uniswap V3 允许存储多达 65,535 个历史累积价格，这使得计算任何历史时间加权几何平均价格变得更加容易。

## 价格操纵缓解

另一个重要的话题是价格操纵以及它在 Uniswap 中如何缓解。

理论上，可以操纵池的价格来获得优势：例如，购买大量代币来提高其价格，并在使用 Uniswap 价格预言机的第三方 DeFi 服务上获利，然后将代币交易回真实价格。 为了减轻此类攻击，Uniswap 会跟踪**在一个区块结束时**的价格以及该区块的*最后*一笔交易**之后的**的价格。 这消除了区块内价格操纵的可能性。

从技术上讲，Uniswap 预言机中的价格会在每个区块的开头更新，并且每个价格都会在该区块中的第一笔交换交易之前计算。

## 价格预言机实现

好了，让我们开始编写代码。

### 观察值和基数

我们将首先创建 `Oracle` 库合约和 `Observation` 结构：

```solidity
// src/lib/Oracle.sol
library Oracle {
    struct Observation {
        uint32 timestamp;
        int56 tickCumulative;
        bool initialized;
    }
    ...
}
```

*观察值*是一个存储记录价格的槽。 它存储一个价格、记录该价格的时间戳，以及在观察值被激活时设置为 `true` 的 `initialized` 标志（默认情况下并非所有观察值都被激活）。 一个池合约最多可以存储 65,535 个观察值：

```solidity
// src/UniswapV3Pool.sol
contract UniswapV3Pool is IUniswapV3Pool {
    using Oracle for Oracle.Observation[65535];
    ...
    Oracle.Observation[65535] public observations;
}
```

但是，由于存储那么多 `Observation` 实例需要大量 gas（有人必须为将每个实例写入合约的存储空间付费），因此默认情况下，一个池只能存储 1 个观察值，每次记录新价格时，该观察值都会被覆盖。 可以随时由愿意为此付费的任何人增加已激活的观察值的数量（观察值的*基数*）。 为了管理基数，我们需要一些额外的状态变量：
```solidity
    ...
    struct Slot0 {
        // Current sqrt(P)
        uint160 sqrtPriceX96;
        // Current tick
        int24 tick;
        // Most recent observation index
        uint16 observationIndex;
        // Maximum number of observations
        uint16 observationCardinality;
        // Next maximum number of observations
        uint16 observationCardinalityNext;
    }
    ...
```

- `observationIndex` 跟踪最近观察值的索引；
- `observationCardinality` 跟踪已激活的观察值的数量；
- `observationCardinalityNext` 跟踪观察值数组可以扩展到的下一个基数。

观察值存储在一个固定长度的数组中，当保存新的观察值并且 `observationCardinalityNext` 大于 `observationCardinality` 时，该数组会扩展（这表示可以扩展基数）。 如果该数组无法扩展（下一个基数值等于当前值），则最旧的观察值会被覆盖，即观察值存储在索引 0 处，下一个观察值存储在索引 1 处，依此类推。

创建池时，`observationCardinality` 和 `observationCardinalityNext` 将设置为 1：
```solidity
// src/UniswapV3Pool.sol
contract UniswapV3Pool is IUniswapV3Pool {
    function initialize(uint160 sqrtPriceX96) public {
        ...

        (uint16 cardinality, uint16 cardinalityNext) = observations.initialize(
            _blockTimestamp()
        );

        slot0 = Slot0({
            sqrtPriceX96: sqrtPriceX96,
            tick: tick,
            observationIndex: 0,
            observationCardinality: cardinality,
            observationCardinalityNext: cardinalityNext
        });
    }
}
```

```solidity
// src/lib/Oracle.sol
library Oracle {
    ...
    function initialize(Observation[65535] storage self, uint32 time)
        internal
        returns (uint16 cardinality, uint16 cardinalityNext)
    {
        self[0] = Observation({
            timestamp: time,
            tickCumulative: 0,
            initialized: true
        });

        cardinality = 1;
        cardinalityNext = 1;
    }
    ...
}
```

### 写入观察值

在 `swap` 函数中，当当前价格发生变化时，会将观察值写入观察值数组：

```solidity
// src/UniswapV3Pool.sol
contract UniswapV3Pool is IUniswapV3Pool {
    function swap(...) public returns (...) {
        ...
        if (state.tick != slot0_.tick) {
            (
                uint16 observationIndex,
                uint16 observationCardinality
            ) = observations.write(
                    slot0_.observationIndex,
                    _blockTimestamp(),
                    slot0_.tick,
                    slot0_.observationCardinality,
                    slot0_.observationCardinalityNext
                );
            
            (
                slot0.sqrtPriceX96,
                slot0.tick,
                slot0.observationIndex,
                slot0.observationCardinality
            ) = (
                state.sqrtPriceX96,
                state.tick,
                observationIndex,
                observationCardinality
            );
        }
        ...
    }
}
```

请注意，此处观察到的 tick 是 `slot0_.tick`（而不是 `state.tick`），即交换之前的价格！ 它会在下一个语句中使用新价格更新。 这就是我们之前讨论过的价格操纵缓解：Uniswap 跟踪一个区块中**第一笔**交易**之前**的价格以及**上一个**区块中**最后**一笔交易**之后**的价格。

另请注意，每个观察值都由 `_blockTimestamp()` 标识，即当前的区块时间戳。 这意味着如果当前区块已经有一个观察值，则不会记录价格。 如果当前区块没有观察值（即这是区块中的第一笔交换交易），则会记录价格。 这是价格操纵缓解机制的一部分。

```solidity
// src/lib/Oracle.sol
function write(
    Observation[65535] storage self,
    uint16 index,
    uint32 timestamp,
    int24 tick,
    uint16 cardinality,
    uint16 cardinalityNext
) internal returns (uint16 indexUpdated, uint16 cardinalityUpdated) {
    Observation memory last = self[index];

    if (last.timestamp == timestamp) return (index, cardinality);

    if (cardinalityNext > cardinality && index == (cardinality - 1)) {
        cardinalityUpdated = cardinalityNext;
    } else {
        cardinalityUpdated = cardinality;
    }

    indexUpdated = (index + 1) % cardinalityUpdated;
    self[indexUpdated] = transform(last, timestamp, tick);
}
```

在这里，我们看到如果在当前区块中已经进行了观察，则会跳过观察。 但是，如果没有这样的观察，我们会保存一个新的观察，并尝试在可能的情况下扩展基数。 模运算符 (`%`) 确保观察索引保持在 $[0, cardinality)$ 范围内，并在达到上限时重置为 0。

现在，让我们看一下 `transform` 函数：

```solidity
function transform(
    Observation memory last,
    uint32 timestamp,
    int24 tick
) internal pure returns (Observation memory) {
    uint56 delta = timestamp - last.timestamp;

    return
        Observation({
            timestamp: timestamp,
            tickCumulative: last.tickCumulative +
                int56(tick) *
                int56(delta),
            initialized: true
        });
}
```

我们在这里计算的是累积价格：当前 tick 乘以自上次观察以来的秒数，并添加到上次累积的价格中。

### 增加基数

现在让我们看看如何扩展基数。

任何人都可以在任何时间增加池的观察值的基数，并支付执行该操作所需的 gas。 为此，我们将向 Pool 合约添加一个新的公共函数：

```solidity
// src/UniswapV3Pool.sol
function increaseObservationCardinalityNext(
    uint16 observationCardinalityNext
) public {
    uint16 observationCardinalityNextOld = slot0.observationCardinalityNext;
    uint16 observationCardinalityNextNew = observations.grow(
        observationCardinalityNextOld,
        observationCardinalityNext
    );

    if (observationCardinalityNextNew != observationCardinalityNextOld) {
        slot0.observationCardinalityNext = observationCardinalityNextNew;
        emit IncreaseObservationCardinalityNext(
            observationCardinalityNextOld,
            observationCardinalityNextNew
        );
    }
}
```

并在 Oracle 中添加一个新函数：

```solidity
// src/lib/Oracle.sol
function grow(
    Observation[65535] storage self,
    uint16 current,
    uint16 next
) internal returns (uint16) {
    if (next <= current) return current;

    for (uint16 i = current; i < next; i++) {
        self[i].timestamp = 1;
    }

    return next;
}
```

在 `grow` 函数中，我们通过将每个观察值的 `timestamp` 字段设置为一些非零值来分配新的观察值。 请注意，`self` 是一个存储变量，将值分配给它的元素会更新数组计数器并将值写入合约的存储空间。

### 读取观察值

我们终于来到了本章中最棘手的部分：读取观察值。 在继续操作之前，让我们回顾一下观察值的存储方式，以便更好地了解。

观察值存储在一个可以扩展的固定长度的数组中：

![观察值数组](images/observations.png)

正如我们在上面所指出的，观察值预计会溢出：如果新的观察值不适合该数组，则写入将从索引 0 处开始继续写入，即最旧的观察值会被覆盖：

![观察值换行](images/observations_wrapping.png)

不能保证每个区块都会存储一个观察值，因为并非每个区块都会发生交换。 因此，有些区块不会记录观察值，并且这种缺少观察值的时期可能会很长。 当然，我们不希望预言机报告的价格出现差距，这就是我们使用时间加权平均价格 (TWAP) 的原因——这样我们就可以在没有观察值的时期内获得平均价格。 TWAP 允许我们*插值*价格，即在两个观察值之间画一条线——该线上的每个点都是两个
观察值之间特定时间戳的价格。

![内插价格](images/interpolated_prices.png)

因此，读取观察值意味着按时间戳查找观察值并内插缺失的观察值，同时考虑到允许观察值数组溢出（例如，最旧的观察值可以在数组中位于最近的观察值之后）。 因为我们没有按时间戳索引观察值（为了节省 gas），所以我们需要使用[二分搜索算法](https://en.wikipedia.org/wiki/Binary_search_algorithm)进行高效搜索。 但并非总是如此。

让我们将其分解为更小的步骤，并首先在 `Oracle` 中实现 `observe` 函数：

```solidity
function observe(
    Observation[65535] storage self,
    uint32 time,
    uint32[] memory secondsAgos,
    int24 tick,
    uint16 index,
    uint16 cardinality
) internal view returns (int56[] memory tickCumulatives) {
    tickCumulatives = new int56[](secondsAgos.length);

    for (uint256 i = 0; i < secondsAgos.length; i++) {
        tickCumulatives[i] = observeSingle(
            self,
            time,
            secondsAgos[i],
            tick,
            index,
            cardinality
        );
    }
}
```

该函数采用当前区块时间戳，我们想要获取价格的时间点列表 (`secondsAgo`)、当前 tick、观察索引和基数。

移动到 `observeSingle` 函数：

```solidity
function observeSingle(
    Observation[65535] storage self,
    uint32 time,
    uint32 secondsAgo,
    int24 tick,
    uint16 index,
    uint16 cardinality
) internal view returns (int56 tickCumulative) {
    if (secondsAgo == 0) {
        Observation memory last = self[index];
        if (last.timestamp != time) last = transform(last, time, tick);
        return last.tickCumulative;
    }
    ...
}
```

当请求最近的观察值（过去了 0 秒）时，我们可以立即返回它。 如果它没有记录在当前区块中，则转换它以考虑当前区块和当前 tick。

如果请求较旧的时间点，我们需要在切换到二分搜索算法之前进行多次检查：
1. 如果请求的时间点是最后一个观察值，我们可以返回最新观察值的累积价格；
1. 如果请求的时间点在最后一个观察值之后，我们可以调用 `transform` 来找到此时的累积价格，了解最后一个观察到的价格和当前价格；
1. 如果请求的时间点在最后一个观察值之前，我们必须使用二分搜索。

让我们直接进入第三点：
```solidity
function binarySearch(
    Observation[65535] storage self,
    uint32 time,
    uint32 target,
    uint16 index,
    uint16 cardinality
)
    private
    view
    returns (Observation memory beforeOrAt, Observation memory atOrAfter)
{
    ...
```

该函数采用当前区块时间戳 (`time`)、请求的价格点的时间戳 (`target`)，以及当前的观察索引和基数。 它返回请求的时间点所在的两个观察值之间的范围。

要初始化二分搜索算法，我们设置边界：
```solidity
uint256 l = (index + 1) % cardinality; // oldest observation
uint256 r = l + cardinality - 1; // newest observation
uint256 i;
```

回想一下，观察值数组预计会溢出，这就是我们在此处使用模运算符的原因。

然后我们启动一个无限循环，在其中我们检查范围的中间点：如果它没有初始化（没有观察值），我们继续下一个点：

```solidity
while (true) {
    i = (l + r) / 2;

    beforeOrAt = self[i % cardinality];

    if (!beforeOrAt.initialized) {
        l = i + 1;
        continue;
    }

    ...
```

如果该点被初始化，我们称它为我们希望请求的时间点包含的范围的左边界。 我们正在尝试找到右边界 (`atOrAfter`)：

```solidity
    ...
    atOrAfter = self[(i + 1) % cardinality];

    bool targetAtOrAfter = lte(time, beforeOrAt.timestamp, target);

    if (targetAtOrAfter && lte(time, target, atOrAfter.timestamp))
        break;
    ...
```
如果我们找到了边界，我们会返回它们。 如果没有，我们继续搜索：

```solidity
    ...
    if (!targetAtOrAfter) r = i - 1;
    else l = i + 1;
}
```

在找到请求的时间点所属的观察值范围后，我们需要计算请求时间点的价格：
```solidity
// function observeSingle() {
    ...
    uint56 observationTimeDelta = atOrAfter.timestamp -
        beforeOrAt.timestamp;
    uint56 targetDelta = target - beforeOrAt.timestamp;
    return
        beforeOrAt.tickCumulative +
        ((atOrAfter.tickCumulative - beforeOrAt.tickCumulative) /
            int56(observationTimeDelta)) *
        int56(targetDelta);
    ...
```

这就像找到该范围内平均变化率，并将其乘以范围下限和我们需要的时间点之间经过的秒数一样简单。 这就是我们之前讨论过的内插。

我们这里需要实现的最后一件事是 Pool 合约中的一个读取和返回观察值的公共函数：

```solidity
// src/UniswapV3Pool.sol
function observe(uint32[] calldata secondsAgos)
    public
    view
    returns (int56[] memory tickCumulatives)
{
    return
        observations.observe(
            _blockTimestamp(),
            secondsAgos,
            slot0.tick,
            slot0.observationIndex,
            slot0.observationCardinality
        );
}
```

### 解释观察值

现在让我们看看如何解释观察值。

我们刚刚添加的 `observe` 函数返回一个累积价格数组，我们想知道如何将它们转换为实际价格。 我将在 `observe` 函数的测试中演示这一点。

在测试中，我在不同的方向和不同的区块中运行了多个交换：

```solidity
function testObserve() public {
    ...
    pool.increaseObservationCardinalityNext(3);

    vm.warp(2);
    pool.swap(address(this), false, swapAmount, sqrtP(6000), extra);

    vm.warp(7);
    pool.swap(address(this), true, swapAmount2, sqrtP(4000), extra);

    vm.warp(20);
    pool.swap(address(this), false, swapAmount, sqrtP(6000), extra);
    ...
```

> `vm.warp` 是 Foundry 提供的一个作弊码：它转发到具有指定时间戳的区块。 2、7、20 – 这些是区块时间戳。

第一次交换发生在时间戳为 2 的区块，第二次交换发生在时间戳为 7 的区块，第三次交换发生在时间戳为 20 的区块。 然后我们可以读取观察值：

```solidity
    ...
    secondsAgos = new uint32[](4);
    secondsAgos[0] = 0;
    secondsAgos[1] = 13;
    secondsAgos[2] = 17;
    secondsAgos[3] = 18;

    int56[] memory tickCumulatives = pool.observe(secondsAgos);
    assertEq(tickCumulatives[0], 1607059);
    assertEq(tickCumulatives[1], 511146);
    assertEq(tickCumulatives[2], 170370);
    assertEq(tickCumulatives[3], 85176);
    ...
```

1. 最早观察到的价格为 0，这是部署池时设置的初始观察值。 但是，由于基数设置为 3，并且我们进行了 3 次交换，因此它被最后一次观察覆盖。
1. 在第一次交换期间，观察到 tick 85176，这是池的初始价格——回想一下，观察到交换之前的价格。 由于第一个观察值被覆盖，因此现在这是最旧的观察值。
1. 下一个返回的累积价格是 170370，即 `85176 + 85194`。 前者是先前的累加器值，后者是第一次交换之后的在第二次交换期间观察到的价格。
1. 下一个返回的累积价格是 511146，即 `(511146 - 170370) / (17 - 13) = 85194`，即第二次和第三次交换之间的累积价格。
1. 最后，最近的观察值是 1607059，即 `(1607059 - 511146) / (20 - 7) = 84301`，约为 4581 USDC/ETH，这是在第三次交换期间观察到的第二次交换后的价格。

这是一个涉及内插的示例：请求的时间点不是交换的时间点：

```solidity
secondsAgos = new uint32[](5);
secondsAgos[0] = 0;
secondsAgos[1] = 5;
secondsAgos[2] = 10;
secondsAgos[3] = 15;
secondsAgos[4] = 18;

tickCumulatives = pool.observe(secondsAgos);
assertEq(tickCumulatives[0], 1607059);
assertEq(tickCumulatives[1], 1185554);
assertEq(tickCumulatives[2], 764049);
assertEq(tickCumulatives[3], 340758);
assertEq(tickCumulatives[4], 85176);
```

这会产生以下价格：4581.03、4581.03、4747.6 和 5008.91，这些是请求的间隔内的平均价格。

> 以下是如何在 Python 中计算这些值：
> ```python
> vals = [1607059, 1185554, 764049, 340758, 85176]
> secs = [0, 5, 10, 15, 18]
> [1.0001**((vals[i] - vals[i+1]) / (secs[i+1] - secs[i])) for i in range(len(vals)-1)]
> ```
