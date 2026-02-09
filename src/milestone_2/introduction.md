# 第二次 Swap

好的，这里开始变得真实了。到目前为止，我们的实现看起来过于合成和静态。为了降低学习曲线，我们已经计算并硬编码了所有的数量，现在我们准备让它变得动态。我们将实现第二次 swap，这是一个相反方向的 swap：出售 ETH 以购买 USDC。为此，我们将显着改进我们的智能合约：
1. 我们需要在 Solidity 中实现数学计算。然而，由于 Solidity 仅支持整数除法，因此在 Solidity 中实现数学运算比较棘手，我们将使用第三方库。
2. 我们需要让用户选择 swap 方向，并且 pool 合约需要支持双向 swap。我们将改进合约，并使其更接近多范围 swap，我们将在下一个里程碑中实现它。
3. 最后，我们将更新 UI 以支持双向 swap 以及输出数量计算！这将要求我们实现另一个合约，Quoter。

在本里程碑结束时，我们将拥有一个几乎像真正的 DEX 一样工作的应用程序！

让我们开始吧！

> 你可以在 [此 Github 分支](https://github.com/Jeiwan/uniswapv3-code/tree/milestone_2) 中找到本章的完整代码。
>
> 此里程碑在现有合约中引入了大量代码更改。[在这里你可以看到自上次里程碑以来的所有更改](https://github.com/Jeiwan/uniswapv3-code/compare/milestone_1...milestone_2)

> 如果你有任何问题，请随时在 [此里程碑的 GitHub 讨论区](https://github.com/Jeiwan/uniswapv3-book/discussions/categories/milestone-2-second-swap) 中提出！
