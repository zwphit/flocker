# Copyright 2015 ClusterHQ Inc.  See LICENSE file for details.
"""
Operations tests for the control service benchmarks.
"""
from uuid import UUID, uuid4

from zope.interface.verify import verifyObject

from twisted.python.components import proxyForInterface
from twisted.python.filepath import FilePath
from twisted.trial.unittest import TestCase

from flocker.apiclient import IFlockerAPIV1Client, FakeFlockerClient
from flocker.apiclient._client import DatasetState

from benchmark.operations import NoOperation, ReadRequest
from benchmark._operations import IProbe, IOperation


def check_interfaces(factory):

    class OperationTests(TestCase):

        def test_interfaces(self):
            operation = factory(control_service=None)
            verifyObject(IOperation, operation)
            probe = operation.get_probe()
            verifyObject(IProbe, probe)

    testname = '{}InterfaceTests'.format(factory.__name__)
    OperationTests.__name__ = testname
    globals()[testname] = OperationTests

for factory in (NoOperation, ReadRequest):
    check_interfaces(factory)


class FastConvergingFakeFlockerClient(
    proxyForInterface(IFlockerAPIV1Client)
):
    def create_dataset(self, *a, **kw):
        result = self.original.create_dataset(*a, **kw)
        self.original.synchronize_state()
        return result

    def move_dataset(self, *a, **kw):
        result = self.original.move_dataset(*a, **kw)
        self.original.synchronize_state()
        return result

    def delete_dataset(self, *a, **kw):
        result = self.original.delete_dataset(*a, **kw)
        self.original.synchronize_state()
        return result

    def create_container(self, *a, **kw):
        result = self.original.create_container(*a, **kw)
        self.original.synchronize_state()
        return result

    def delete_container(self, *a, **kw):
        result = self.original.delete_container(*a, **kw)
        self.original.synchronize_state()
        return result


class ReadRequestTests(TestCase):

    def test_read_request(self):
        control_service = FastConvergingFakeFlockerClient(FakeFlockerClient())
        primary = uuid4()

        # Create a single dataset on the cluster
        d = control_service.create_dataset(primary=primary)

        # Get the probe to read the state of the cluster
        def start_read_request(result):
            request = ReadRequest(control_service=control_service)
            return request.get_probe()
        d.addCallback(start_read_request)

        # Run the probe to read the state of the cluster
        def run_probe(probe):
            def cleanup(result):
                cleaned_up = probe.cleanup()
                cleaned_up.addCallback(lambda _ignored: result)
                return cleaned_up
            d = probe.run()
            d.addCallback(cleanup)
            return d
        d.addCallback(run_probe)

        # Check the cluster state has one dataset with the correct primary
        def handle_results(states):
            self.assertEqual([state.primary for state in states], [primary])
        d.addCallback(handle_results)

        return d
