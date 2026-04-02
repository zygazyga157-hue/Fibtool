import torch
import torch.nn as nn


class LSTMClassifier(nn.Module):
    def __init__(self, input_size: int, hidden_size: int = 64, num_layers: int = 1, bidirectional: bool = False, dropout: float = 0.1):
        super().__init__()
        self.lstm = nn.LSTM(input_size=input_size, hidden_size=hidden_size, num_layers=num_layers, batch_first=True, bidirectional=bidirectional, dropout=dropout if num_layers>1 else 0.0)
        out_dim = hidden_size * (2 if bidirectional else 1)
        self.head = nn.Sequential(
            nn.Linear(out_dim, out_dim//2),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(out_dim//2, 1)
        )

    def forward(self, x):
        # x: (batch, seq_len, features)
        out, (hn, cn) = self.lstm(x)
        # use last timestep output
        last = out[:, -1, :]
        return self.head(last).squeeze(-1)
