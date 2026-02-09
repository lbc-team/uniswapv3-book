# 跨 Tick 交易

到目前为止，我们已经取得了很大的进展，我们的 Uniswap V3 实现已经非常接近原始版本了！但是，我们的实现仅支持在价格范围内进行交易——而这正是我们将在本里程碑中改进的地方。

在本里程碑中，我们将：
1. 更新 `mint` 函数，以在不同的价格范围内提供流动性；
2. 更新 `swap` 函数，当当前价格范围内的流动性不足时，跨越价格范围；
3. 学习如何在智能合约中计算流动性；
4. 在 `mint` 和 `swap` 函数中实现滑点保护；
5. 更新 UI 应用程序，以允许在不同的价格范围内添加流动性；
6. 更多地了解定点数。

在这个里程碑中，我们将完成交易，这是 Uniswap 的核心功能！

让我们开始吧！

> 你可以在 [这个 Github 分支](https://github.com/Jeiwan/uniswapv3-code/tree/milestone_3) 中找到本章的完整代码。
>
> 本里程碑在现有合约中引入了大量代码更改。[在这里你可以看到自上次里程碑以来的所有更改](https://github.com/Jeiwan/uniswapv3-code/compare/milestone_2...milestone_3)

> 如果你有任何问题，请随时在 [此里程碑的 GitHub 讨论区](https://github.com/Jeiwan/uniswapv3-book/discussions/categories/milestone-3-cross-tick-swaps) 中提问！
