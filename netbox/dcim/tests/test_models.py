from django.test import TestCase

from dcim.constants import *
from dcim.models import *


class RackTestCase(TestCase):

    def setUp(self):

        self.site1 = Site.objects.create(
            name='TestSite1',
            slug='test-site-1'
        )
        self.site2 = Site.objects.create(
            name='TestSite2',
            slug='test-site-2'
        )
        self.group1 = RackGroup.objects.create(
            name='TestGroup1',
            slug='test-group-1',
            site=self.site1
        )
        self.group2 = RackGroup.objects.create(
            name='TestGroup2',
            slug='test-group-2',
            site=self.site2
        )
        self.rack = Rack.objects.create(
            name='TestRack1',
            facility_id='A101',
            site=self.site1,
            group=self.group1,
            u_height=42
        )
        self.manufacturer = Manufacturer.objects.create(
            name='Acme',
            slug='acme'
        )

        self.device_type = {
            'ff2048': DeviceType.objects.create(
                manufacturer=self.manufacturer,
                model='FrameForwarder 2048',
                slug='ff2048'
            ),
            'cc5000': DeviceType.objects.create(
                manufacturer=self.manufacturer,
                model='CurrentCatapult 5000',
                slug='cc5000',
                u_height=0
            ),
        }
        self.role = {
            'Server': DeviceRole.objects.create(
                name='Server',
                slug='server',
            ),
            'Switch': DeviceRole.objects.create(
                name='Switch',
                slug='switch',
            ),
            'Console Server': DeviceRole.objects.create(
                name='Console Server',
                slug='console-server',
            ),
            'PDU': DeviceRole.objects.create(
                name='PDU',
                slug='pdu',
            ),

        }

    def test_rack_device_outside_height(self):

        rack1 = Rack(
            name='TestRack2',
            facility_id='A102',
            site=self.site1,
            u_height=42
        )
        rack1.save()

        device1 = Device(
            name='TestSwitch1',
            device_type=DeviceType.objects.get(manufacturer__slug='acme', slug='ff2048'),
            device_role=DeviceRole.objects.get(slug='switch'),
            site=self.site1,
            rack=rack1,
            position=43,
            face=RACK_FACE_FRONT,
        )
        device1.save()

        with self.assertRaises(ValidationError):
            rack1.clean()

    def test_rack_group_site(self):

        rack_invalid_group = Rack(
            name='TestRack2',
            facility_id='A102',
            site=self.site1,
            u_height=42,
            group=self.group2
        )
        rack_invalid_group.save()

        with self.assertRaises(ValidationError):
            rack_invalid_group.clean()

    def test_mount_single_device(self):

        device1 = Device(
            name='TestSwitch1',
            device_type=DeviceType.objects.get(manufacturer__slug='acme', slug='ff2048'),
            device_role=DeviceRole.objects.get(slug='switch'),
            site=self.site1,
            rack=self.rack,
            position=10,
            face=RACK_FACE_REAR,
        )
        device1.save()

        # Validate rack height
        self.assertEqual(list(self.rack.units), list(reversed(range(1, 43))))

        # Validate inventory (front face)
        rack1_inventory_front = self.rack.get_front_elevation()
        self.assertEqual(rack1_inventory_front[-10]['device'], device1)
        del(rack1_inventory_front[-10])
        for u in rack1_inventory_front:
            self.assertIsNone(u['device'])

        # Validate inventory (rear face)
        rack1_inventory_rear = self.rack.get_rear_elevation()
        self.assertEqual(rack1_inventory_rear[-10]['device'], device1)
        del(rack1_inventory_rear[-10])
        for u in rack1_inventory_rear:
            self.assertIsNone(u['device'])

    def test_mount_zero_ru(self):
        pdu = Device.objects.create(
            name='TestPDU',
            device_role=self.role.get('PDU'),
            device_type=self.device_type.get('cc5000'),
            site=self.site1,
            rack=self.rack,
            position=None,
            face=None,
        )
        self.assertTrue(pdu)


