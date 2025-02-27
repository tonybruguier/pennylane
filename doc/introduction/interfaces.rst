.. role:: html(raw)
   :format: html

.. _intro_interfaces:

Gradients and training
======================

PennyLane offers seamless integration between classical and quantum computations. Code up quantum
circuits in PennyLane, compute :doc:`gradients of quantum circuits <glossary/quantum_gradient>`, and
connect them easily to the top scientific computing and machine learning libraries.

Gradients
---------

When creating a QNode, you can specify the :doc:`differentiation method
<glossary/quantum_differentiable_programming>` that PennyLane should use whenever the gradient of
that QNode is requested.

.. code-block:: python

    @qml.qnode(dev, diff_method="parameter-shift")
    def circuit(x):
        qml.RX(x, wires=0)
        return qml.probs(wires=0)

PennyLane currently provides the following differentiation methods for QNodes:

Simulation-based differentiation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The following methods use `reverse accumulation
<https://en.wikipedia.org/wiki/Automatic_differentiation#Reverse_accumulation>`__ to compute
gradients; a well-known example of this approach is backpropagation. These methods are **not** hardware compatible; they are only supported on
*statevector* simulator devices such as :class:`default.qubit <~.DefaultQubit>`.

However, for rapid prototyping on simulators, these methods typically out-perform forward-mode
accumulators such as the parameter-shift rule and finite-differences. For more details, see the
:doc:`quantum backpropagation <demos/tutorial_backprop>` demonstration.

* ``"backprop"``: Use standard backpropagation.

  This differentiation method is only allowed on simulator
  devices that are classically end-to-end differentiable, for example
  :class:`default.qubit <~.DefaultQubit>`. This method does *not* work on devices
  that estimate measurement statistics using a finite number of shots; please use
  the ``parameter-shift`` rule instead.

* ``"adjoint"``: Use a form of backpropagation that takes advantage of the unitary or reversible
  nature of quantum computation.

  The `adjoint method <https://arxiv.org/abs/2009.02823>`__  reverses through the circuit after a
  forward pass by iteratively applying the inverse (adjoint) gate. This method is similar to
  ``"backprop"``, but has significantly lower memory usage and a similar runtime.

Hardware-compatible differentiation
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The following methods support both quantum hardware and simulators, and are examples of `forward
accumulation <https://en.wikipedia.org/wiki/Automatic_differentiation#Forward_accumulation>`__.
However, when using a simulator, you may notice that the time required to compute the gradients
:doc:`scales quadratically <demos/tutorial_backprop>` with the number of trainable circuit
parameters.

* ``"parameter-shift"``: Use the analytic :doc:`parameter-shift rule
  <glossary/parameter_shift>` for all supported quantum operation arguments, with
  finite-difference as a fallback.

* ``"finite-diff"``: Use numerical finite-differences for all quantum operation arguments.


Device gradients
~~~~~~~~~~~~~~~~

* ``"device"``: Queries the device directly for the gradient.
  Only allowed on devices that provide their own gradient computation.


.. note::

    If not specified, the default differentiation method is ``diff_method="best"``. PennyLane
    will attempt to determine the *best* differentiation method given the device and interface.
    Typically, PennyLane will prioritize device-provided gradients, backpropagation, parameter-shift
    rule, and finally finite differences, in that order.


Gradient transforms
-------------------

In addition to registering the differentiation method of QNodes to be used with autodifferentiation
frameworks, PennyLane also provides a library of **gradient transforms** via the
:mod:`qml.gradients <pennylane.gradients>` module.

Quantum gradient transforms are strategies for computing the gradient of a quantum
circuit that work by **transforming** the quantum circuit into one or more gradient circuits.
They accompany these circuits with a function that **post-processes** their output.
These gradient circuits, once executed and post-processed, return the gradient
of the original circuit.

Examples of quantum gradient transforms include finite-difference rules and parameter-shift
rules; these can be applied *directly* to QNodes:

.. code-block:: python

    dev = qml.device("default.qubit", wires=2)

    @qml.qnode(dev)
    def circuit(weights):
        qml.RX(weights[0], wires=0)
        qml.RY(weights[1], wires=1)
        qml.CNOT(wires=[0, 1])
        qml.RX(weights[2], wires=1)
        return qml.probs(wires=1)

>>> weights = np.array([0.1, 0.2, 0.3], requires_grad=True)
>>> circuit(weights)
tensor([0.9658079, 0.0341921], requires_grad=True)
>>> qml.gradients.param_shift(circuit)(weights)
tensor([[-0.04673668, -0.09442394, -0.14409127],
        [ 0.04673668,  0.09442394,  0.14409127]], requires_grad=True)

