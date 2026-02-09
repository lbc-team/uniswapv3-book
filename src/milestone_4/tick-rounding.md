# Tick Rounding

让我们回顾一下为了支持不同的 tick 间距，我们需要做的一些其他更改。

大于 1 的 Tick 间距将不允许用户选择任意价格范围：tick 的索引必须是 tick 间距的倍数。例如，对于 tick 间距 60，我们可以有 ticks：0, 60, 120, 180, 等等。因此，当用户选择一个范围时，我们需要“四舍五入”它，使其边界是 pool 的 tick 间距的倍数。

## JavaScript 中的 `nearestUsableTick`

在 [Uniswap V3 SDK](https://github.com/Uniswap/v3-sdk) 中，执行此操作的函数称为 [nearestUsableTick](https://github.com/Uniswap/v3-sdk/blob/b6cd73a71f8f8ec6c40c130564d3aff12c38e693/src/utils/nearestUsableTick.ts)：
```javascript
/**
 * 返回最接近给定 tick 且可用于给定 tick 间距的 tick
 * @param tick 目标 tick
 * @param tickSpacing pool 的间距
 */
export function nearestUsableTick(tick: number, tickSpacing: number) {
  invariant(Number.isInteger(tick) && Number.isInteger(tickSpacing), 'INTEGERS')
  invariant(tickSpacing > 0, 'TICK_SPACING')
  invariant(tick >= TickMath.MIN_TICK && tick <= TickMath.MAX_TICK, 'TICK_BOUND')
  const rounded = Math.round(tick / tickSpacing) * tickSpacing
  if (rounded < TickMath.MIN_TICK) return rounded + tickSpacing
  else if (rounded > TickMath.MAX_TICK) return rounded - tickSpacing
  else return rounded
}
```

其核心是：
```javascript
Math.round(tick / tickSpacing) * tickSpacing
```

其中 `Math.round` 是四舍五入到最接近的整数：当小数部分小于 0.5 时，它四舍五入到较小的整数；当它大于 0.5 时，它四舍五入到较大的整数；当它是 0.5 时，它也四舍五入到较大的整数。

因此，在 web 应用程序中，我们将在构建 `mint` 参数时使用 `nearestUsableTick`：
```javascript
const mintParams = {
  tokenA: pair.token0.address,
  tokenB: pair.token1.address,
  tickSpacing: pair.tickSpacing,
  lowerTick: nearestUsableTick(lowerTick, pair.tickSpacing),
  upperTick: nearestUsableTick(upperTick, pair.tickSpacing),
  amount0Desired, amount1Desired, amount0Min, amount1Min
}
```

> 实际上，每当用户调整价格范围时都应该调用它，因为我们希望用户看到将要创建的实际价格。在我们的简化应用程序中，我们使其对用户不太友好。

但是，我们也希望在 Solidity 测试中有一个类似的函数，但我们使用的数学库都没有实现它。

## Solidity 中的 `nearestUsableTick`

在我们的智能合约测试中，我们需要一种对 ticks 进行四舍五入并将四舍五入后的价格转换为 $\sqrt{P}$ 的方法。在前一章中，我们选择使用 [ABDKMath64x64](https://github.com/abdk-consulting/abdk-libraries-solidity) 来处理测试中的定点数数学。但是，该库没有实现我们需要移植 `nearestUsableTick` 的舍入函数，因此我们需要自己实现它：

```solidity
function divRound(int128 x, int128 y)
    internal
    pure
    returns (int128 result)
{
    int128 quot = ABDKMath64x64.div(x, y);
    result = quot >> 64;

    // 检查余数是否大于 0.5
    if (quot % 2**64 >= 0x8000000000000000) {
        result += 1;
    }
}
```

该函数执行多个操作：
1. 它将两个 Q64.64 数字相除；
2. 然后将结果四舍五入到十进制数 (`result = quot >> 64`)，此时小数部分丢失（即，结果向下舍入）；
3. 然后将商除以 $2^{64}$，取余数，并将其与 `0x8000000000000000` 进行比较（即 Q64.64 中的 0.5）；
4. 如果余数大于或等于 0.5，则将结果四舍五入为更大的整数。

我们得到的是一个根据 JavaScript 的 `Math.round` 规则四舍五入的整数。然后我们可以重新实现 `nearestUsableTick`：

```solidity
function nearestUsableTick(int24 tick_, uint24 tickSpacing)
    internal
    pure
    returns (int24 result)
{
    result =
        int24(divRound(int128(tick_), int128(int24(tickSpacing)))) *
        int24(tickSpacing);

    if (result < TickMath.MIN_TICK) {
        result += int24(tickSpacing);
    } else if (result > TickMath.MAX_TICK) {
        result -= int24(tickSpacing);
    }
}
```

就是这样！
