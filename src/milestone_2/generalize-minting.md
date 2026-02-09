# 通用化 Minting

现在，我们准备好更新 `mint` 函数，这样我们就不再需要硬编码数值，而是可以进行计算。

## 索引已初始化的 Tick

回想一下，在 `mint` 函数中，我们更新了 TickInfo 映射以存储关于在各个 tick 可用流动性的信息。现在，我们还需要在位图索引中索引新初始化的 tick——稍后我们将使用此索引在交易期间查找下一个已初始化的 tick。

首先，我们需要更新 `Tick.update` 函数：
```solidity
// src/lib/Tick.sol
function update(
    mapping(int24 => Tick.Info) storage self,
    int24 tick,
    uint128 liquidityDelta
) internal returns (bool flipped) {
    ...
    flipped = (liquidityAfter == 0) != (liquidityBefore == 0);
    ...
}
```

它现在返回一个 `flipped` 标志，当流动性被添加到空 tick 或全部流动性从 tick 中移除时，该标志设置为 true。

然后，在 `mint` 函数中，我们更新位图索引：
```solidity
// src/UniswapV3Pool.sol
...
bool flippedLower = ticks.update(lowerTick, amount);
bool flippedUpper = ticks.update(upperTick, amount);

if (flippedLower) {
    tickBitmap.flipTick(lowerTick, 1);
}

if (flippedUpper) {
    tickBitmap.flipTick(upperTick, 1);
}
...
```

> 再次说明，我们将 tick 间距设置为 1，直到我们在里程碑 4 中引入不同的值。

## Token 数量计算

`mint` 函数中最大的变化是切换到 token 数量计算。在里程碑 1 中，我们硬编码了这些值：
```solidity
    amount0 = 0.998976618347425280 ether;
    amount1 = 5000 ether;
```

现在我们将使用里程碑 1 中的公式在 Solidity 中计算它们。让我们回顾一下这些公式：

$$\Delta x = \frac{L(\sqrt{p(i_u)} - \sqrt{p(i_c)})}{\sqrt{p(i_u)}\sqrt{p(i_c)}}$$
$$\Delta y = L(\sqrt{p(i_c)} - \sqrt{p(i_l)})$$

$\Delta x$ 是 `token0` 的数量，或者 token $x$。让我们在 Solidity 中实现它：
```solidity
// src/lib/Math.sol
function calcAmount0Delta(
    uint160 sqrtPriceAX96,
    uint160 sqrtPriceBX96,
    uint128 liquidity
) internal pure returns (uint256 amount0) {
    if (sqrtPriceAX96 > sqrtPriceBX96)
        (sqrtPriceAX96, sqrtPriceBX96) = (sqrtPriceBX96, sqrtPriceAX96);

    require(sqrtPriceAX96 > 0);

    amount0 = divRoundingUp(
        mulDivRoundingUp(
            (uint256(liquidity) << FixedPoint96.RESOLUTION),
            (sqrtPriceBX96 - sqrtPriceAX96),
            sqrtPriceBX96
        ),
        sqrtPriceAX96
    );
}
```

> 这个函数与我们的 Python 脚本中的 `calc_amount0` 完全相同。

第一步是对价格进行排序，以确保在相减时不会下溢。接下来，我们通过将 `liquidity` 乘以 2**96，将其转换为 Q96.64 数字。接下来，根据公式，我们将其乘以价格的差值，然后除以较大的价格。然后，我们除以较小的价格。除法的顺序并不重要，但我们希望进行两次除法，因为价格的乘法可能会溢出。

我们使用 `mulDivRoundingUp` 在一个操作中进行乘法和除法。此函数基于 `PRBMath` 中的 `mulDiv`：
```solidity
function mulDivRoundingUp(
    uint256 a,
    uint256 b,
    uint256 denominator
) internal pure returns (uint256 result) {
    result = PRBMath.mulDiv(a, b, denominator);
    if (mulmod(a, b, denominator) > 0) {
        require(result < type(uint256).max);
        result++;
    }
}
```

`mulmod` 是一个 Solidity 函数，它将两个数字（`a` 和 `b`）相乘，将结果除以 `denominator`，然后返回余数。如果余数为正，我们将结果向上舍入。

接下来，$\Delta y$:
```solidity
function calcAmount1Delta(
    uint160 sqrtPriceAX96,
    uint160 sqrtPriceBX96,
    uint128 liquidity
) internal pure returns (uint256 amount1) {
    if (sqrtPriceAX96 > sqrtPriceBX96)
        (sqrtPriceAX96, sqrtPriceBX96) = (sqrtPriceBX96, sqrtPriceAX96);

    amount1 = mulDivRoundingUp(
        liquidity,
        (sqrtPriceBX96 - sqrtPriceAX96),
        FixedPoint96.Q96
    );
}
```

> 这个函数与我们的 Python 脚本中的 `calc_amount1` 完全相同。

同样，我们使用 `mulDivRoundingUp` 来避免乘法过程中的溢出。

就这样！我们现在可以使用这些函数来计算 token 数量：
```solidity
// src/UniswapV3Pool.sol
function mint(...) {
    ...
    Slot0 memory slot0_ = slot0;

    amount0 = Math.calcAmount0Delta(
        slot0_.sqrtPriceX96,
        TickMath.getSqrtRatioAtTick(upperTick),
        amount
    );

    amount1 = Math.calcAmount1Delta(
        slot0_.sqrtPriceX96,
        TickMath.getSqrtRatioAtTick(lowerTick),
        amount
    );
    ...
}
```

其他一切保持不变。你需要更新 pool 测试中的数量，由于舍入的原因，它们会略有不同。
