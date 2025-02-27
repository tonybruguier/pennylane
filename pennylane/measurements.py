# Copyright 2018-2021 Xanadu Quantum Technologies Inc.

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# pylint: disable=protected-access
"""
This module contains the functions for computing different types of measurement
outcomes from quantum observables - expectation values, variances of expectations,
and measurement samples using AnnotatedQueues.
"""
# pylint: disable=too-many-instance-attributes
import copy
import uuid
import warnings
from enum import Enum
from typing import Generic, TypeVar

import numpy as np

import pennylane as qml
from pennylane.operation import Observable
from pennylane.wires import Wires

# =============================================================================
# ObservableReturnTypes types
# =============================================================================


class ObservableReturnTypes(Enum):
    """Enumeration class to represent the return types of an observable."""

    Sample = "sample"
    Variance = "var"
    Expectation = "expval"
    Probability = "probs"
    State = "state"
    MidMeasure = "measure"

    def __repr__(self):
        """String representation of the return types."""
        return str(self.value)


Sample = ObservableReturnTypes.Sample
"""Enum: An enumeration which represents sampling an observable."""

Variance = ObservableReturnTypes.Variance
"""Enum: An enumeration which represents returning the variance of
an observable on specified wires."""

Expectation = ObservableReturnTypes.Expectation
"""Enum: An enumeration which represents returning the expectation
value of an observable on specified wires."""

Probability = ObservableReturnTypes.Probability
"""Enum: An enumeration which represents returning probabilities
of all computational basis states."""

State = ObservableReturnTypes.State
"""Enum: An enumeration which represents returning the state in the computational basis."""

MidMeasure = ObservableReturnTypes.MidMeasure
"""Enum: An enumeration which represents returning sampling the computational
basis in the middle of the circuit."""


