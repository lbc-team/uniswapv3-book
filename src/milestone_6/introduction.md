# NFT 仓位

这是本书的锦上添花之笔。在这个里程碑中，我们将学习 Uniswap 合约如何被扩展和集成到第三方协议中。这种可能性是拥有仅包含关键功能的核心合约的直接结果，这允许集成到其他合约中，而无需向核心合约添加新功能。

Uniswap V3 的一个额外功能是将流动性仓位转化为 NFT token 的能力。这是一个此类 token 的示例：

<p align="center">
<img src="images/nft_example.png" alt="Uniswap V3 NFT example"/>
</p>

它显示了 token 符号、资金池费用、仓位 ID、下限和上限 tick、token 地址，以及提供仓位的曲线段。

> 你可以在[这个 OpenSea 合集](https://opensea.io/collection/uniswap-v3-positions)中查看所有 Uniswap V3 NFT 仓位。

在这个里程碑中，我们将添加流动性仓位的 NFT token 化！

开始吧！

> 你可以在[这个 Github 分支](https://github.com/Jeiwan/uniswapv3-code/tree/milestone_6)中找到本章的完整代码。
>
> 这个里程碑在现有合约中引入了许多代码更改。[在这里你可以看到自上次里程碑以来的所有更改](https://github.com/Jeiwan/uniswapv3-code/compare/milestone_5...milestone_6)

> 如果你有任何问题，请随时在[此里程碑的 GitHub 讨论](https://github.com/Jeiwan/uniswapv3-book/discussions/categories/milestone-6-nft-positions)中提问！
