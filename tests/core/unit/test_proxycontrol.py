from unittest.mock import Mock

import pytest

from calvin.runtime.north import calvincontrol
from calvin.runtime.north.calvin_network import CalvinNetwork
from calvin.runtime.north.calvin_proto import CalvinProto



def test_control_tunnel_server():
    # Give the dummy node communication power (for proxy tests)
    node = Mock()
    node.control_uri = "http://localhost:5001"
    node.control = calvincontrol.CalvinControl(node, node.control_uri, node.control_uri)
    node.network = CalvinNetwork(node)
    node.proto = CalvinProto(node, node.network)

#    ts = calvincontrol.CalvinControlTunnelServer(node, None)

    tunnel = Mock()
    tunnel.peer_node_id = "other_id"

    assert node.control.tunnel_request_handles(tunnel)
    tunnel.register_tunnel_down.assert_called_once()
    tunnel.register_tunnel_up.assert_called_once()
    tunnel.register_recv.assert_called_once()
    assert node.control.controltunnels[tunnel.peer_node_id]
    control_tunnel = node.control.controltunnels[tunnel.peer_node_id]
    print(control_tunnel)

    tunnel.send.assert_called_once()
    for index, call_ in enumerate(tunnel.method_calls):
        name, args, kwargs = call_
        print(name, args, kwargs)

    assert node.control.tunnel_up(tunnel)


    node.control.tunnel_recv_handler(tunnel, {})
    for index, call_ in enumerate(tunnel.method_calls):
        name, args, kwargs = call_
        print(name, args, kwargs)

    assert node.control.tunnel_down(tunnel)
    assert tunnel.peer_node_id not in node.control.controltunnels
    assert tunnel.peer_node_id not in node.control.tunnels
    # tunnel.close.assert_called_once()
