import pytest
import time

import ray
from ray.air.checkpoint import Checkpoint
from ray.air.predictor import (
    Predictor,
    DataBatchType,
    PredictorNotSerializableException,
)
from ray.air.batch_predictor import BatchPredictor


class DummyPredictor(Predictor):
    def __init__(self, factor: float = 1.0):
        self.factor = factor

    @classmethod
    def from_checkpoint(cls, checkpoint: Checkpoint, **kwargs) -> "DummyPredictor":
        checkpoint_data = checkpoint.to_dict()
        return DummyPredictor(**checkpoint_data)

    def predict(self, data: DataBatchType, **kwargs) -> DataBatchType:
        return data * self.factor


class DummyPredictorFS(DummyPredictor):
    @classmethod
    def from_checkpoint(cls, checkpoint: Checkpoint, **kwargs) -> "DummyPredictor":
        with checkpoint.as_directory():
            # simulate reading
            time.sleep(1)
        checkpoint_data = checkpoint.to_dict()
        return DummyPredictor(**checkpoint_data)


def test_serialization():
    """Tests that Predictor instances are not serializable."""

    # Class is serializable.
    ray.put(DummyPredictor)

    # Instance is not serializable.
    predictor = DummyPredictor()
    with pytest.raises(PredictorNotSerializableException):
        ray.put(predictor)


def test_batch_prediction():
    batch_predictor = BatchPredictor.from_checkpoint(
        Checkpoint.from_dict({"factor": 2.0}), DummyPredictor
    )

    test_dataset = ray.data.from_items([1.0, 2.0, 3.0, 4.0])
    assert batch_predictor.predict(
        test_dataset
    ).to_pandas().to_numpy().squeeze().tolist() == [
        2.0,
        4.0,
        6.0,
        8.0,
    ]


def test_batch_prediction_fs():
    batch_predictor = BatchPredictor.from_checkpoint(
        Checkpoint.from_dict({"factor": 2.0}), DummyPredictorFS
    )

    test_dataset = ray.data.from_items([1.0, 2.0, 3.0, 4.0] * 32).repartition(8)
    assert (
        batch_predictor.predict(test_dataset, min_scoring_workers=4)
        .to_pandas()
        .to_numpy()
        .squeeze()
        .tolist()
        == [
            2.0,
            4.0,
            6.0,
            8.0,
        ]
        * 32
    )


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main(["-sv", __file__]))
