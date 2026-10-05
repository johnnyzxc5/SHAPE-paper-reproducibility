import torch

from shape_ai.models import build_model


def test_multijoint_2d_forward():
    model = build_model("shape_cwt")
    logits, fused, joints = model(torch.zeros(2, 6, 64, 64), return_features=True)
    assert logits.shape == (2, 4)
    assert fused.shape == (2, 768)
    assert joints.shape == (2, 6, 128)


def test_energy_2d_forward():
    model = build_model("energy_cwt")
    logits = model(torch.zeros(2, 1, 64, 64))
    assert logits.shape == (2, 4)

def test_multijoint_1d_forward():
    model = build_model("shape_fft")
    logits = model(torch.zeros(2, 6, 256))
    assert logits.shape == (2, 4)
