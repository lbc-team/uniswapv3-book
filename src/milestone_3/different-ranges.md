# 不同的价格范围

按照我们目前的实现方式，我们的 Pool 合约仅创建包含当前价格的价格范围：
```solidity
// src/UniswapV3Pool.sol
function mint() {
    ...
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

    liquidity += uint128(amount);
    ...
}
```

从这段代码中，您还可以看到我们总是更新 liquidity tracker（仅跟踪当前可用的流动性，即当前价格下的流动性）。

然而，在现实中，价格范围也可以创建在**当前价格之下或之上**。就是这样：Uniswap V3 的设计允许流动性提供者提供不会立即被使用的流动性。当当前价格进入这种“休眠”价格范围时，这种流动性会被“注入”。

以下是可能存在的价格范围类型：
1. 有效价格范围，即包含当前价格的范围。
2. 位于当前价格之下的价格范围。此范围的上限 tick 低于当前 tick。
3. 位于当前价格之上的价格范围。此范围的下限 tick 高于当前 tick。

## 限价订单

关于非活跃流动性（即未在当前价格提供的流动性）一个有趣的现象是，它类似于*限价订单*。

在交易中，限价订单是指当价格穿过交易者选择的水平时执行的订单。例如，您可以设置一个限价订单，当 ETH 的价格降至 \$1000 时购买 1 个 ETH。同样，您可以使用限价订单出售资产。通过 Uniswap V3，您可以通过在低于或高于当前价格的范围内放置流动性来获得类似的行为。让我们看看这是如何运作的：

![当前价格之外的流动性范围](https://img.learnblockchain.cn/how_to_defi/uniswapv3/src/milestone_3/images/ranges_outside_current_price.png)

如果您在当前价格之下（即您选择的价格范围完全低于当前价格）或之上提供流动性，那么您的全部流动性将仅由**一种资产**组成——该资产将是两种资产中较便宜的一种。在我们的示例中，我们正在构建一个以 ETH 作为 token $x$，USDC 作为 token $y$ 的池子，并将价格定义为：

$$P = \frac{y}{x}$$

如果我们将流动性置于当前价格之下，那么流动性将完全由 USDC 组成，因为在我们添加流动性的地方，USDC 的价格低于当前价格。同样，当我们将流动性置于当前价格之上时，流动性将由 ETH 组成，因为 ETH 在该范围内更便宜。

回想一下引言中的这张图：

![价格范围耗尽](https://img.learnblockchain.cn/how_to_defi/uniswapv3/src/milestone_1/images/range_depleted.png)

如果我们从这个范围购买所有可用的 ETH，该范围将只包含另一种 token，USDC，并且价格将向曲线的右侧移动。正如我们定义的价格（$\frac{y}{x}$）将**增加**。如果在这个范围的右边有一个价格范围，它需要有 ETH 流动性，并且只有 ETH，而不是 USDC：它需要为下一次交换提供 ETH。如果我们继续购买并提高价格，我们也可能“耗尽”下一个价格范围，这意味着购买其所有的 ETH 并出售 USDC。同样，价格范围最终只包含 USDC，并且当前价格移到范围之外。

类似地，如果我们购买 USDC token，我们将价格向左移动，并从池中移除 USDC token。下一个价格范围将只包含 USDC token 以满足我们的需求，并且与上述情况类似，如果我们从其中购买所有 USDC，最终将只包含 ETH token。

请注意一个有趣的事实：当穿过整个价格范围时，其流动性会从一个 token 交换到另一个 token。如果我们设置一个非常窄的价格范围，一个在价格移动过程中迅速被穿过的范围，我们就能得到一个限价订单！例如，如果您想以更低的价格购买 ETH，您需要在较低的价格放置一个仅包含 USDC 的价格范围，并等待当前价格穿过它。之后，您需要移除您的流动性并将其转换为 ETH！

我希望这个例子没有让您感到困惑！我认为这是一个解释价格范围动态的好方法。

## 更新 `mint` 函数

为了支持所有类型的价格范围，我们需要知道当前价格是低于、位于内部还是高于用户指定的价格范围，并相应地计算 token 数量。如果价格范围高于当前价格，我们希望流动性由 token $x$ 组成：

```solidity
// src/UniswapV3Pool.sol
function mint() {
    ...
    if (slot0_.tick < lowerTick) {
        amount0 = Math.calcAmount0Delta(
            TickMath.getSqrtRatioAtTick(lowerTick),
            TickMath.getSqrtRatioAtTick(upperTick),
            amount
        );
    ...
```

当价格范围包含当前价格时，我们希望两种 token 的数量与价格成正比（这是我们之前实现的场景）：
```solidity
} else if (slot0_.tick < upperTick) {
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

    liquidity = LiquidityMath.addLiquidity(liquidity, int128(amount));
```

请注意，这是我们想要更新 `liquidity` 的唯一情况，因为该变量跟踪的是立即可以使用的流动性。

在所有其他情况下，当价格范围低于当前价格时，我们希望该范围仅包含 token $y$：
```solidity
} else {
    amount1 = Math.calcAmount1Delta(
        TickMath.getSqrtRatioAtTick(lowerTick),
        TickMath.getSqrtRatioAtTick(upperTick),
        amount
    );
}
```

就是这样！
