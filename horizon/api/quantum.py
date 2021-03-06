# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2012 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
#
# Copyright 2012 Cisco Systems, Inc.
# Copyright 2012 NEC Corporation
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

from __future__ import absolute_import

import logging

from quantumclient.v2_0 import client as quantum_client
from django.utils.datastructures import SortedDict

from horizon.api.base import APIDictWrapper, url_for


LOG = logging.getLogger(__name__)


class QuantumAPIDictWrapper(APIDictWrapper):

    def set_id_as_name_if_empty(self, length=8):
        try:
            if not self._apidict['name']:
                id = self._apidict['id']
                if length:
                    id = id[:length]
                self._apidict['name'] = '(%s)' % id
        except KeyError:
            pass

    def items(self):
        return self._apidict.items()


class Network(QuantumAPIDictWrapper):
    """Wrapper for quantum Networks"""
    _attrs = ['name', 'id', 'subnets', 'tenant_id', 'status', 'admin_state_up']

    def __init__(self, apiresource):
        apiresource['admin_state'] = \
            'UP' if apiresource['admin_state_up'] else 'DOWN'
        super(Network, self).__init__(apiresource)


class Subnet(QuantumAPIDictWrapper):
    """Wrapper for quantum subnets"""
    _attrs = ['name', 'id', 'cidr', 'network_id', 'tenant_id',
              'ip_version', 'ipver_str']

    def __init__(self, apiresource):
        apiresource['ipver_str'] = get_ipver_str(apiresource['ip_version'])
        super(Subnet, self).__init__(apiresource)


class Port(QuantumAPIDictWrapper):
    """Wrapper for quantum ports"""
    _attrs = ['name', 'id', 'network_id', 'tenant_id',
              'admin_state_up', 'status', 'mac_address',
              'fixed_ips', 'host_routes', 'device_id']

    def __init__(self, apiresource):
        apiresource['admin_state'] = \
            'UP' if apiresource['admin_state_up'] else 'DOWN'
        super(Port, self).__init__(apiresource)


IP_VERSION_DICT = {4: 'IPv4', 6: 'IPv6'}


def get_ipver_str(ip_version):
    """Convert an ip version number to a human-friendly string"""
    return IP_VERSION_DICT.get(ip_version, '')


def quantumclient(request):
    LOG.debug('quantumclient connection created using token "%s" and url "%s"'
              % (request.user.token.id, url_for(request, 'network')))
    LOG.debug('user_id=%(user)s, tenant_id=%(tenant)s' %
              {'user': request.user.id, 'tenant': request.user.tenant_id})
    c = quantum_client.Client(token=request.user.token.id,
                              endpoint_url=url_for(request, 'network'))
    return c


def network_list(request, **params):
    LOG.debug("network_list(): params=%s" % (params))
    networks = quantumclient(request).list_networks(**params).get('networks')
    # Get subnet list to expand subnet info in network list.
    subnets = subnet_list(request)
    subnet_dict = SortedDict([(s['id'], s) for s in subnets])
    # Expand subnet list from subnet_id to values.
    for n in networks:
        n['subnets'] = [subnet_dict[s] for s in n['subnets']]
    return [Network(n) for n in networks]


def network_get(request, network_id, **params):
    LOG.debug("network_get(): netid=%s, params=%s" % (network_id, params))
    network = quantumclient(request).show_network(network_id,
                                                  **params).get('network')
    # Since the number of subnets per network must be small,
    # call subnet_get() for each subnet instead of calling
    # subnet_list() once.
    network['subnets'] = [subnet_get(request, sid)
                          for sid in network['subnets']]
    return Network(network)


def network_create(request, **kwargs):
    """
    Create a subnet on a specified network.
    :param request: request context
    :param tenant_id: (optional) tenant id of the network created
    :param name: (optional) name of the network created
    :returns: Subnet object
    """
    LOG.debug("network_create(): kwargs = %s" % kwargs)
    body = {'network': kwargs}
    network = quantumclient(request).create_network(body=body).get('network')
    return Network(network)