class MeasurementProcess:
    """Represents a measurement process occurring at the end of a
    quantum variational circuit.

    Args:
        return_type (.ObservableReturnTypes): The type of measurement process.
            This includes ``Expectation``, ``Variance``, ``Sample``, ``State``, or ``Probability``.
        obs (.Observable): The observable that is to be measured as part of the
            measurement process. Not all measurement processes require observables (for
            example ``Probability``); this argument is optional.
        wires (.Wires): The wires the measurement process applies to.
            This can only be specified if an observable was not provided.
        eigvals (array): A flat array representing the eigenvalues of the measurement.
            This can only be specified if an observable was not provided.
    """

    # pylint: disable=too-few-public-methods
    # pylint: disable=too-many-arguments

    def __init__(self, return_type, obs=None, wires=None, eigvals=None, id=None):
        self.return_type = return_type
        self.obs = obs
        self.id = id

        if wires is not None and obs is not None:
            raise ValueError("Cannot set the wires if an observable is provided.")

        self._wires = wires or Wires([])
        self._eigvals = None

        if eigvals is not None:
            if obs is not None:
                raise ValueError("Cannot set the eigenvalues if an observable is provided.")

            self._eigvals = np.array(eigvals)

        # TODO: remove the following lines once devices
        # have been refactored to accept and understand recieving
        # measurement processes rather than specific observables.

        # The following lines are only applicable for measurement processes
        # that do not have corresponding observables (e.g., Probability). We use
        # them to 'trick' the device into thinking it has recieved an observable.

        # Below, we imitate an identity observable, so that the
        # device undertakes no action upon recieving this observable.
        self.name = "Identity"
        self.data = []

        # Queue the measurement process
        self.queue()

    def diagonalizing_gates(self):
        """Returns the gates that diagonalize the measured wires such that they
        are in the eigenbasis of the circuit observables.

        Returns:
            List[.Operation]: the operations that diagonalize the observables
        """
        try:
            return self.expand().operations
        except qml.operation.DecompositionUndefinedError:
            return []

    def __repr__(self):
        """Representation of this class."""
        if self.obs is None:
            return f"{self.return_type.value}(wires={self.wires.tolist()})"

        # Todo: when tape is core the return type will always be taken from the MeasurementProcess
        if self.obs.return_type is None:
            return f"{self.return_type.value}({self.obs})"

        return f"{self.obs}"

    def __copy__(self):
        cls = self.__class__

        if self.obs is not None:
            return cls(self.return_type, obs=copy.copy(self.obs))

        return cls(self.return_type, eigvals=self._eigvals, wires=self._wires)

    @property
    def wires(self):
        r"""The wires the measurement process acts on."""
        if self.obs is not None:
            return self.obs.wires
        return self._wires

    @property
    def eigvals(self):
        r"""Eigenvalues associated with the measurement process.

        .. warning::
            The ``eigvals`` property is deprecated and will be removed in
            an upcoming release. Please use :class:`qml.eigvals <.pennylane.eigvals>` instead.

        If the measurement process has an associated observable,
        the eigenvalues will correspond to this observable. Otherwise,
        they will be the eigenvalues provided when the measurement
        process was instantiated.

        Note that the eigenvalues are not guaranteed to be in any
        particular order.

        **Example:**

        >>> m = MeasurementProcess(Expectation, obs=qml.PauliX(wires=1))
        >>> m.get_eigvals()
        array([1, -1])

        Returns:
            array: eigvals representation
        """
        warnings.warn(
            "The 'eigvals' property is deprecated and will be removed in an upcoming release. "
            "Please use 'qml.eigvals' instead.",
            UserWarning,
        )
        return self.get_eigvals()

    def get_eigvals(self):
        r"""Eigenvalues associated with the measurement process.

        If the measurement process has an associated observable,
        the eigenvalues will correspond to this observable. Otherwise,
        they will be the eigenvalues provided when the measurement
        process was instantiated.

        Note that the eigenvalues are not guaranteed to be in any
        particular order.

        **Example:**

        >>> m = MeasurementProcess(Expectation, obs=qml.PauliX(wires=1))
        >>> m.get_eigvals()
        array([1, -1])

        Returns:
            array: eigvals representation
        """
        if self.obs is not None:
            try:
                return self.obs.get_eigvals()
            except qml.operation.EigvalsUndefinedError:
                pass

        return self._eigvals

    def expand(self):
        """Expand the measurement of an observable to a unitary
        rotation and a measurement in the computational basis.

        Returns:
            .QuantumTape: a quantum tape containing the operations
            required to diagonalize the observable

        **Example**

        Consider a measurement process consisting of the expectation
        value of an Hermitian observable:

        >>> H = np.array([[1, 2], [2, 4]])
        >>> obs = qml.Hermitian(H, wires=['a'])
        >>> m = MeasurementProcess(Expectation, obs=obs)

        Expanding this out:

        >>> tape = m.expand()

        We can see that the resulting tape has the qubit unitary applied,
        and a measurement process with no observable, but the eigenvalues
        specified:

        >>> print(tape.operations)
        [QubitUnitary(array([[-0.89442719,  0.4472136 ],
              [ 0.4472136 ,  0.89442719]]), wires=['a'])]
        >>> print(tape.measurements[0].get_eigvals())
        [0. 5.]
        >>> print(tape.measurements[0].obs)
        None
        """
        if self.obs is None:
            raise qml.operation.DecompositionUndefinedError

        with qml.tape.QuantumTape() as tape:
            self.obs.diagonalizing_gates()
            MeasurementProcess(
                self.return_type, wires=self.obs.wires, eigvals=self.obs.get_eigvals()
            )

        return tape

    def queue(self, context=qml.QueuingContext):
        """Append the measurement process to an annotated queue."""
        if self.obs is not None:
            try:
                context.update_info(self.obs, owner=self)
            except qml.queuing.QueuingError:
                self.obs.queue(context=context)
                context.update_info(self.obs, owner=self)

            context.append(self, owns=self.obs)
        else:
            context.append(self)

        return self

    @property
    def hash(self):
        """int: returns an integer hash uniquely representing the measurement process"""
        if self.obs is None:
            fingerprint = (
                str(self.name),
                tuple(self.wires.tolist()),
                str(self.data),
                self.return_type,
            )
        else:
            fingerprint = (
                str(self.obs.name),
                tuple(self.wires.tolist()),
                str(self.obs.data),
                self.return_type,
            )

        return hash(fingerprint)


