import collections

import torch
import torch.nn.functional as F
from torch_geometric.nn import ChebConv, GATConv, GCNConv, SAGEConv, SGConv


class Net(torch.nn.Module):
    def __init__(
        self,
        dataset,
        device,
        loss_function,
        mode="unsupervised",
        conv="GCN",
        hidden_layer=64,
        out_layer=128,
        dropout=0,
        num_layers=2,
    ):
        super(Net, self).__init__()
        self.mode = mode
        self.conv = conv
        self.num_layers = num_layers
        self.data = dataset
        self.num_features = dataset.x.shape[1]
        # print(dataset.num_features)
        self.loss_function = loss_function
        self.convs = torch.nn.ModuleList()
        self.hidden_layer = hidden_layer
        self.out_layer = out_layer
        self.dropout = dropout
        self.device = device
        self.history = []

        if self.mode == "unsupervised":
            out_channels = self.out_layer
        elif self.mode == "supervised":
            out_channels = len(
                collections.Counter(self.data.y.tolist()).keys()
            )  # 128 FOR LINK PREDICTION, FOR NODE CLASSIFICATION UNCOMMENT
        if self.conv == "GCN":
            if self.num_layers == 1:
                self.convs.append(GCNConv(self.num_features, out_channels))
            else:
                self.convs.append(GCNConv(self.num_features, self.hidden_layer))
                for i in range(1, self.num_layers - 1):
                    self.convs.append(GCNConv(self.hidden_layer, self.hidden_layer))
                self.convs.append(GCNConv(self.hidden_layer, out_channels))
        elif self.conv == "SAGE":

            if self.num_layers == 1:
                self.convs.append(SAGEConv(self.num_features, out_channels))
            else:
                self.convs.append(SAGEConv(self.num_features, self.hidden_layer))
                for i in range(1, self.num_layers - 1):
                    self.convs.append(SAGEConv(self.hidden_layer, self.hidden_layer))
                self.convs.append(SAGEConv(self.hidden_layer, out_channels))
        elif self.conv == "GAT":
            if self.num_layers == 1:
                self.convs.append(GATConv(self.num_features, out_channels))
            else:
                self.convs.append(GATConv(self.num_features, self.hidden_layer))
                for i in range(1, self.num_layers - 1):
                    self.convs.append(GATConv(self.hidden_layer, self.hidden_layer))
                self.convs.append(GATConv(self.hidden_layer, out_channels))

        if loss_function["loss var"] == "Random Walks":
            self.loss = self.lossRandomWalks
        elif loss_function["loss var"] == "Context Matrix":
            self.loss = self.lossContextMatrix
        elif loss_function["loss var"] == "Factorization":
            self.loss = self.lossFactorization
        elif loss_function["loss var"] == "Laplacian EigenMaps":
            self.loss = self.lossLaplacianEigenMaps
        elif loss_function["loss var"] == "Force2Vec":
            self.loss = self.lossTdistribution
        self.reset_parameters()

    def reset_parameters(self):
        for conv in self.convs:
            conv.reset_parameters()

    def forward(self, x, adjs):
        for i, (edge_index, _, size) in enumerate(adjs):
            x_target = x[: size[1]]  # Target nodes are always placed first.
            x = self.convs[i]((x, x_target), edge_index)
            if i != self.num_layers - 1:
                x = F.relu(x)
                x = F.dropout(x, p=self.dropout, training=self.training)
        if self.mode == "unsupervised":
            return x
        elif self.mode == "supervised":
            return x.log_softmax(dim=1)

    def inference(self, data, dp=0):

        x, edge_index, edge_weight = data.x, data.edge_index, data.edge_attr

        for i, conv in enumerate(self.convs):

            x = conv(x, edge_index)
            if i != self.num_layers - 1:
                x = x.relu()
                x = F.dropout(x, p=dp, training=self.training)
        if self.mode == "unsupervised":  # ONLY FOR LINK PREDICTION
            return x
        elif self.mode == "supervised":
            return x.log_softmax(dim=-1)

    def lossRandomWalks(self, out, PosNegSamples):
        (pos_rw, neg_rw) = PosNegSamples
        pos_rw, neg_rw = pos_rw.type(torch.LongTensor).to(self.device), neg_rw.type(torch.LongTensor).to(self.device)
        # Positive loss.
        pos_loss = 0
        start, rest = pos_rw[:, 0], pos_rw[:, 1:].contiguous()
        h_start = out[start].view(pos_rw.size(0), 1, self.out_layer)
        h_rest = out[rest.view(-1)].view(pos_rw.size(0), -1, self.out_layer)
        dot = (h_start * h_rest).sum(dim=-1).view(-1)

        pos_loss = -(torch.nn.LogSigmoid()(dot)).mean()  # -torch.log(torch.sigmoid(dot)).mean()

        # print('dot',dot.device)
        # Negative loss
        start, rest = neg_rw[:, 0], neg_rw[:, 1:].contiguous()
        h_start = out[start].view(neg_rw.size(0), 1, self.out_layer)
        h_rest = out[rest.view(-1)].view(neg_rw.size(0), -1, self.out_layer)
        dot = (h_start * h_rest).sum(dim=-1).view(-1)
        neg_loss = -(torch.nn.LogSigmoid()((-1) * dot)).mean()

        return pos_loss + neg_loss  # +0.5*lmbda*sum(sum(out*out))

    def lossContextMatrix(self, out, PosNegSamples):
        (pos_rw, neg_rw) = PosNegSamples
        pos_rw = pos_rw.to(self.device)
        neg_rw = neg_rw.to(self.device)

        start, rest = neg_rw[:, 0].type(torch.LongTensor), neg_rw[:, 1:].type(torch.LongTensor).contiguous()
        indices = start != rest.view(-1)
        start = start[indices]
        h_start = out[start].view(start.shape[0], 1, self.out_layer)
        rest = rest.view(-1)
        rest = rest[indices]
        # print('neg',start,rest)
        h_rest = out[rest].view(rest.shape[0], -1, self.out_layer)

        dot = (h_start * h_rest).sum(dim=-1).view(-1)
        neg_loss = -(torch.nn.LogSigmoid()((-1) * dot)).mean()
        # Positive loss.
        start, rest = pos_rw[:, 0].type(torch.LongTensor), pos_rw[:, 1].type(torch.LongTensor).contiguous()
        weight = pos_rw[:, 2]
        h_start = out[start].view(pos_rw.size(0), 1, self.out_layer)

        h_rest = out[rest.view(-1)].view(pos_rw.size(0), -1, self.out_layer)
        dot = ((h_start * h_rest).sum(dim=-1)).view(-1)
        if self.loss_function["Name"] == "LINE":
            pos_loss = -2 * (weight * torch.nn.LogSigmoid()((-1) * dot)).mean()

        elif self.loss_function["Name"].split("_")[0] == "VERSE" or self.loss_function["Name"] == "APP":
            pos_loss = -(weight * torch.nn.LogSigmoid()((-1) * dot)).mean()

        return pos_loss + neg_loss

    def lossFactorization(self, out, S, **kwargs):
        S = S.to(self.device)
        lmbda = self.loss_function["lmbda"]
        loss = 0.5 * sum(sum((S - torch.matmul(out, out.t())) * (S - torch.matmul(out, out.t())))) + 0.5 * lmbda * sum(
            sum(out * out)
        )
        return loss

    def lossLaplacianEigenMaps(self, out, A):
        dd = torch.device("cuda", 0)
        # dd=torch.device('cpu')
        L = (torch.diag(sum(A)) - A).type(torch.FloatTensor).to(dd)
        out_tr = out.t().to(dd)
        loss = torch.trace(torch.matmul(torch.matmul(out_tr, L), out))
        yDy = torch.matmul(
            torch.matmul(out_tr, torch.diag(sum(A.t())).type(torch.FloatTensor).to(dd)), out
        ) - torch.diag(torch.ones(out.shape[1])).type(torch.FloatTensor).to(dd)
        loss_2 = torch.sqrt(sum(sum(yDy * yDy)))
        return loss + loss_2

    def lossTdistribution(self, out, PosNegSamples):
        eps = 10e-6
        (pos_rw, neg_rw) = PosNegSamples
        pos_rw = pos_rw.to(self.device)
        neg_rw = neg_rw.to(self.device)

        start, rest = neg_rw[:, 0].type(torch.LongTensor), neg_rw[:, 1:].type(torch.LongTensor).contiguous()
        indices = start != rest.view(-1)
        start = start[indices]
        h_start = out[start].view(start.shape[0], 1, self.out_layer)
        rest = rest.view(-1)
        rest = rest[indices]
        # print('neg',start,rest)
        h_rest = out[rest].view(rest.shape[0], -1, self.out_layer)

        # h_start=torch.nn.functional.normalize(h_start, p=2.0, dim = -1)
        # h_rest=torch.nn.functional.normalize(h_rest, p=2.0, dim = -1)
        # print(h_start,h_rest)
        t_squared = ((h_start - h_rest) * (h_start - h_rest)).mean(dim=-1).view(-1)

        # if len((t_squared==0).nonzero())>0:
        #   print('tsquared')
        #    print(start[(t_squared==0).nonzero()],rest[(t_squared==0).nonzero()])

        # idx=(torch.log(t_squared)==torch.tensor((-1)*np.inf)).nonzero()
        # self.history.append(h_start)
        # if len(idx)>0:
        # print('error',len(idx),h_start[idx])
        #  for i in range(len(self.history)):
        #     print(self.history[i][idx])

        # neg_loss = -(torch.log(torch.nn.Softsign()(t_squared))).mean()
        neg_loss = (-torch.log((t_squared / (1 + t_squared)) + eps)).mean()
        # neg_loss = (-torch.log(t_squared) + torch.log(t_squared+1)).mean()
        # print(torch.sum(t_squared==0), torch.log(t_squared+1).sum())
        # print('neg',neg_loss)
        # Positive loss.
        start, rest = pos_rw[:, 0].type(torch.LongTensor), pos_rw[:, 1].type(torch.LongTensor).contiguous()
        weight = pos_rw[:, 2]
        h_start = out[start].view(pos_rw.size(0), 1, self.out_layer)
        h_rest = out[rest.view(-1)].view(pos_rw.size(0), -1, self.out_layer)
        # h_start=torch.nn.functional.normalize(h_start, p=2.0, dim = -1)
        # h_rest=torch.nn.functional.normalize(h_rest, p=2.0, dim = -1)
        t_squared = ((h_start - h_rest) * (h_start - h_rest)).sum(dim=-1).view(-1)
        pos_loss = -(torch.log(1 / (1 + t_squared))).mean()
        # print('losses',pos_loss,neg_loss)
        return pos_loss + neg_loss

    # loss function for supervised mode
    def loss_sup(self, pred, label):
        return F.nll_loss(pred, label)
