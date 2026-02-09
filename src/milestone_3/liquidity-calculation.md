# 流动性计算

在 Uniswap V3 的所有数学计算中，我们尚未在 Solidity 中实现的还有流动性计算。在 Python 脚本中，我们有这些函数：

```python
def liquidity0(amount, pa, pb):
    if pa > pb:
        pa, pb = pb, pa
    return (amount * (pa * pb) / q96) / (pb - pa)


def liquidity1(amount, pa, pb):
    if pa > pb:
        pa, pb = pb, pa
    return amount * q96 / (pb - pa)
```

让我们在 Solidity 中实现它们，以便我们可以在 `Manager.mint()` 函数中计算流动性。

## 为 Token X 实现流动性计算

我们将要实现的函数允许我们在 token 数量和价格范围已知时计算流动性（$L = \sqrt{xy}$）。幸运的是，我们已经知道了所有的公式。让我们回顾一下这个公式：

$$\Delta x = \Delta \frac{1}{\sqrt{P}}L$$

在前一章中，我们使用此公式来计算交换数量（在本例中为 $\Delta x$），现在我们将使用它来找到 $L$：

$$L = \frac{\Delta x}{\Delta \frac{1}{\sqrt{P}}}$$

或者，简化后：
$$L = \frac{\Delta x \sqrt{P_u} \sqrt{P_l}}{\sqrt{P_u} - \sqrt{P_l}}$$

> 我们在[流动性数量计算](https://uniswapv3book.com/docs/milestone_1/calculating-liquidity/#liquidity-amount-calculation)中推导出了这个公式。

在 Solidity 中，我们将再次使用 `PRBMath` 来处理乘法然后除法时的溢出：

```solidity
function getLiquidityForAmount0(
    uint160 sqrtPriceAX96,
    uint160 sqrtPriceBX96,
    uint256 amount0
) internal pure returns (uint128 liquidity) {
    if (sqrtPriceAX96 > sqrtPriceBX96)
        (sqrtPriceAX96, sqrtPriceBX96) = (sqrtPriceBX96, sqrtPriceAX96);

    uint256 intermediate = PRBMath.mulDiv(
        sqrtPriceAX96,
        sqrtPriceBX96,
        FixedPoint96.Q96
    );
    liquidity = uint128(
        PRBMath.mulDiv(amount0, intermediate, sqrtPriceBX96 - sqrtPriceAX96)
    );
}
```

## 为 Token Y 实现流动性计算

类似地，我们将使用[流动性数量计算](https://uniswapv3book.com/docs/milestone_1/calculating-liquidity/#liquidity-amount-calculation)中的另一个公式来在 $y$ 的数量和价格范围已知时找到 $L$：

$$\Delta y = \Delta\sqrt{P} L$$
$$L = \frac{\Delta y}{\sqrt{P_u}-\sqrt{P_l}}$$

```solidity
function getLiquidityForAmount1(
    uint160 sqrtPriceAX96,
    uint160 sqrtPriceBX96,
    uint256 amount1
) internal pure returns (uint128 liquidity) {
    if (sqrtPriceAX96 > sqrtPriceBX96)
        (sqrtPriceAX96, sqrtPriceBX96) = (sqrtPriceBX96, sqrtPriceAX96);

    liquidity = uint128(
        PRBMath.mulDiv(
            amount1,
            FixedPoint96.Q96,
            sqrtPriceBX96 - sqrtPriceAX96
        )
    );
}
```

我希望这很清楚！

## 寻找公平的流动性

你可能想知道为什么有两种计算 $L$ 的方法，而我们一直只有一个 $L$，它被计算为 $L = \sqrt{xy}$，并且这两种方法中哪一种是正确的？答案是：它们都是正确的。

在上面的公式中，我们基于不同的参数计算 $L$：价格范围和 token 的数量。不同的价格范围和不同的 token 数量将导致不同的 $L$ 值。并且在有一种情况下，我们需要计算两个 $L$，然后选择其中一个。回想一下 `mint` 函数中的这一段代码：

```solidity
if (slot0_.tick < lowerTick) {
    amount0 = Math.calcAmount0Delta(...);
} else if (slot0_.tick < upperTick) {
    amount0 = Math.calcAmount0Delta(...);

    amount1 = Math.calcAmount1Delta(...);

    liquidity = LiquidityMath.addLiquidity(liquidity, int128(amount));
} else {
    amount1 = Math.calcAmount1Delta(...);
}
```

事实证明，在计算流动性时，我们还需要遵循这个逻辑：
1. 如果我们正在计算高于当前价格的范围的流动性，我们使用公式中的 $\Delta x$ 版本；
2. 当我们计算低于当前价格的范围的流动性时，我们使用 $\Delta y$ 版本；
3. 当价格范围包括当前价格时，我们计算**两者**并选择较小的那个。

> 同样，我们在[流动性数量计算](https://uniswapv3book.com/docs/milestone_1/calculating-liquidity/#liquidity-amount-calculation)中讨论了这些想法。

让我们现在实现这个逻辑。

当当前价格低于价格范围的下限时：
```solidity
function getLiquidityForAmounts(
    uint160 sqrtPriceX96,
    uint160 sqrtPriceAX96,
    uint160 sqrtPriceBX96,
    uint256 amount0,
    uint256 amount1
) internal pure returns (uint128 liquidity) {
    if (sqrtPriceAX96 > sqrtPriceBX96)
        (sqrtPriceAX96, sqrtPriceBX96) = (sqrtPriceBX96, sqrtPriceAX96);

    if (sqrtPriceX96 <= sqrtPriceAX96) {
        liquidity = getLiquidityForAmount0(
            sqrtPriceAX96,
            sqrtPriceBX96,
            amount0
        );
```

当当前价格在范围内时，我们选择较小的 $L$：
```solidity
} else if (sqrtPriceX96 <= sqrtPriceBX96) {
    uint128 liquidity0 = getLiquidityForAmount0(
        sqrtPriceX96,
        sqrtPriceBX96,
        amount0
    );
    uint128 liquidity1 = getLiquidityForAmount1(
        sqrtPriceAX96,
        sqrtPriceX96,
        amount1
    );

    liquidity = liquidity0 < liquidity1 ? liquidity0 : liquidity1;
```

最后：
```solidity
} else {
    liquidity = getLiquidityForAmount1(
        sqrtPriceAX96,
        sqrtPriceBX96,
        amount1
    );
}
```

完成了。