def network_modify(request, network_id, **kwargs):
    LOG.debug("network_modify(): netid=%s, params=%s" % (network_id, kwargs))
    body = {'network': kwargs}
    network = quantumclient(request).update_network(network_id,
                                                    body=body).get('network')
    return Network(network)


def network_delete(request, network_id):
    LOG.debug("network_delete(): netid=%s" % network_id)
    quantumclient(request).delete_network(network_id)


def subnet_list(request, **params):
    LOG.debug("subnet_list(): params=%s" % (params))
    subnets = quantumclient(request).list_subnets(**params).get('subnets')
    return [Subnet(s) for s in subnets]


def subnet_get(request, subnet_id, **params):
    LOG.debug("subnet_get(): subnetid=%s, params=%s" % (subnet_id, params))
    subnet = quantumclient(request).show_subnet(subnet_id,
                                                **params).get('subnet')
    return Subnet(subnet)


def subnet_create(request, network_id, cidr, ip_version, **kwargs):
    """
    Create a subnet on a specified network.
    :param request: request context
    :param network_id: network id a subnet is created on
    :param cidr: subnet IP address range
    :param ip_version: IP version (4 or 6)
    :param gateway_ip: (optional) IP address of gateway
    :param tenant_id: (optional) tenant id of the subnet created
    :param name: (optional) name of the subnet created
    :returns: Subnet object
    """
    LOG.debug("subnet_create(): netid=%s, cidr=%s, ipver=%d, kwargs=%s"
              % (network_id, cidr, ip_version, kwargs))
    body = {'subnet':
                {'network_id': network_id,
                 'ip_version': ip_version,
                 'cidr': cidr}}
    body['subnet'].update(kwargs)
    subnet = quantumclient(request).create_subnet(body=body).get('subnet')
    return Subnet(subnet)


def subnet_modify(request, subnet_id, **kwargs):
    LOG.debug("subnet_modify(): subnetid=%s, kwargs=%s" % (subnet_id, kwargs))
    body = {'subnet': kwargs}
    subnet = quantumclient(request).update_subnet(subnet_id,
                                                  body=body).get('subnet')
    return Subnet(subnet)


def subnet_delete(request, subnet_id):
    LOG.debug("subnet_delete(): subnetid=%s" % subnet_id)
    quantumclient(request).delete_subnet(subnet_id)


def port_list(request, **params):
    LOG.debug("port_list(): params=%s" % (params))
    ports = quantumclient(request).list_ports(**params).get('ports')
    return [Port(p) for p in ports]


def port_get(request, port_id, **params):
    LOG.debug("port_get(): portid=%s, params=%s" % (port_id, params))
    port = quantumclient(request).show_port(port_id, **params).get('port')
    return Port(port)


def port_create(request, network_id, **kwargs):
    """
    Create a port on a specified network.
    :param request: request context
    :param network_id: network id a subnet is created on
    :param device_id: (optional) device id attached to the port
    :param tenant_id: (optional) tenant id of the port created
    :param name: (optional) name of the port created
    :returns: Port object
    """
    LOG.debug("port_create(): netid=%s, kwargs=%s" % (network_id, kwargs))
    body = {'port': {'network_id': network_id}}
    body['port'].update(kwargs)
    port = quantumclient(request).create_port(body=body).get('port')
    return Port(port)


def port_delete(request, port_id):
    LOG.debug("port_delete(): portid=%s" % port_id)
    quantumclient(request).delete_port(port_id)


def port_modify(request, port_id, **kwargs):
    LOG.debug("port_modify(): portid=%s, kwargs=%s" % (port_id, kwargs))
    body = {'port': kwargs}
    port = quantumclient(request).update_port(port_id, body=body).get('port')
    return Port(port)
