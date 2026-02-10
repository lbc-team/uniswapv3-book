# 用户界面

我们现在准备好用本里程碑中所做的更改来更新 UI。我们将添加两个新功能：
1. 添加流动性对话框窗口；
2. 交易中的滑点容忍度。

## 添加流动性对话框

![添加流动性对话框窗口](https://img.learnblockchain.cn/how_to_defi/uniswapv3/src/milestone_3/images/add_liquidity_dialog.png)

此更改最终将从我们的代码中删除硬编码的流动性数量，并允许我们在任意范围内添加流动性。

该对话框是一个带有几个输入的简单组件。 我们甚至可以重用先前实现中的 `addLiquidity` 函数。 但是，现在我们需要在 JavaScript 中将价格转换为 tick 指数：我们希望用户输入价格，但合约期望的是 tick。 为了使我们的工作更轻松，我们将使用 [官方的 Uniswap V3 SDK](https://github.com/Uniswap/v3-sdk/)。

要将价格转换为 $\sqrt{P}$，我们可以使用 [encodeSqrtRatioX96](https://github.com/Uniswap/v3-sdk/blob/08a7c050cba00377843497030f502c05982b1c43/src/utils/encodeSqrtRatioX96.ts) 函数。 该函数将两个数量作为输入，并通过将一个数量除以另一个数量来计算价格。 由于我们只想将价格转换为 $\sqrt{P}$，因此我们可以将 1 作为 `amount0` 传递：
```javascript
const priceToSqrtP = (price) => encodeSqrtRatioX96(price, 1);
```

要将价格转换为 tick 指数，我们可以使用 [TickMath.getTickAtSqrtRatio](https://github.com/Uniswap/v3-sdk/blob/08a7c050cba00377843497030f502c05982b1c43/src/utils/tickMath.ts#L82) 函数。 这是 JavaScript 中 Solidity TickMath 库的实现：

```javascript
const priceToTick = (price) => TickMath.getTickAtSqrtRatio(priceToSqrtP(price));
```

所以我们现在可以将用户输入的价格转换为 tick:

```javascript
const lowerTick = priceToTick(lowerPrice);
const upperTick = priceToTick(upperPrice);
```

我们需要在此处添加的另一件事是滑点保护。 为了简单起见，我将其作为硬编码值并将其设置为 0.5%。 以下是如何使用滑点容忍度来计算最小金额：

```javascript
const slippage = 0.5;
const amount0Desired = ethers.utils.parseEther(amount0);
const amount1Desired = ethers.utils.parseEther(amount1);
const amount0Min = amount0Desired.mul((100 - slippage) * 100).div(10000);
const amount1Min = amount1Desired.mul((100 - slippage) * 100).div(10000);
```

## 交易中的滑点容忍度

即使我们是应用程序的唯一用户，因此在开发过程中永远不会遇到滑点问题，让我们添加一个输入来控制交易期间的滑点容忍度。

![Web 应用程序的主屏幕](https://img.learnblockchain.cn/how_to_defi/uniswapv3/src/milestone_3/images/slippage_tolerance.png)

交易时，滑点保护通过限制价格来实现——我们不希望在交易期间高于或低于的价格。 这意味着我们需要在发送交易交易之前知道这个价格。 但是，我们不需要在前端计算它，因为 Quoter 合约会为我们做这件事：

```solidity
function quote(QuoteParams memory params)
    public
    returns (
        uint256 amountOut,
        uint160 sqrtPriceX96After,
        int24 tickAfter
    ) { ... }
```

并且我们正在调用 Quoter 来计算交易金额。

因此，要计算限制价格，我们需要获取 `sqrtPriceX96After` 并从中减去滑点容忍度——这将是我们不希望在交易期间低于的价格。

```solidity
const limitPrice = priceAfter.mul((100 - parseFloat(slippage)) * 100).div(10000);
```

就是这样！
