import torch
import torch.nn as nn


class ResidualBlock(nn.Module):
    """Simple residual block: Linear → ReLU → LayerNorm → Dropout + skip."""

    def __init__(self, dim: int, dropout: float = 0.1):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(dim, dim),
            nn.ReLU(),
            nn.LayerNorm(dim),
            nn.Dropout(float(dropout)),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x + self.net(x)


class AsiaSweepMLP(nn.Module):
    """Plan-aligned tabular classifier.

    - Symbol embedding (categorical)
    - Numeric features (engineered)
    - MLP with LayerNorm + Dropout
    - Optional residual connections for training stability with small data

    Outputs a single logit per sample (use sigmoid for probability).
    """

    def __init__(
        self,
        *,
        num_numeric_features: int,
        num_symbols: int,
        symbol_emb_dim: int = 8,
        hidden_sizes: tuple[int, ...] = (64, 32),
        dropout: float = 0.1,
        use_residual: bool = False,
    ):
        super().__init__()
        self.num_numeric_features = int(num_numeric_features)
        self.num_symbols = int(num_symbols)
        self.symbol_emb_dim = int(symbol_emb_dim)

        if self.num_symbols < 1:
            raise ValueError("num_symbols must be >= 1")
        if self.num_numeric_features < 1:
            raise ValueError("num_numeric_features must be >= 1")

        self.symbol_emb = nn.Embedding(self.num_symbols, self.symbol_emb_dim)

        in_dim = self.num_numeric_features + self.symbol_emb_dim
        layers: list[nn.Module] = []
        prev = in_dim
        for h in hidden_sizes:
            h = int(h)
            layers.append(nn.Linear(prev, h))
            layers.append(nn.ReLU())
            layers.append(nn.LayerNorm(h))
            layers.append(nn.Dropout(float(dropout)))
            if use_residual and prev == h:
                layers.append(ResidualBlock(h, dropout=dropout))
            prev = h
        layers.append(nn.Linear(prev, 1))
        self.mlp = nn.Sequential(*layers)

    def forward(self, x_num: torch.Tensor, symbol_id: torch.Tensor) -> torch.Tensor:
        # x_num: (batch, num_numeric_features)
        # symbol_id: (batch,) long
        if x_num.ndim != 2:
            raise ValueError("x_num must be 2D: (batch, features)")
        if symbol_id.ndim != 1:
            symbol_id = symbol_id.view(-1)

        emb = self.symbol_emb(symbol_id.long())
        x = torch.cat([x_num, emb], dim=1)
        return self.mlp(x).squeeze(-1)


# Backward-compatible baseline kept for older experiments (not plan-aligned).
class MLPClassifier(nn.Module):
    def __init__(self, input_dim: int, hidden_sizes=(128, 64), dropout=0.1):
        super().__init__()
        layers = []
        prev = input_dim
        for h in hidden_sizes:
            layers.append(nn.Linear(prev, h))
            layers.append(nn.ReLU())
            layers.append(nn.BatchNorm1d(h))
            layers.append(nn.Dropout(dropout))
            prev = h
        layers.append(nn.Linear(prev, 1))
        self.net = nn.Sequential(*layers)

    def forward(self, x):
        return self.net(x).squeeze(-1)