class CableTestCase(TestCase):

    def setUp(self):

        site = Site.objects.create(name='Test Site 1', slug='test-site-1')
        manufacturer = Manufacturer.objects.create(name='Test Manufacturer 1', slug='test-manufacturer-1')
        devicetype = DeviceType.objects.create(
            manufacturer=manufacturer, model='Test Device Type 1', slug='test-device-type-1'
        )
        devicerole = DeviceRole.objects.create(
            name='Test Device Role 1', slug='test-device-role-1', color='ff0000'
        )
        self.device1 = Device.objects.create(
            device_type=devicetype, device_role=devicerole, name='TestDevice1', site=site
        )
        self.device2 = Device.objects.create(
            device_type=devicetype, device_role=devicerole, name='TestDevice2', site=site
        )
        self.interface1 = Interface.objects.create(device=self.device1, name='eth0')
        self.interface2 = Interface.objects.create(device=self.device2, name='eth0')
        self.cable = Cable(termination_a=self.interface1, termination_b=self.interface2)
        self.cable.save()

        self.power_port1 = PowerPort.objects.create(device=self.device2, name='psu1')
        self.patch_pannel = Device.objects.create(
            device_type=devicetype, device_role=devicerole, name='TestPatchPannel', site=site
        )
        self.rear_port = RearPort.objects.create(device=self.patch_pannel, name='R1', type=1000)
        self.front_port = FrontPort.objects.create(
            device=self.patch_pannel, name='F1', type=1000, rear_port=self.rear_port
        )

    def test_cable_creation(self):
        """
        When a new Cable is created, it must be cached on either termination point.
        """
        interface1 = Interface.objects.get(pk=self.interface1.pk)
        self.assertEqual(self.cable.termination_a, interface1)
        interface2 = Interface.objects.get(pk=self.interface2.pk)
        self.assertEqual(self.cable.termination_b, interface2)

    def test_cable_deletion(self):
        """
        When a Cable is deleted, the `cable` field on its termination points must be nullified.
        """
        self.cable.delete()
        interface1 = Interface.objects.get(pk=self.interface1.pk)
        self.assertIsNone(interface1.cable)
        interface2 = Interface.objects.get(pk=self.interface2.pk)
        self.assertIsNone(interface2.cable)

    def test_cabletermination_deletion(self):
        """
        When a CableTermination object is deleted, its attached Cable (if any) must also be deleted.
        """
        self.interface1.delete()
        cable = Cable.objects.filter(pk=self.cable.pk).first()
        self.assertIsNone(cable)

    def test_cable_validates_compatibale_types(self):
        """
        The clean method should have a check to ensure only compatiable port types can be connected by a cable
        """
        # An interface cannot be connected to a power port
        cable = Cable(termination_a=self.interface1, termination_b=self.power_port1)
        with self.assertRaises(ValidationError):
            cable.clean()

    def test_cable_cannot_have_the_same_terminination_on_both_ends(self):
        """
        A cable cannot be made with the same A and B side terminations
        """
        cable = Cable(termination_a=self.interface1, termination_b=self.interface1)
        with self.assertRaises(ValidationError):
            cable.clean()

    def test_cable_front_port_cannot_connect_to_corresponding_rear_port(self):
        """
        A cable cannot connect a front port to its sorresponding rear port
        """
        cable = Cable(termination_a=self.front_port, termination_b=self.rear_port)
        with self.assertRaises(ValidationError):
            cable.clean()

    def test_cable_cannot_be_connected_to_an_existing_connection(self):
        """
        Either side of a cable cannot be terminated when that side aready has a connection
        """
        # Try to create a cable with the same interface terminations
        cable = Cable(termination_a=self.interface2, termination_b=self.interface1)
        with self.assertRaises(ValidationError):
            cable.clean()

    def test_cable_cannot_connect_to_a_virtual_inteface(self):
        """
        A cable connection cannot include a virtual interface
        """
        virtual_interface = Interface(device=self.device1, name="V1", type=0)
        cable = Cable(termination_a=self.interface2, termination_b=virtual_interface)
        with self.assertRaises(ValidationError):
            cable.clean()