def expval(op):
    r"""Expectation value of the supplied observable.

    **Example:**

    .. code-block:: python3

        dev = qml.device("default.qubit", wires=2)

        @qml.qnode(dev)
        def circuit(x):
            qml.RX(x, wires=0)
            qml.Hadamard(wires=1)
            qml.CNOT(wires=[0, 1])
            return qml.expval(qml.PauliY(0))

    Executing this QNode:

    >>> circuit(0.5)
    -0.4794255386042029

    Args:
        op (Observable): a quantum observable object

    Raises:
        QuantumFunctionError: `op` is not an instance of :class:`~.Observable`
    """
    if not isinstance(op, (Observable, qml.Hamiltonian)):
        raise qml.QuantumFunctionError(
            f"{op.name} is not an observable: cannot be used with expval"
        )

    return MeasurementProcess(Expectation, obs=op)


def var(op):
    r"""Variance of the supplied observable.

    **Example:**

    .. code-block:: python3

        dev = qml.device("default.qubit", wires=2)

        @qml.qnode(dev)
        def circuit(x):
            qml.RX(x, wires=0)
            qml.Hadamard(wires=1)
            qml.CNOT(wires=[0, 1])
            return qml.var(qml.PauliY(0))

    Executing this QNode:

    >>> circuit(0.5)
    0.7701511529340698

    Args:
        op (Observable): a quantum observable object

    Raises:
        QuantumFunctionError: `op` is not an instance of :class:`~.Observable`
    """
    if not isinstance(op, Observable):
        raise qml.QuantumFunctionError(f"{op.name} is not an observable: cannot be used with var")

    return MeasurementProcess(Variance, obs=op)


def sample(op=None, wires=None):
    r"""Sample from the supplied observable, with the number of shots
    determined from the ``dev.shots`` attribute of the corresponding device.
    If no observable is provided then basis state samples are returned directly
    from the device.

    Args:
        op (Observable or None): a quantum observable object
        wires (Sequence[int] or int or None): the wires we wish to sample from, ONLY set wires if op is None

    Raises:
        QuantumFunctionError: `op` is not an instance of :class:`~.Observable`
        ValueError: Cannot set wires if an observable is provided

    The samples are drawn from the eigenvalues :math:`\{\lambda_i\}` of the observable.
    The probability of drawing eigenvalue :math:`\lambda_i` is given by
    :math:`p(\lambda_i) = |\langle \xi_i | \psi \rangle|^2`, where :math:`| \xi_i \rangle`
    is the corresponding basis state from the observable's eigenbasis.

    **Example**

    .. code-block:: python3

        dev = qml.device("default.qubit", wires=2, shots=4)

        @qml.qnode(dev)
        def circuit(x):
            qml.RX(x, wires=0)
            qml.Hadamard(wires=1)
            qml.CNOT(wires=[0, 1])
            return qml.sample(qml.PauliY(0))

    Executing this QNode:

    >>> circuit(0.5)
    array([ 1.,  1.,  1., -1.])

    If no observable is provided, then the raw basis state samples obtained
    from device are returned (e.g., for a qubit device, samples from the
    computational device are returned). In this case, ``wires`` can be specified
    so that sample results only include measurement results of the qubits of interest.

    .. code-block:: python3

        dev = qml.device("default.qubit", wires=2, shots=4)

        @qml.qnode(dev)
        def circuit(x):
            qml.RX(x, wires=0)
            qml.Hadamard(wires=1)
            qml.CNOT(wires=[0, 1])
            return qml.sample()

    Executing this QNode:

    >>> circuit(0.5)
    array([[0, 1],
           [0, 0],
           [1, 1],
           [0, 0]])

    .. note::

        QNodes that return samples cannot, in general, be differentiated, since the derivative
        with respect to a sample --- a stochastic process --- is ill-defined. The one exception
        is if the QNode uses the parameter-shift method (``diff_method="parameter-shift"``), in which
        case ``qml.sample(obs)`` is interpreted as a single-shot expectation value of the
        observable ``obs``.
    """
    if not isinstance(op, Observable) and op is not None:  # None type is also allowed for op
        raise qml.QuantumFunctionError(
            f"{op.name} is not an observable: cannot be used with sample"
        )

    if wires is not None:
        if op is not None:
            raise ValueError(
                "Cannot specify the wires to sample if an observable is "
                "provided. The wires to sample will be determined directly from the observable."
            )

        return MeasurementProcess(Sample, obs=op, wires=qml.wires.Wires(wires))

    return MeasurementProcess(Sample, obs=op)


