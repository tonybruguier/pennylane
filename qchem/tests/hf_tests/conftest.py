import pennylane as qml
import pytest


@pytest.fixture(scope="session")
def tol():
    """Numerical tolerance for equality tests."""
    return {"rtol": 0, "atol": 1e-8}


@pytest.fixture(
    scope="module",
    params=[
        None,
        qml.wires.Wires(
            list("ab") + [-3, 42] + ["xyz", "23", "wireX"] + [f"w{i}" for i in range(20)]
        ),
        list(range(100, 120)),
        {13 - i: "abcdefghijklmn"[i] for i in range(14)},
    ],
)
def custom_wires(request):
    """Custom wire mapping for Pennylane<->OpenFermion conversion"""
    return request.param
