import json

import pytest
import requests


system_config = r"""
- class: REGISTRY
  name: registry
  port: 4998
  type: REST
- class: ACTORSTORE
  name: actorstore
  port: 4999
  type: REST
- class: RUNTIME
  actorstore: $actorstore
  name: server
  registry: $registry
- class: RUNTIME
  actorstore: $actorstore
  name: client
  registry: $server
"""
    
    
def test_simple(system_setup, control_api):
    # We have two runtimes with identical capabilities, 
    # but one is proxy server and one is proxy client.
    # Thus, the 'supernode' information in the registry will reflact that.
    # Use the above facts for a simple sanity test of proxy storage 
    server_uri = system_setup['server']['uri']
    client_uri = system_setup['client']['uri']
    reg_uri = system_setup['registry']['uri']
    status, response = control_api.get_node_id(server_uri)
    assert status == 200
    server_id = response['id']
    assert server_id == system_setup['server']['node_id']
    status, response = control_api.get_node_id(client_uri)
    assert status == 200
    client_id = response['id']
    assert client_id == system_setup['client']['node_id']
    res = requests.get(reg_uri + "/dumpstorage")
    db = res.json()
    key_value_db, indexed_db = db
    print(json.dumps(key_value_db, indent=4))
    print(json.dumps(indexed_db, indent=4))
    
    assert 'node-{}'.format(server_id) in key_value_db
    assert 'node-{}'.format(client_id) in key_value_db

    assert indexed_db["('supernode', '0')"] == [client_id]
    assert indexed_db["('supernode', '0', '1')"] == [server_id]

    assert all([set(value) == set([server_id, client_id]) 
        for key, value in indexed_db.items() 
            if not key.startswith("('supernode',") 
                and not key.startswith("('node/attribute', 'node_name'")])