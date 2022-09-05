# Benchmarking-Loss-Functions
## About the project
We tested a number of local structure preserving loss functions and their influence on node classification task.

## How to use

examples are in NodeClassificaton.jpynb 

## Available loss functions
* Laplacian Eigenmaps (https://proceedings.neurips.cc/paper/2001/file/f106b7f99d2cb30c3db1c3cc0fde9ccb-Paper.pdf)
* Graph Factorization (https://dl.acm.org/doi/pdf/10.1145/2488388.2488393)
* HOPE (https://dl.acm.org/doi/pdf/10.1145/2939672.2939751)
* VERSE (https://arxiv.org/pdf/1803.04742.pdf)
* LINE (https://arxiv.org/pdf/1503.03578.pdf)
* APP (https://ojs.aaai.org/index.php/AAAI/article/view/10878)
* DeepWalk (https://arxiv.org/pdf/1403.6652.pdf)
* Node2Vec (https://arxiv.org/pdf/1607.00653.pdf)
* Force2Vec (https://arxiv.org/pdf/2009.10035.pdf)

## Available convolutions 
* GCN (https://pytorch-geometric.readthedocs.io/en/latest/modules/nn.html#torch_geometric.nn.conv.GCNConv)
* GAT (https://pytorch-geometric.readthedocs.io/en/latest/modules/nn.html#torch_geometric.nn.conv.GATConv)
* SAGE (https://pytorch-geometric.readthedocs.io/en/latest/modules/nn.html#torch_geometric.nn.conv.SAGEConv)