class CablePathTestCase(TestCase):

    def setUp(self):

        site = Site.objects.create(name='Test Site 1', slug='test-site-1')
        manufacturer = Manufacturer.objects.create(name='Test Manufacturer 1', slug='test-manufacturer-1')
        devicetype = DeviceType.objects.create(
            manufacturer=manufacturer, model='Test Device Type 1', slug='test-device-type-1'
        )
        devicerole = DeviceRole.objects.create(
            name='Test Device Role 1', slug='test-device-role-1', color='ff0000'
        )
        self.device1 = Device.objects.create(
            device_type=devicetype, device_role=devicerole, name='Test Device 1', site=site
        )
        self.device2 = Device.objects.create(
            device_type=devicetype, device_role=devicerole, name='Test Device 2', site=site
        )
        self.interface1 = Interface.objects.create(device=self.device1, name='eth0')
        self.interface2 = Interface.objects.create(device=self.device2, name='eth0')
        self.panel1 = Device.objects.create(
            device_type=devicetype, device_role=devicerole, name='Test Panel 1', site=site
        )
        self.panel2 = Device.objects.create(
            device_type=devicetype, device_role=devicerole, name='Test Panel 2', site=site
        )
        self.rear_port1 = RearPort.objects.create(
            device=self.panel1, name='Rear Port 1', type=PORT_TYPE_8P8C
        )
        self.front_port1 = FrontPort.objects.create(
            device=self.panel1, name='Front Port 1', type=PORT_TYPE_8P8C, rear_port=self.rear_port1
        )
        self.rear_port2 = RearPort.objects.create(
            device=self.panel2, name='Rear Port 2', type=PORT_TYPE_8P8C
        )
        self.front_port2 = FrontPort.objects.create(
            device=self.panel2, name='Front Port 2', type=PORT_TYPE_8P8C, rear_port=self.rear_port2
        )

    def test_path_completion(self):

        # First segment
        cable1 = Cable(termination_a=self.interface1, termination_b=self.front_port1)
        cable1.save()
        interface1 = Interface.objects.get(pk=self.interface1.pk)
        self.assertIsNone(interface1.connected_endpoint)
        self.assertIsNone(interface1.connection_status)

        # Second segment
        cable2 = Cable(termination_a=self.rear_port1, termination_b=self.rear_port2)
        cable2.save()
        interface1 = Interface.objects.get(pk=self.interface1.pk)
        self.assertIsNone(interface1.connected_endpoint)
        self.assertIsNone(interface1.connection_status)

        # Third segment
        cable3 = Cable(termination_a=self.front_port2, termination_b=self.interface2, status=CONNECTION_STATUS_PLANNED)
        cable3.save()
        interface1 = Interface.objects.get(pk=self.interface1.pk)
        self.assertEqual(interface1.connected_endpoint, self.interface2)
        self.assertEqual(interface1.connection_status, CONNECTION_STATUS_PLANNED)

        # Switch third segment from planned to connected
        cable3.status = CONNECTION_STATUS_CONNECTED
        cable3.save()
        interface1 = Interface.objects.get(pk=self.interface1.pk)
        self.assertEqual(interface1.connected_endpoint, self.interface2)
        self.assertEqual(interface1.connection_status, CONNECTION_STATUS_CONNECTED)

    def test_path_teardown(self):

        # Build the path
        cable1 = Cable(termination_a=self.interface1, termination_b=self.front_port1)
        cable1.save()
        cable2 = Cable(termination_a=self.rear_port1, termination_b=self.rear_port2)
        cable2.save()
        cable3 = Cable(termination_a=self.front_port2, termination_b=self.interface2)
        cable3.save()
        interface1 = Interface.objects.get(pk=self.interface1.pk)
        self.assertEqual(interface1.connected_endpoint, self.interface2)
        self.assertEqual(interface1.connection_status, CONNECTION_STATUS_CONNECTED)

        # Remove a cable
        cable2.delete()
        interface1 = Interface.objects.get(pk=self.interface1.pk)
        self.assertIsNone(interface1.connected_endpoint)
        self.assertIsNone(interface1.connection_status)
        interface2 = Interface.objects.get(pk=self.interface2.pk)
        self.assertIsNone(interface2.connected_endpoint)
        self.assertIsNone(interface2.connection_status)
