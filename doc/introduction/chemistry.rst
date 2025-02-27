Quantum Chemistry
=================

PennyLane provides a differentiable Hartree-Fock solver module :mod:`~.hf` and a quantum chemistry
module :mod:`~.qchem` to perform quantum simulations of the electronic structure of molecules. These
modules contain tools to construct the electronic Hamiltonian of molecules that can be used to
implement the Variational Quantum Eigensolver (VQE) algorithm.

.. figure:: ../_static/sketch_pennylane_qchem.png
    :width: 80%
    :align: center

.. note::

    To access the ``qchem`` module, the ``PennyLane-QChem`` plugin must be installed separately:

    .. code-block::

        pip install pennylane-qchem

Building the electronic Hamiltonian
-----------------------------------

The ``qchem`` module provides access to a driver function :func:`~.molecular_hamiltonian`
to generate the electronic Hamiltonian in a single call. For example,

.. code-block:: python

    from pennylane import qchem
    import numpy as np

    symbols, coordinates = (['H', 'H'], np.array([0., 0., -0.66140414, 0., 0., 0.66140414]))
    h, qubits = qchem.molecular_hamiltonian(
        symbols,
        coordinates,
        charge=0,
        mult=1,
        basis='sto-3g',
        active_electrons=2,
        active_orbitals=2
    )

where:

* ``h`` is the qubit Hamiltonian of the molecule represented as a PennyLane Hamiltonian, and

* ``qubits`` is the number of qubits needed to perform the quantum simulation.

Internally, :func:`~.molecular_hamiltonian` calls the following functions in order
to generate the qubit Hamiltonian:

.. currentmodule:: pennylane_qchem.qchem

.. autosummary::

    read_structure
    meanfield
    active_space
    decompose


For more fine-grained control, these functions may be
called independently as required.


Importing molecular structure data
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The atomic structure of a molecule can be imported from an external file using the
:func:`~.read_structure` function:

.. code-block:: python

    >>> symbols, coordinates = qchem.read_structure('h2.xyz')
    >>> print(symbols, coordinates)
    ['H', 'H'] [0.    0.   -0.66140414    0.    0.    0.66140414]

The geometry of the molecule is returned as a list containing the symbol and the Cartesian
coordinates of each atomic species.

Solving the Hartree-Fock equations
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The :func:`~.meanfield` function uses the `OpenFermion-PySCF <https://github
.com/quantumlib/OpenFermion-PySCF>`_ and `OpenFermion-Psi4 <https://github
.com/quantumlib/OpenFermion-Psi4>`_ plugins to solve the Hartree-Fock equations for the molecule
using the electronic structure packages `PySCF <https://github.com/sunqm/pyscf>`_ and `Psi4
<http://psicode.org/>`_, respectively.

For this, it is required to specify a string to label the molecule. Furthermore, the net charge,
the `spin multiplicity <https://en.wikipedia.org/wiki/Multiplicity_(chemistry)>`_ and the  `atomic basis functions <https://www.basissetexchange.org/>`_ can also be specified.

.. code-block:: python

    symbols, coordinates = qchem.read_structure('h2o.xyz')
    hf_file = qchem.meanfield(
        symbols,
        coordinates,
        name='water',
        charge=-1,
        mult=2,
        basis='6-31g',
        package='pyscf'
    )

The output ``hf_file`` is the absolute path to the file containing
the Hartree-Fock electronic structure of the water molecule.

Mapping the Hamiltonian to the Pauli basis
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The function :func:`~.active_space` is used to create an `active space <https://en.wikipedia
.org/wiki/Complete_active_space>`__  by classifying the Hartree-Fock molecular orbitals as
core, active, and external orbitals. Within this approximation, a certain number of *active electrons* can populate the *active orbitals*.

.. code-block:: python

    from openfermion import MolecularData
    water = MolecularData(filename=hf_file)
    core, active = qchem.active_space(
        water.n_electrons,
        water.n_orbitals,
        mult=2,
        active_electrons=3,
        active_orbitals=4
    )

Once we have defined the active space, :func:`~.decompose` uses
OpenFermion functionalities to generate the second-quantized fermionic Hamiltonian
and map it to a linear combination of Pauli operators via the `Jordan-Wigner
<https://en.wikipedia.org/wiki/Jordan%E2%80%93Wigner_transformation>`__ or `Bravyi-Kitaev
<https://arxiv.org/abs/1208.5986>`__ transformation. For example,

.. code-block:: python

    qubit_hamiltonian = qchem.decompose(
        hf_file,
        mapping='jordan_wigner',
        core=core,
        active=active
    )

Here, ``qubit_hamiltonian`` is an instance of the QubitOperator class of `OpenFermion <https://github.com/quantumlib/OpenFermion>`_.

.. _pl_qchem_vqe:

VQE simulations
---------------

The Variational Quantum Eigensolver (VQE) is a hybrid quantum-classical computational scheme,
where a quantum computer is used to prepare the trial wave function of a molecule and to measure
the expectation value of the *electronic Hamiltonian*, while a classical optimizer is used to
find its ground state.

PennyLane supports treating Hamiltonians just like any other observable, and the 
expectation value of a Hamiltonian can be calculated using ``qml.expval``:

.. code-block:: python

    import pennylane as qml

    dev = qml.device('default.qubit', wires=4)

    hamiltonian = 2.0 * qml.PauliZ(0) @ qml.PauliZ(1)

    @qml.qnode(dev)
    def circuit(params):
        qml.BasisState(np.array([1, 1, 0, 0]), wires=[0,1,2,3])
        for i in range(4):
            qml.Rot(*params[i], wires=i)
        qml.CNOT(wires=[2, 3])
        qml.CNOT(wires=[2, 0])
        qml.CNOT(wires=[3, 1])
        return qml.expval(hamiltonian)

    rng = np.random.default_rng(seed=42)
    params = rng.random([4, 3])
    circuit(params)

The rotation angles can be optimized using the machine learning interface of choice
until the energy difference between two consecutive iterations has converged to near zero.

.. note::

    For more details on VQE and the quantum chemistry functionality available in ``qml.qchem``,
    check out the PennyLane quantum chemistry tutorials.