def probs(wires=None, op=None):
    r"""Probability of each computational basis state.

    This measurement function accepts either a wire specification or
    an observable. Passing wires to the function
    instructs the QNode to return a flat array containing the
    probabilities :math:`|\langle i | \psi \rangle |^2` of measuring
    the computational basis state :math:`| i \rangle` given the current
    state :math:`| \psi \rangle`.

    Marginal probabilities may also be requested by restricting
    the wires to a subset of the full system; the size of the
    returned array will be ``[2**len(wires)]``.

    **Example:**

    .. code-block:: python3

        dev = qml.device("default.qubit", wires=2)

        @qml.qnode(dev)
        def circuit():
            qml.Hadamard(wires=1)
            return qml.probs(wires=[0, 1])

    Executing this QNode:

    >>> circuit()
    array([0.5, 0.5, 0. , 0. ])

    The returned array is in lexicographic order, so corresponds
    to a :math:`50\%` chance of measuring either :math:`|00\rangle`
    or :math:`|01\rangle`.

    .. code-block:: python3

        dev = qml.device("default.qubit", wires=2)

        H = 1 / np.sqrt(2) * np.array([[1, 1], [1, -1]])

        @qml.qnode(dev)
        def circuit():
            qml.PauliZ(wires=0)
            qml.PauliX(wires=1)
            return qml.probs(op=qml.Hermitian(H, wires=0))

    >>> circuit()

    array([0.14644661 0.85355339])

    The returned array is in lexicographic order, so corresponds
    to a :math:`14.6\%` chance of measuring the rotated :math:`|0\rangle` state
    and :math:`85.4\%` of measuring the rotated :math:`|1\rangle` state.

    Args:
        wires (Sequence[int] or int): the wire the operation acts on
        op (Observable): Observable (with a diagonalzing_gates attribute) that rotates
         the computational basis
    """
    # pylint: disable=protected-access
    if isinstance(op, qml.Hamiltonian):
        raise qml.QuantumFunctionError("Hamiltonians are not supported for rotating probabilities.")

    if op is not None and not qml.operation.defines_diagonalizing_gates(op):
        raise qml.QuantumFunctionError(
            f"{op} does not define diagonalizing gates : cannot be used to rotate the probability"
        )

    if wires is not None:
        if op is not None:
            raise qml.QuantumFunctionError(
                "Cannot specify the wires to probs if an observable is "
                "provided. The wires for probs will be determined directly from the observable."
            )
        return MeasurementProcess(Probability, wires=qml.wires.Wires(wires))
    return MeasurementProcess(Probability, obs=op)


def state():
    r"""Quantum state in the computational basis.

    This function accepts no observables and instead instructs the QNode to return its state. A
    ``wires`` argument should *not* be provided since ``state()`` always returns a pure state
    describing all wires in the device.

    **Example:**

    .. code-block:: python3

        dev = qml.device("default.qubit", wires=2)

        @qml.qnode(dev)
        def circuit():
            qml.Hadamard(wires=1)
            return qml.state()

    Executing this QNode:

    >>> circuit()
    array([0.70710678+0.j, 0.70710678+0.j, 0.        +0.j, 0.        +0.j])

    The returned array is in lexicographic order. Hence, we have a :math:`1/\sqrt{2}` amplitude
    in both :math:`|00\rangle` and :math:`|01\rangle`.

    .. note::

        Differentiating :func:`~.state` is currently only supported when using the
        classical backpropagation differentiation method (``diff_method="backprop"``) with a
        compatible device.

    .. UsageDetails::

        A QNode with the ``qml.state`` output can be used in a cost function with
        is then differentiated:

        >>> dev = qml.device('default.qubit', wires=2)
        >>> qml.qnode(dev, diff_method="backprop")
        ... def test(x):
        ...     qml.RY(x, wires=[0])
        ...     return qml.state()
        >>> def cost(x):
        ...     return np.abs(test(x)[0])
        >>> cost(x)
        tensor(0.98877108, requires_grad=True)
        >>> qml.grad(cost)(x)
        -0.07471906623679961
    """
    # pylint: disable=protected-access
    return MeasurementProcess(State)


