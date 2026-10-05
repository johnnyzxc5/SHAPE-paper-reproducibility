import numpy as np

from shape_ai.contracts import REPRESENTATIONS, to_model_array


def test_cwt_axis_conversion():
    spec = REPRESENTATIONS["shape_cwt"]
    source = np.zeros(spec.disk_shape, dtype=np.float32)
    result = to_model_array(source, spec)
    assert result.shape == spec.tensor_shape
    assert result.flags.c_contiguous


def test_temporal_axis_conversion():
    spec = REPRESENTATIONS["shape_temporal"]
    source = np.zeros(spec.disk_shape, dtype=np.float32)
    result = to_model_array(source, spec)
    assert result.shape == spec.tensor_shape
