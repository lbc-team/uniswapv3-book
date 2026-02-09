# 我们将构建什么

本书的目标是构建一个 Uniswap V3 的克隆。但是，我们不会构建一个精确的副本。主要原因是 Uniswap 是一个大型项目，包含许多细微之处和辅助机制——分解所有这些会使本书内容膨胀，并使读者更难完成阅读。相反，我们将构建 Uniswap 的核心，其最困难和最重要的机制。这包括流动性管理、交易、费用、外围合约、报价合约和 NFT 合约。之后，我相信，你将能够阅读 Uniswap V3 的源代码，并理解本书范围之外的所有机制。

## 智能合约

完成本书后，你将实现以下合约：
1. `UniswapV3Pool`–实现流动性管理和交易的核心池合约。此合约非常接近[原始合约](https://github.com/Uniswap/v3-core/blob/main/contracts/UniswapV3Pool.sol)，但是，一些实现细节有所不同，并且为了简单起见，省略了一些内容。例如，我们的实现只会处理“精确输入”的交易，即具有已知输入量的交易。最初的实现还支持具有已知*输出*量的交易（即，当你想购买一定数量的代币时）。
1. `UniswapV3Factory`–注册合约，用于部署新池并记录所有已部署的池。除了更改所有者和费用的能力外，此合约与[原始合约](https://github.com/Uniswap/v3-core/blob/main/contracts/UniswapV3Factory.sol)基本相同。
1. `UniswapV3Manager`–一个外围合约，使与池合约的交互更加容易。这是 [SwapRouter](https://github.com/Uniswap/v3-periphery/blob/main/contracts/SwapRouter.sol) 的一个非常简化的实现。同样，正如你所看到的，我没有区分“精确输入”和“精确输出”的交易，仅实现了前者。
1. `UniswapV3Quoter` 是一个很棒的合约，允许链上计算交易价格。这是 [Quoter](https://github.com/Uniswap/v3-periphery/blob/main/contracts/lens/Quoter.sol) 和 [QuoterV2](https://github.com/Uniswap/v3-periphery/blob/main/contracts/lens/QuoterV2.sol) 的最小副本。同样，仅支持“精确输入”的交易。
1. `UniswapV3NFTManager` 允许将流动性头寸转换为 NFT。这是 [NonfungiblePositionManager](https://github.com/Uniswap/v3-periphery/blob/main/contracts/NonfungiblePositionManager.sol) 的一个简化实现。

## 前端应用程序

对于本书，我还构建了 [Uniswap UI](https://app.uniswap.org/) 的简化克隆。这是一个非常笨拙的克隆，我的 React 和前端技能非常差，但它演示了前端应用程序如何使用 Ethers.js 和 MetaMask 与智能合约交互。
