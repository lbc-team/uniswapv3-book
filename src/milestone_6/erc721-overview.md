# ERC721 概述

让我们从 [EIP-721](https://eips.ethereum.org/EIPS/eip-721) 的概述开始，这个标准定义了 NFT 合约。

ERC721 是 ERC20 的一个变体。它们之间的主要区别在于 ERC721 代币是 *非同质化* 的，也就是说：一个代币与另一个代币不相同。为了区分 ERC721 代币，每个代币都有一个唯一的 ID，这个 ID 几乎总是代币被铸造时的计数器。ERC721 代币也有一个扩展的所有权概念：每个代币的所有者都会被追踪并存储在合约中。这意味着只有由代币 ID 标识的不同代币才能被转移（或批准转移）。

Uniswap V3 流动性仓位和 NFT 的共同点在于这种非同质性：NFT 和流动性仓位不可互换，并通过唯一的 ID 标识。正是这种相似性将允许我们合并这两个概念。

ERC20 和 ERC721 之间最大的区别是后者中的 `tokenURI` 函数。作为 ERC721 智能合约实现的 NFT 代币，具有存储在外部而非区块链上的链接资产。为了将代币 ID 链接到存储在区块链之外的图像（或声音，或其他任何东西），ERC721 定义了 `tokenURI` 函数。该函数应返回一个指向 JSON 文件的链接，该文件定义了 NFT 代币元数据，例如：
```json
{
    "name": "Thor's hammer",
    "description": "Mjölnir, the legendary hammer of the Norse god of thunder.",
    "image": "https://game.example/item-id-8u5h2m.png",
    "strength": 20
}
```
（此示例取自 [OpenZeppelin 上的 ERC721 文档](https://docs.openzeppelin.com/contracts/4.x/erc721)）

这样的 JSON 文件定义了代币的名称、集合的描述、代币图像的链接以及代币的属性。

或者，我们可以将 JSON 元数据和代币图像存储在链上。当然，这是非常昂贵的（在链上保存数据是以太坊中最昂贵的操作），但如果存储模板，我们可以使其更便宜。集合中的所有代币都具有相似的元数据（大部分相同，但图像链接和属性对于每个代币都不同）和视觉效果。对于后者，我们可以使用 SVG，这是一种类似 HTML 的格式，而 HTML 是一种很好的模板语言。

当在链上存储 JSON 元数据和 SVG 时，`tokenURI` 函数将直接返回 JSON 元数据，而不是返回链接，使用 [data URI scheme](https://en.wikipedia.org/wiki/Data_URI_scheme#Syntax) 对其进行编码。SVG 图像也将被内联，无需发出外部请求来下载代币元数据和图像。
