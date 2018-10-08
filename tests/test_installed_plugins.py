"""
Unit tests for all installed plugins.
"""

import unittest
from unittest_data_provider import data_provider
import logging as log
log.getLogger()

from pkg_resources import iter_entry_points
import inspect

import openqml as qm
import numpy as np

import traceback #todo: remove once we no longer capture the exception further down

# import autograd
# import autograd.numpy as np
# from autograd.numpy.random import (randn,)

# from matplotlib.pyplot import figure

from defaults import openqml as qm, BaseTest
from openqml import Device

class PluginTest(BaseTest):
    """Plugin test.
    """
    def all_plugins():
        return tuple([ (entry,) for entry in iter_entry_points('openqml.plugins')])

    @data_provider(all_plugins)
    def test_resolve_all_plugins(self, plugin):
        obj = plugin.resolve()
        self.assertIsNotNone(obj, msg="Plugin "+plugin.name+" advertised entry point "+str(plugin)+" but it could not be resolved.")

    @data_provider(all_plugins)
    def test_load_all_plugins(self, plugin):
        device = plugin.load()
        self.assertIsNotNone(device, msg="Plugin "+plugin.name+" advertised device "+str(plugin)+" but it could not be loaded.")

    @data_provider(all_plugins)
    def test_plugin_device(self, plugin):
        class IgnoreOperationException(Exception):
            pass

        print("Testing "+plugin.name+" plugin:")
        obj = plugin.resolve()
        device = plugin.load()
        wires = 3 #This should be as large as the largest gate/observable, but we cannot know that before instantiating the device. We thus check later that all gates/observables fit.

        #fullargspec = inspect.getfullargspec(obj)
        #print(fullargspec)
        #print(fullargspec.args[1::])

        sig = inspect.signature(obj)

        if 'cutoff_dim' in sig.parameters:
            bind = sig.bind_partial(wires=wires, cutoff_dim=5)
        else:
            bind = sig.bind_partial(wires=wires)
        bind.apply_defaults()

        try:
            dev = device(*bind.args, **bind.kwargs)

        except (ValueError, TypeError) as e:
            print("The device "+plugin.name+" could not be instantiated with only the standard parameters because ("+str(e)+"). Skipping automatic test.")
            return

        # run all single gate circuits
        for gate in dev.gates:
            for observable in dev.observables:
                print("Testing "+plugin.name+": "+gate+" and "+observable)

                @qm.qfunc(dev)
                def circuit():
                    gate_class = getattr(qm, gate)
                    observable_class = getattr(qm.expectation, observable)

                    if gate_class.n_wires > wires:
                        raise IgnoreOperationException('Skipping because the operation '+gate+" acts on more than the default number of wires "+str(wires)+". Maybe you want to increase that?")
                    if observable_class.n_wires > wires:
                        raise IgnoreOperationException('Skipping because the observable '+observable+" acts on more than the default number of wires "+str(wires)+". Maybe you want to increase that?")

                    if gate_class.par_domain == 'N':
                        gate_pars = np.random.randint(0, 5, gate_class.n_params)
                    elif gate_class.par_domain == 'R':
                        gate_pars = np.abs(np.random.randn(gate_class.n_params)) #todo: some operations/expectations fail when parameters are negative (e.g. thermal state) but par_domain is not fine grained enough to capture this
                    elif gate_class.par_domain == 'A':
                        raise IgnoreOperationException('Skipping because of the operation '+gate)#todo: For these gates it is impossible to guess the size and all constrains on the matrix

                    if observable_class.par_domain == 'N':
                        observable_pars = np.random.randint(0, 5, observable_class.n_params)
                    if observable_class.par_domain == 'R':
                        observable_pars = np.abs(np.random.randn(observable_class.n_params)) #todo: some operations/expectations fail when parameters are negative (e.g. thermal state) but par_domain is not fine grained enough to capture this
                    elif observable_class.par_domain == 'A':
                        raise IgnoreOperationException('Skipping because of the observable '+observable)#todo: For these expectations it is impossible to guess the size and all constrains on the matrix

                    # apply to the first wires
                    gate_wires = list(range(gate_class.n_wires)) if gate_class.n_wires > 1 else 0
                    observable_wires = list(range(observable_class.n_wires)) if observable_class.n_wires > 1 else 0

                    gate_class(*gate_pars, gate_wires)
                    return observable_class(*observable_pars, observable_wires)

                try:
                    circuit()
                except IgnoreOperationException as e:
                    print(e)
                except Exception as e:
                    print(e)#todo: currently it is good that this just prints all the errors to get a quick overview, but we either want an assert here or not catch the exception in the first place
                    try:
                        raise e
                    except:
                        pass

                    traceback.print_exc()


if __name__ == '__main__':
    # run the tests in this file
    suite = unittest.TestSuite()
    for t in (PluginTest,):
        ttt = unittest.TestLoader().loadTestsFromTestCase(t)
        suite.addTests(ttt)

    unittest.TextTestRunner().run(suite)