def density_matrix(wires):
    r"""Quantum density matrix in the computational basis.

    This function accepts no observables and instead instructs the QNode to return its density
    matrix or reduced density matrix. The ``wires`` argument gives the possibility
    to trace out a part of the system. It can result in obtaining a mixed state, which can be
    only represented by the reduced density matrix.

    **Example:**

    .. code-block:: python3

        dev = qml.device("default.qubit", wires=2)

        @qml.qnode(dev)
        def circuit():
            qml.PauliY(wires=0)
            qml.Hadamard(wires=1)
            return qml.density_matrix([0])

    Executing this QNode:

    >>> circuit()
    array([[0.+0.j 0.+0.j]
        [0.+0.j 1.+0.j]])

    The returned matrix is the reduced density matrix, where system 1 is traced out.

    Args:
        wires (Sequence[int] or int): the wires of the subsystem

    .. note::

        Calculating the derivative of :func:`~.density_matrix` is currently only supported when
        using the classical backpropagation differentiation method (``diff_method="backprop"``)
        with a compatible device.
    """
    # pylint: disable=protected-access
    return MeasurementProcess(State, wires=qml.wires.Wires(wires))


T = TypeVar("T")


class MeasurementValueError(ValueError):
    """Error raised when an unknown measurement value is being used."""


class MeasurementValue(Generic[T]):
    """A class representing unknown measurement outcomes in the qubit model.

    Measurements on a single qubit in the computational basis are assumed.

    Args:
        measurement_id (str): The id of the measurement that this object depends on.
        zero_case (float): the first measurement outcome value
        one_case (float): the second measurement outcome value
    """

    __slots__ = ("_depends_on", "_zero_case", "_one_case", "_control_value")

    def __init__(
        self,
        measurement_id: str,
        zero_case: float = 0,
        one_case: float = 1,
    ):
        self._depends_on = measurement_id
        self._zero_case = zero_case
        self._one_case = one_case
        self._control_value = one_case  # By default, control on the one case

    @property
    def branches(self):
        """A dictionary representing all the possible outcomes of the MeasurementValue."""
        branch_dict = {}
        branch_dict[(0,)] = self._zero_case
        branch_dict[(1,)] = self._one_case
        return branch_dict

    def __invert__(self):
        """Return a copy of the measurement value with an inverted control
        value."""
        inverted_self = copy.copy(self)
        zero = self._zero_case
        one = self._one_case

        inverted_self._control_value = one if self._control_value == zero else zero

        return inverted_self

    def __eq__(self, control_value):
        """Allow asserting measurement values."""
        measurement_outcomes = {self._zero_case, self._one_case}

        if not isinstance(control_value, tuple(type(val) for val in measurement_outcomes)):
            raise MeasurementValueError(
                f"The equality operator is used to assert measurement outcomes, but got a value with type {type(control_value)}."
            )

        if control_value not in measurement_outcomes:
            raise MeasurementValueError(
                f"Unknown measurement value asserted; the set of possible measurement outcomes is: {measurement_outcomes}."
            )

        self._control_value = control_value
        return self

    @property
    def control_value(self):
        """The control value to consider for the measurement outcome."""
        return self._control_value

    @property
    def measurements(self):
        """List of all measurements this MeasurementValue depends on."""
        return [self._depends_on]


def measure(wires):
    """Perform a mid-circuit measurement in the computational basis on the
    supplied qubit.

    Measurement outcomes can be obtained and used to conditionally apply
    operations.

    If a device doesn't support mid-circuit measurements natively, then the
    QNode will apply the :func:`defer_measurements` transform.

    **Example:**

    .. code-block:: python3

        dev = qml.device("default.qubit", wires=2)

        @qml.qnode(dev)
        def func(x, y):
            qml.RY(x, wires=0)
            qml.CNOT(wires=[0, 1])
            m_0 = qml.measure(1)

            qml.cond(m_0, qml.RY)(y, wires=0)
            return qml.probs(wires=[0])

    Executing this QNode:

    >>> pars = np.array([0.643, 0.246], requires_grad=True)
    >>> func(*pars)
    tensor([0.90165331, 0.09834669], requires_grad=True)

    Args:
        wires (Wires): The wire of the qubit the measurement process applies to.

    Raises:
        QuantumFunctionError: if multiple wires were specified
    """
    wire = qml.wires.Wires(wires)
    if len(wire) > 1:
        raise qml.QuantumFunctionError(
            "Only a single qubit can be measured in the middle of the circuit"
        )

    # Create a UUID and a map between MP and MV to support serialization
    measurement_id = str(uuid.uuid4())[:8]
    MeasurementProcess(MidMeasure, wires=wire, id=measurement_id)
    return MeasurementValue(measurement_id)
