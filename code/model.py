import cupy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

class mCNN(nn.Module):
    def __init__(self, dim=300, seq_len=300, hidden=64, classes=2):
        super(mCNN, self).__init__()
        self.loss_func = focal()
        self.activation = GELU()

        self.enc_size = [hidden]*(5+1)
        self.blocks = nn.ModuleList([self.linear_block(in_f, out_f) for in_f, out_f in zip(self.enc_size, self.enc_size[1:]) ])
        #self.encoder = nn.Sequential(*blocks)
        self.layer1 = nn.Embedding(120000, 300, padding_idx=0)

        self.conv1 = nn.Conv2d(1, hidden, (3, dim), padding=(1, 0))
        self.decoder = nn.Linear(hidden, classes)

        self.IC_input = self.IC(300)
        self.resweight = nn.Parameter(torch.Tensor([0]))
        self.dropout = nn.Dropout(p=0.1)

    def IC(self, in_f, *args, **kwargs):
        #BatchNorm1d#LayerNorm
        return nn.Sequential( nn.LayerNorm(in_f), nn.Dropout(p=0.9) )

    def res_block(self, x):
        for i in self.blocks:
            x_org = x
            x = i(x)
            x = x_org + x*self.resweight
        return x

    def linear_block(self, in_f, out_f, *args, **kwargs):
        return nn.Sequential(
            self.IC(in_f),
            nn.Linear(in_f, int(in_f/3)),
            self.activation,
            self.IC(int(in_f/3)),
            nn.Linear(int(in_f/3), in_f), 
            self.activation,
        )

    def main_task(self, h):
        h = self.layer1(h)
        #h = self.dropout(h)
        h = self.IC_input(h)
        h = self.conv1(h.unsqueeze(1)).squeeze(3)
        h = self.activation(h)
        h = F.avg_pool2d(h, (1, h.size(2))).squeeze(2)
        
        #h_org = h
        h = self.res_block(h)
        #h = h_org + h * self.resweight
        h = self.dropout(h)
        rating = self.decoder(h)
        return rating, h

    def forward(self, data_, mode='train'):
        if mode == 'inference':
            return self.main_task(data_[0])[0]
        else:
            x1 = data_[0]
            y1 = data_[1]

            if len(data_) == 4:
                return
            else:
                y_rating, embed = self.main_task(x1)
                return y_rating, self.loss_func(y_rating, y1)
    
class simple_CNN(nn.Module):
    def __init__(self, dim=300, seq_len=300, hidden=64, classes=2):
        super(simple_CNN, self).__init__()
        self.loss_func = nn.CrossEntropyLoss()
        self.activation = nn.ReLU()

        self.layer1 = nn.Conv2d(1, hidden, (3, dim), padding=(1, 0))
        self.decoder = nn.Linear(hidden, classes)

        self.dropout = nn.Dropout(p=0.1)
    def main_task(self, h):
        h = self.layer1(h.unsqueeze(1)).squeeze(3)
        h = self.activation(h)
        h = F.avg_pool2d(h, (1, h.size(2))).squeeze(2)
        
        h = self.dropout(h)
        rating = self.decoder(h)
        return rating, h

    def forward(self, data_, mode='train'):
        if mode == 'inference':
            return self.main_task(data_[0])[0]
        else:
            x1 = data_[0]
            y1 = data_[1]

            if len(data_) == 4:
                return
            else:
                y_rating, embed = self.main_task(x1)
                return y_rating, self.loss_func(y_rating, y1)

class EmbCNN(nn.Module):
    def __init__(self, dim=300, seq_len=300, hidden=64, classes=2):
        super(EmbCNN, self).__init__()
        self.loss_func = nn.CrossEntropyLoss()
        self.activation = nn.ReLU()

        self.layer1 = nn.Embedding(120000, dim, padding_idx=0)
        self.conv = nn.Conv2d(1, hidden, (3, dim), padding=(1, 0))
        self.decoder = nn.Linear(hidden, classes)
        self.dropout = nn.Dropout(p=0.1)

    def main_task(self, h):
        h = self.layer1(h)
        h = self.dropout(h)
        h = self.conv(h.unsqueeze(1)).squeeze(3)
        h = self.activation(h)
        h = F.avg_pool2d(h, (1, h.size(2))).squeeze(2)
        h = self.dropout(h)
        rating = self.decoder(h)
        return rating, h

    def forward(self, data_, mode='train'):
        if mode == 'inference':
            return self.main_task(data_[0])[0]
        else:
            x1 = data_[0]
            y1 = data_[1]

            if len(data_) == 4:
                return
            else:
                y_rating, embed = self.main_task(x1)
                return y_rating, self.loss_func(y_rating, y1)

class BertCls(nn.Module):
    def __init__(self, bert_model, bert_weight, trainable, classes=2):
        super(BertCls, self).__init__()
        self.loss_func = nn.CrossEntropyLoss()
        self.activation = nn.ReLU()
       
        self.pretrained = bert_model.from_pretrained(bert_weight)
       
        for param in self.pretrained.parameters():
            param.requires_grad = False
        
        for i in range(1, trainable+1):
            for param in self.pretrained.encoder.layer[-i].parameters():
                param.requires_grad = True
       
        self.decoder = nn.Linear(768, classes)
        self.dropout = nn.Dropout(p=0.1)

    def main_task(self, h):
        _, h = self.pretrained(h)

        h = self.dropout(h)
        rating = self.decoder(h)
        return rating, h

    def forward(self, data_, mode='train'):
        if mode == 'inference':
            return self.main_task(data_[0])[0]
        else:
            x1 = data_[0]
            y1 = data_[1]

            if len(data_) == 4:
                return
            else:
                y_rating, embed = self.main_task(x1)
                return y_rating, self.loss_func(y_rating, y1)

class DistilBertCls(nn.Module):
    def __init__(self, bert_model, bert_weight, classes=2):
        super(DistilBertCls, self).__init__()
        self.loss_func = nn.CrossEntropyLoss()
        self.activation = nn.ReLU()
       
        self.pretrained = bert_model.from_pretrained(bert_weight)

        #DistilBert
        for param in self.pretrained.parameters():
            param.requires_grad = False
        for param in self.pretrained.transformer.layer[-1].parameters():
            param.requires_grad = True

        self.decoder = nn.Linear(768, classes)
        self.dropout = nn.Dropout(p=0.1)

    def main_task(self, h):
        #64x512x768
        #DistilBert
        h = checkpoint(self.pretrained, h)
        h = h[0][:, 0, :]
        
        #_, h = self.pretrained(h)

        rating = self.decoder(h)
        return rating, h

    def forward(self, data_, mode='train'):
        if mode == 'inference':
            return self.main_task(data_[0])[0]
        else:
            x1 = data_[0]
            y1 = data_[1]

            if len(data_) == 4:
                return
            else:
                y_rating, embed = self.main_task(x1)
                return y_rating, self.loss_func(y_rating, y1)

