# 介绍

在这个里程碑中，我们将构建一个池合约，它可以接收来自用户的流动性，并在一个价格范围内进行兑换。为了尽可能简单，我们将只在一个价格范围内提供流动性，并且只允许在一个方向上进行兑换。此外，我们将手动计算所有需要的数学，以便在开始在 Solidity 中使用数学库之前获得更好的直觉。

让我们对要构建的情况进行建模：
1. 将会有一个 ETH/USDC 池合约。ETH 将是 \\(x\\) 储备，USDC 将是 \\(y\\) 储备。
1. 我们会将当前价格设置为每 1 ETH 5000 USDC。
1. 我们将提供的流动性范围是每 1 ETH 4545-5500 USDC。
1. 我们将从池中购买一些 ETH。此时，由于我们只有一个价格范围，我们希望交易价格保持在该价格范围内。

从视觉上看，这个模型看起来像这样：

![购买 USDC 的 ETH 可视化](https://img.learnblockchain.cn/how_to_defi/uniswapv3/src/milestone_1/images/buy_eth_model.png)

在开始编写代码之前，让我们先弄清楚数学，并计算模型的所有参数。为了简化，我将在 Solidity 中实现它们之前，先用 Python 进行数学计算。这将使我们能够专注于数学，而无需深入研究 Solidity 中数学的细微差别。这也意味着，在智能合约中，我们将硬编码所有的金额。这将使我们能够从一个简单的最小可行产品开始。

为了您的方便，我将所有 Python 计算都放在 [unimath.py](https://github.com/Jeiwan/uniswapv3-code/blob/main/unimath.py) 中。

> 您可以在 [这个 Github 分支](https://github.com/Jeiwan/uniswapv3-code/tree/milestone_1) 中找到此里程碑的完整代码。

>  如果您有任何问题，请随时在 [此里程碑的 GitHub 讨论](https://github.com/Jeiwan/uniswapv3-book/discussions/categories/milestone-1-first-swap) 中提问！