Note that, while gradient transforms allow quantum gradient rules to be applied directly to QNodes,
this is not a replacement --- and should not be used instead of --- standard training workflows (for example,
``qml.grad()`` if using Autograd, ``loss.backward()`` for PyTorch, or ``tape.gradient()`` for TensorFlow).
This is because gradient transforms do not take into account classical computation nodes, and only
support gradients of QNodes.
For more details on available gradient transforms, as well as learning how to define your own
gradient transform, please see the :mod:`qml.gradients <pennylane.gradients>` documentation.

Training and interfaces
-----------------------

The bridge between the quantum and classical worlds is provided in PennyLane via *interfaces*.
Currently, there are four built-in interfaces: :doc:`NumPy <interfaces/numpy>`, :doc:`PyTorch
<interfaces/torch>`, :doc:`JAX <interfaces/jax>`, and :doc:`TensorFlow <interfaces/tf>`. These
interfaces make each of these libraries quantum-aware, allowing quantum circuits to be treated just
like any other operation. Any interface can be chosen with any device.

In PennyLane, an interface is declared when creating a :class:`QNode <pennylane.QNode>`, e.g.,

.. code-block:: python

    @qml.qnode(dev, interface="tf")
    def my_quantum_circuit(...):
        ...

.. note::
    If no interface is specified, PennyLane will default to the NumPy interface (powered by the
    `autograd <https://github.com/HIPS/autograd>`_ library).

This will allow native numerical objects of the specified library (NumPy arrays, Torch Tensors,
or TensorFlow Tensors) to be passed as parameters to the quantum circuit. It also makes
the gradients of the quantum circuit accessible to the classical library, enabling the
optimization of arbitrary hybrid circuits.

When specifying an interface, the objects of the chosen framework are converted
into NumPy objects and are passed to a device in most cases. Exceptions include
cases when the devices support end-to-end computations in a framework. Such
devices may be referred to as backpropagation or passthru devices.

See the links below for walkthroughs of each specific interface:

.. raw:: html

    <style>
        #interfaces .card {
            box-shadow: none!important;
        }
        #interfaces .card:hover {
            box-shadow: none!important;
        }
    </style>
    <div id="interfaces" class="container mt-2 mb-2">
        <div class="row mt-3">
            <div class="col-lg-3 mb-2 align-items-stretch">
                <a href="interfaces/numpy.html">
                    <div class="card rounded-lg py-2" style="height:100%;">
                        <div class="d-flex justify-content-center align-items-center" style="height:100%;">
                            <img src="../_static/numpy.png" class="card-img-top" style="width:80%;"></img>
                        </div>
                    </div>
                </a>
            </div>
            <div class="col-lg-3 mb-2 align-items-stretch">
                <a href="interfaces/torch.html">
                    <div class="card rounded-lg py-2" style="height:100%;">
                        <div class="d-flex justify-content-center align-items-center" style="height:100%;">
                          <img src="../_static/pytorch.png" class="card-img-top"></img>
                        </div>
                    </div>
                </a>
            </div>
            <div class="col-lg-3 mb-2 align-items-stretch">
                <a href="interfaces/tf.html">
                    <div class="card rounded-lg py-2" style="height:100%;">
                        <div class="d-flex justify-content-center align-items-center" style="height:100%;">
                            <img src="../_static/tensorflow.png" class="card-img-top" style="width:90%;"></img>
                        </div>
                    </div>
                </a>
            </div>
            <div class="col-lg-3 mb-2 align-items-stretch">
                <a href="interfaces/jax.html">
                    <div class="card rounded-lg py-2" style="height:100%;">
                        <div class="d-flex justify-content-center align-items-center" style="height:100%;">
                            <img src="../_static/jax.png" class="card-img-top" style="max-width:60%;"></img>
                        </div>
                    </div>
                </a>
            </div>
        </div>
    </div>

In addition to the core interfaces discussed above, PennyLane also provides higher-level classes for
converting QNodes into both Keras and ``torch.nn`` layers:


:html:`<div class="summary-table">`

.. autosummary::

    pennylane.qnn.KerasLayer
    pennylane.qnn.TorchLayer


.. note::

    QNodes with an interface will always incur a small overhead on evaluation. If you do not
    need to compute quantum gradients of a QNode, specifying ``interface=None`` will remove
    this overhead and result in a slightly faster evaluation. However, gradients will no
    longer be available.


:html:`</div>`

.. toctree::
    :hidden:

    interfaces/numpy
    interfaces/torch
    interfaces/tf
    interfaces/jax
