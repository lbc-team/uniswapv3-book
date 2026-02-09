# 用户界面

在介绍了 swap 路径之后，我们可以显著简化我们的 web 应用程序的内部结构。首先，现在每个 swap 都使用一个路径，因为一个路径不必包含多个池子。其次，现在更容易改变 swap 的方向：我们可以简单地反转路径。而且，由于通过 `CREATE2` 和唯一 salts 实现了统一的池地址生成，我们不再需要存储池地址和关心 token 的顺序。

但是，如果不添加一个关键的算法，我们就无法在 web 应用程序中集成多池 swap。问自己一个问题：“如何在两个没有池子的 token 之间找到一条路径？”

## AutoRouter

Uniswap 实现了所谓的 *AutoRouter*，这是一种寻找两个 token 之间最短路径的算法。此外，它还将一笔支付分成多个较小的支付，以找到最佳的平均汇率。与不进行拆分的交易相比，利润可以高达 [36.84%](https://uniswap.org/blog/auto-router-v2)。这听起来很棒，但是，我们不会构建如此高级的算法。相反，我们将构建更简单的东西。

## 一个简单的 Router 设计

假设我们有一大堆池子：

![分散的池子](images/pools_scattered.png)

我们如何在这种混乱中找到两个 token 之间的最短路径？

对于这种类型的任务，最合适的解决方案是基于 *图*。图是一种数据结构，由节点（代表某些东西的对象）和边（连接节点的链接）组成。我们可以将这些混乱的池子变成一个图，其中每个节点是一个 token（拥有一个池子），每条边是该 token 所属的池子。因此，一个表示为图的池子是两个用一条边连接的节点。上面的池子变成了这张图：

![池子图](images/pools_graph.png)

图给我们的最大优势是能够遍历其节点，从一个节点到另一个节点，以找到路径。具体来说，我们将使用 [A* 搜索算法](https://en.wikipedia.org/wiki/A*_search_algorithm)。可以随意了解该算法的工作原理，但是，在我们的应用程序中，我们将使用一个库来简化我们的生活。我们将使用 [ngraph.ngraph](https://github.com/anvaka/ngraph.graph) 来构建图，并使用 [ngraph.path](https://github.com/anvaka/ngraph.path) 来查找路径（后者实现了 A* 搜索算法以及其他一些算法）。

在 UI 应用程序中，让我们创建一个路径查找器。这将是一个类，实例化后，它会将一对对列表转换为图，以便以后使用该图来查找两个 token 之间的最短路径。
```javascript
import createGraph from 'ngraph.graph';
import path from 'ngraph.path';

class PathFinder {
  constructor(pairs) {
    this.graph = createGraph();

    pairs.forEach((pair) => {
      this.graph.addNode(pair.token0.address);
      this.graph.addNode(pair.token1.address);
      this.graph.addLink(pair.token0.address, pair.token1.address, pair.tickSpacing);
      this.graph.addLink(pair.token1.address, pair.token0.address, pair.tickSpacing);
    });

    this.finder = path.aStar(this.graph);
  }

  ...
```

在构造函数中，我们创建了一个空图，并用链接的节点填充它。每个节点都是一个 token 地址，并且链接具有关联的数据，即 tick 间距 —— 我们将能够从 A* 找到的路径中提取此信息。初始化图后，我们实例化 A* 算法的实现。

接下来，我们需要实现一个函数，该函数将找到 token 之间的路径，并将其转换为 token 地址和 tick 间距的数组：

```javascript
findPath(fromToken, toToken) {
  return this.finder.find(fromToken, toToken).reduce((acc, node, i, orig) => {
    if (acc.length > 0) {
      acc.push(this.graph.getLink(orig[i - 1].id, node.id).data);
    }

    acc.push(node.id);

    return acc;
  }, []).reverse();
}
```

`this.finder.find(fromToken, toToken)` 返回一个节点列表，但不幸的是，不包含有关它们之间边的信息（我们将 tick 间距存储在边中）。因此，我们调用 `this.graph.getLink(previousNode, currentNode)` 来查找边。

现在，每当用户更改输入或输出 token 时，我们都可以调用 `pathFinder.findPath(token0, token1)` 来构建一条新路径。
