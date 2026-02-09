# Solidity 中的数学

由于 Solidity 不支持带小数部分的数字，因此 Solidity 中的数学运算有些复杂。Solidity 提供了整数和无符号整数类型，但对于或多或少复杂的数学计算来说，这些是不够的。

另一个困难是 gas 消耗：算法越复杂，消耗的 gas 就越多。因此，如果我们需要高级数学运算（如 `exp`、`ln` 和 `sqrt`），我们希望它们尽可能地节省 gas。

另一个大问题是下溢/溢出的可能性。当乘以 `uint256` 数字时，存在溢出的风险：结果数字可能太大，以至于无法容纳到 256 位中。

所有这些困难迫使我们使用第三方数学库来实现高级数学运算，并且最好优化它们的 gas 消耗。如果我们需要的算法没有库，我们将不得不自己实现它，如果我们需要实现一个独特的计算，这是一项艰巨的任务。

## 复用数学合约

在我们的 Uniswap V3 实现中，我们将使用两个第三方数学合约：
1. [PRBMath](https://github.com/paulrberg/prb-math)，这是一个很棒的高级定点数学算法库。我们将使用 `mulDiv` 函数来处理整数相乘然后相除时的溢出。
1. 来自原始 Uniswap V3 仓库的 [TickMath](https://github.com/Uniswap/v3-core/blob/main/contracts/libraries/TickMath.sol)。该合约实现了两个函数，`getSqrtRatioAtTick` 和 `getTickAtSqrtRatio`，它们将 $\sqrt{P}$
转换为 ticks，然后再转换回来。

让我们关注后者。

在我们的合约中，我们需要将 ticks 转换为对应的 $\sqrt{P}$，然后再转换回来。公式是：

$$\sqrt{P(i)} = \sqrt{1.0001^i} = 1.0001^{\frac{i}{2}}$$

$$i = log_{\sqrt{1.0001}}\sqrt{P(i)}$$

这些是复杂的数学运算（至少对于 Solidity 而言），并且它们需要高精度，因为我们不希望在计算价格时出现舍入误差。为了获得更好的精度和优化，我们需要一个独特的实现。

如果您查看 [getSqrtRatioAtTick](https://github.com/Uniswap/v3-core/blob/8f3e4645a08850d2335ead3d1a8d0c64fa44f222/contracts/libraries/TickMath.sol#L23-L54) 和 [getTickAtSqrtRatio](https://github.com/Uniswap/v3-core/blob/8f3e4645a08850d2335ead3d1a8d0c64fa44f222/contracts/libraries/TickMath.sol#L61-L204) 的原始代码，您会发现它们非常复杂：其中包含许多幻数（例如 `0xfffcb933bd6fad37aa2d162d1a594001`）、乘法和位运算。目前，我们不打算分析代码或重新实现它，因为这是一个非常高级且有些不同的话题。我们将按原样使用该合约。并且，在以后的里程碑中，我们将分解计算过程。
