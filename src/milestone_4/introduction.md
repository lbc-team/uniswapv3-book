# 多 Pool 交易

在实现了跨 tick 交易之后，我们已经非常接近真实的 Uniswap V3 交易了。我们实现的一个重要限制是，它只允许在 pool 内部进行交易——如果没有一对 token 的 pool，那么在这些 token 之间进行交易是不可能的。但在 Uniswap 中并非如此，因为它允许多 pool 交易。在本章中，我们将向我们的实现中添加多 pool 交易。

以下是计划：

1. 首先，我们将学习并实现 Factory 合约；
2. 然后，我们将了解链式或多 pool 交易如何工作，并实现 Path 库；
3. 接着，我们将更新前端应用以支持多 pool 交易；
4. 我们将实现一个基本的路由器，用于查找两个 token 之间的路径；
5. 一路上，我们还将了解 tick 间距，这是一种优化交易的方式。

完成本章后，我们的实现将能够处理多 pool 交易，例如，通过不同的稳定币将 WBTC 兑换为 WETH：WETH → USDC → USDT → WBTC。

让我们开始吧！

> 您可以在 [这个 Github 分支](https://github.com/Jeiwan/uniswapv3-code/tree/milestone_4) 中找到本章的完整代码。
>
> 此里程碑在现有合约中引入了许多代码更改。[在这里您可以看到自上次里程碑以来的所有更改](https://github.com/Jeiwan/uniswapv3-code/compare/milestone_3...milestone_4)

> 如果您有任何问题，请随时在 [此里程碑的 GitHub 讨论区](https://github.com/Jeiwan/uniswapv3-book/discussions/categories/milestone-4-multi-pool-swaps) 中提出！
