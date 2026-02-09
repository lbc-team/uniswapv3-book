# 费用和价格预言机

在本里程碑中，我们将向我们的 Uniswap 实现添加两个新特性。它们有一个共同点：它们建立在我们已经构建的基础上——这就是为什么我们把它们延迟到这个里程碑。然而，它们的重要性并不相同。

我们将添加交易费用(swap fees)和价格预言机(price oracle)：
- 交易费用是我们正在实现的 DEX 设计的关键机制。它们是使事物结合在一起的粘合剂。正如我们已经了解到的，交易费用激励流动性提供者(liquidity providers)提供流动性，没有流动性就不可能进行交易。
- 另一方面，价格预言机是 DEX 的一个可选的实用功能。DEX 在进行交易时，也可以充当价格预言机——即向其他服务提供代币价格。这不会影响实际的交易，但会为其他链上应用提供有用的服务。

好的，让我们开始构建吧！

> 你可以在 [此 Github 分支](https://github.com/Jeiwan/uniswapv3-code/tree/milestone_5) 中找到本章的完整代码。
>
> 此里程碑在现有合约中引入了许多代码更改。[在这里你可以看到自上次里程碑以来的所有更改](https://github.com/Jeiwan/uniswapv3-code/compare/milestone_4...milestone_5)

> 如果你有任何问题，请随时在[此里程碑的 GitHub 讨论](https://github.com/Jeiwan/uniswapv3-book/discussions/categories/milestone-5-fees-and-price-oracle) 中提问！
