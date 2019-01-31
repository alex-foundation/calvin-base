# -*- coding: utf-8 -*-

# Copyright (c) 2018 Ericsson AB
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json
from calvin.requests import calvinresponse
from calvin.utilities.calvinlogger import get_logger
from calvin.utilities.calvin_callback import CalvinCB
from calvin.utilities.issuetracker import IssueTracker
# from calvin.csparser import cscompile as compiler
# from calvin.csparser.dscodegen import calvin_dscodegen
from calvin.runtime.north.appmanager import Deployer
from calvin.runtime.north.plugins.port import DISCONNECT
from calvin.utilities.security import security_enabled
from routes import register, handler
from authentication import authentication_decorator
from calvin.utilities.replication_defs import PRE_CHECK, REPLICATION_STATUS

_log = get_logger(__name__)

# FIXME: Which ones are needed? Which ones should be in debug API? 

# USED BY: GUI, CSWEB, CSCONTROL
@handler(method="GET", path="/applications")
@authentication_decorator
def handle_get_applications(self, handle, connection, match, data, hdr):
    """
    GET /applications
    Get applications launched from this node
    Response status code: OK
    Response: List of application ids
    """
    self.send_response(handle, connection, json.dumps(self.node.app_manager.list_applications()))

# USED BY: GUI, CSWEB, CSCONTROL
@handler(method="DELETE", path="/application/{application_id}")
@authentication_decorator
def handle_del_application(self, handle, connection, match, data, hdr):
    """
    DELETE /application/{application-id}
    Stop application (only applications launched from this node)
    Response status code: OK, NOT_FOUND, INTERNAL_ERROR
    Response: [<actor_id>, ...] when error list of actors (replicas) in application not destroyed
    """
    try:
        self.node.app_manager.destroy(match.group(1), cb=CalvinCB(self.handle_del_application_cb,
                                                                    handle, connection))
    except:
        _log.exception("Destroy application failed")
        self.send_response(handle, connection, None, status=calvinresponse.INTERNAL_ERROR)

@register
def handle_del_application_cb(self, handle, connection, status=None):
    if not status and status.data:
        data = json.dumps(status.data)
    else:
        data = None
    self.send_response(handle, connection, data, status=status.status)


# DEPRECATED
@handler(method="POST", path="/actor")
@authentication_decorator
def handle_new_actor(self, handle, connection, match, data, hdr):
    """
    POST /actor
    Create a new actor
    NOTE: this should only be allowed for testing purposes as it allows bypassing application signature
    verification.
    Body:
    {
        "actor_type:" <type of actor>,
        "args" : { "name": <name of actor>, <actor argument>:<value>, ... }
        "deploy_args" : {"app_id": <application id>, "app_name": <application name>} (optional)
    }
    Response status code: OK or INTERNAL_ERROR
    Response: {"actor_id": <actor-id>}
    """
    try:
        actor_id = self.node.new(actor_type=data['actor_type'], args=data['args'],
                                 security=self.security,
                                 access_decision=True,
                                 deploy_args=data['deploy_args'])
        status = calvinresponse.OK
    except:
        _log.exception("Failed when creating actor %s" % data['actor_type'])
        actor_id = None
        status = calvinresponse.INTERNAL_ERROR
    self.send_response(
        handle, connection, None if actor_id is None else json.dumps({'actor_id': actor_id}), status=status)


# USED BY: GUI, CSCONTROL
@handler(method="GET", path="/actors")
@authentication_decorator
def handle_get_actors(self, handle, connection, match, data, hdr):
    """
    GET /actors
    Get list of actors on this runtime
    Response status code: OK
    Response: list of actor ids
    """
    actors = self.node.am.list_actors()
    self.send_response(
        handle, connection, json.dumps(actors))

# DEPRECATED
@handler(method="DELETE", path="/actor/{actor_id}")
@authentication_decorator
def handle_del_actor(self, handle, connection, match, data, hdr):
    """
    DELETE /actor/{actor-id}
    Delete actor
    Response status code: OK or NOT_FOUND
    Response: none
    """
    try:
        self.node.am.destroy(match.group(1))
        status = calvinresponse.OK
    except:
        _log.exception("Destroy actor failed")
        status = calvinresponse.NOT_FOUND
    self.send_response(handle, connection, None, status=status)

@register
def _actor_report(self, handle, connection, match, data, hdr):
    try:
        # Now we allow passing in arguments (must be dictionary or None)
        report = self.node.am.report(match.group(1), data)
        status = calvinresponse.OK
    except:
        _log.exception("Actor report failed")
        report = None
        status = calvinresponse.NOT_FOUND
    self.send_response(handle, connection, None if report is None else json.dumps(report, default=repr), status=status)

# DEPRECATED: Perhaps used in Kappa?
@handler(method="GET", path="/actor/{actor_id}/report")
@authentication_decorator
def handle_get_actor_report(self, handle, connection, match, data, hdr):
    """
    GET /actor/{actor-id}/report
    Some actor store statistics on inputs and outputs, this reports these. Not always present.
    Response status code: OK or NOT_FOUND
    Response: Depends on actor
    """
    self._actor_report(handle, connection, match, data, hdr)

# DEPRECATED
@handler(method="POST", path="/actor/{actor_id}/report")
@authentication_decorator
def handle_post_actor_report(self, handle, connection, match, data, hdr):
    """
    POST /actor/{actor-id}/report
    Some actors accept external input using this function. Not always present.
    Response status code: OK or NOT_FOUND
    Response: Depends on actor
    """
    self._actor_report(handle, connection, match, data, hdr)


@register
def handle_actor_migrate_proto_cb(self, handle, connection, status, *args, **kwargs):
    self.send_response(handle, connection, None, status=status.status)

@register
def handle_actor_migrate_lookup_peer_cb(self, key, value, handle, connection, actor_id, peer_node_id):
    if calvinresponse.isnotfailresponse(value):
        self.node.proto.actor_migrate_direct(value['node_id'],
            CalvinCB(self.handle_actor_migrate_proto_cb, handle, connection),
            actor_id,
            peer_node_id)
    else:
        self.send_response(handle, connection, None, status=calvinresponse.NOT_FOUND)

# USED BY: GUI, CSWEB, CSCONTROL
@handler(method="POST", path="/actor/{actor_id}/migrate")
@authentication_decorator
def handle_actor_migrate(self, handle, connection, match, data, hdr):
    """
    POST /actor/{actor-id}/migrate
    Migrate actor to (other) node, either explicit node_id or by updated requirements
    Body: {"peer_node_id": <node-id>}
    Alternative body:
    Body:
    {
        "requirements": [ {"op": "<matching rule name>",
                          "kwargs": {<rule param key>: <rule param value>, ...},
                          "type": "+" or "-" for set intersection or set removal, respectively
                          }, ...
                        ],
        "extend": True or False  # defaults to False, i.e. replace current requirements
        "move": True or False  # defaults to False, i.e. when possible stay on the current node
    }

    For further details about requirements see application deploy.
    Response status code: OK, BAD_REQUEST, INTERNAL_ERROR or NOT_FOUND
    Response: none
    """
    status = calvinresponse.OK
    actor_id = match.group(1)
    if 'peer_node_id' in data:
        if actor_id in self.node.am.list_actors():
            try:
                self.node.am.migrate(actor_id, data['peer_node_id'],
                                 callback=CalvinCB(self.actor_migrate_cb, handle, connection))
            except:
                _log.exception("Migration failed")
                status = calvinresponse.INTERNAL_ERROR
        else:
            self.node.storage.get_actor(actor_id,
                CalvinCB(func=self.handle_actor_migrate_lookup_peer_cb, handle=handle, connection=connection,
                    actor_id=actor_id, peer_node_id=data['peer_node_id']))
    elif 'requirements' in data:
        try:
            self.node.am.update_requirements(match.group(1), data['requirements'],
                extend=data['extend'] if 'extend' in data else False,
                move=data['move'] if 'move' in data else False,
                callback=CalvinCB(self.actor_migrate_cb, handle, connection))
        except:
            _log.exception("Migration failed")
            status = calvinresponse.INTERNAL_ERROR
    else:
        status=calvinresponse.BAD_REQUEST

    if status != calvinresponse.OK:
        self.send_response(handle, connection, None, status=status)

@register
def actor_migrate_cb(self, handle, connection, status, *args, **kwargs):
    """ Migrate actor respons
    """
    self.send_response(handle, connection, None, status=status.status)

# DEPRECATED
@handler(method="POST", path="/actor/{actor_id}/disable")
@authentication_decorator
def handle_actor_disable(self, handle, connection, match, data, hdr):
    """
    POST /actor/{actor-id}/disable
    DEPRECATED. Disables an actor
    Response status code: OK or NOT_FOUND
    Response: none
    """
    try:
        self.node.am.disable(match.group(1))
        status = calvinresponse.OK
    except:
        status = calvinresponse.NOT_FOUND
    self.send_response(handle, connection, None, status)

# USED BY: CSWEB
@handler(method="POST", path="/actor/{replication_id}/replicate")
@authentication_decorator
def handle_actor_replicate(self, handle, connection, match, data, hdr):
    """
    POST /actor/{replication-id}/replicate
    Will replicate an actor having manual_scaling requirement applied
    Currently must be sent to the runtime having the elected replication manager for the replication id
    Response status code: OK or NOT_FOUND
    """
    data = {} if data is None else data
    try:
        _log.debug("MANUAL REPLICATION ORDERED")
        replication_id = match.group(1)
        node_id = data.get('peer_node_id', None)
        replicate = not data.get('dereplicate', False)
        op = PRE_CHECK.SCALE_OUT if replicate else PRE_CHECK.SCALE_IN
        if (self.node.rm.managed_replications[replication_id].operation != PRE_CHECK.NO_OPERATION or
            self.node.rm.managed_replications[replication_id].status != REPLICATION_STATUS.READY):
            # Can't order another operation while processing previous
            self.send_response(handle, connection, None, calvinresponse.SERVICE_UNAVAILABLE)
            _log.debug("MANUAL REPLICATION NOT APPLIED %s" % PRE_CHECK.reverse_mapping[op])
            return
        # This must be done on the node that is elected leader for the replication_id
        # Return NOT_FOUND otherwise
        self.node.rm.managed_replications[replication_id].operation = op
        self.node.rm.managed_replications[replication_id].selected_node_id = node_id
        self.node.sched.replication_direct(replication_id=replication_id)
        _log.debug("MANUAL REPLICATION APPLIED %s" % PRE_CHECK.reverse_mapping[op])
        self.send_response(handle, connection, None, calvinresponse.OK)
    except:
        _log.exception("Failed manual replication")
        self.send_response(handle, connection, None, calvinresponse.NOT_FOUND)

@register
def handle_actor_replicate_cb(self, handle, connection, status):
    self.send_response(handle, connection, json.dumps(status.data), status=status.status)

# USED BY: GUI, CSWEB
@handler(method="GET", path="/actor/{actor_id}/port/{port_id}/state")
@authentication_decorator
def handle_get_port_state(self, handle, connection, match, data, hdr):
    """
    GET /actor/{actor-id}/port/{port-id}/state
    Get port state {port-id} of actor {actor-id}
    Response status code: OK or NOT_FOUND
    """
    state = {}
    try:
        state = self.node.am.get_port_state(match.group(1), match.group(2))
        status = calvinresponse.OK
    except:
        status = calvinresponse.NOT_FOUND
    self.send_response(handle, connection, json.dumps(state), status)

# DEPRECATED
@handler(method="POST", path="/connect")
@authentication_decorator
def handle_connect(self, handle, connection, match, data, hdr):
    """
    POST /connect
    Connect actor ports
    Body:
    {
        "actor_id" : <actor-id>,
        "port_name": <port-name>,
        "port_dir": <in/out>,
        "peer_node_id": <node-id>,
        "peer_actor_id": <actor-id>,
        "peer_port_name": <port-name>,
        "peer_port_dir": <out/in>
    }
    Response status code: OK, BAD_REQUEST, INTERNAL_ERROR or NOT_FOUND
    Response: {"peer_port_id": <peer port id>}
    """
    # FIXME: The long and winding construct should be replaced by the more concise:
    #        self.node.connect(**data, cb=CalvinCB(self.handle_connect_cb, handle, connection))
    self.node.connect(
        actor_id=data.get("actor_id"),
        port_name=data.get("port_name"),
        port_dir=data.get("port_dir"),
        port_properties=data.get("port_properties"),
        port_id=data.get("port_id"),
        peer_node_id=data.get("peer_node_id"),
        peer_actor_id=data.get("peer_actor_id"),
        peer_port_name=data.get("peer_port_name"),
        peer_port_dir=data.get("peer_port_dir"),
        peer_port_properties=data.get("peer_port_properties"),
        peer_port_id=data.get("peer_port_id"),
        cb=CalvinCB(self.handle_connect_cb, handle, connection))

# DEPRECATED
@register
def handle_connect_cb(self, handle, connection, **kwargs):
    status = kwargs.get('status', None)
    peer_port_id = kwargs.get('peer_port_id', None)
    self.send_response(handle, connection, json.dumps({'peer_port_id': peer_port_id}) if status else None,
                       status=status.status)
    _log.debug("Handle connect finnished")

# DEPRECATED
@handler(method="POST", path="/set_port_property")
@authentication_decorator
def handle_set_port_property(self, handle, connection, match, data, hdr):
    """
    POST /set_port_property
    Sets a property of the port.
    Body:
    {
        "actor_id" : <actor-id>,
        "port_type": <in/out>,
        "port_name": <port-name>,
        "port_id": <port-id>, optionally instead of the above identifiers
        "port_property": <property-name as string>
        "value" : <property value>
    }
    Response status code: OK, BAD_REQUEST or NOT_FOUND
    Response: none
    """
    try:
        if data.get("port_properties") is None:
            status = self.node.pm.set_port_property(
                port_id=data.get("port_id"),
                actor_id=data.get("actor_id"),
                port_dir=data.get("port_type"),
                port_name=data.get("port_name"),
                port_property=data.get("port_property"),
                value=data.get("value"))
        else:
            status = self.node.pm.set_port_properties(
                port_id=data.get("port_id"),
                actor_id=data.get("actor_id"),
                port_dir=data.get("port_type"),
                port_name=data.get("port_name"),
                **data.get("port_properties"))
    except:
        _log.exception("Failed setting port property")
        status = calvinresponse.CalvinResponse(calvinresponse.NOT_FOUND)
    self.send_response(handle, connection, None, status=status.status)


# DEPRECATED
# FIXME: This was compile_script_check_security but now we only get deployable 
#        => we just need to check integrity according to policy
def check_security(data, cb, security=None, content=None, verify=True, node=None, signature=None):
    """
    'credentials' are optional security credentials(?)
    'verify' is deprecated and will be removed
    'node' is the runtime performing security check(?)
    'cb' is a CalvinCB callback

    N.B. If callback 'cb' is given, this method calls cb(deployable, errors, warnings) and returns None
    N.B. If callback 'cb' is given, and method runs to completion, cb is called with additional parameter 'security' (?)
    """
    def _exit_with_error(callback):
        """Helper method to generate a proper error"""
        it = IssueTracker()
        it.add_error("UNAUTHORIZED", info={'status':401})
        callback({}, it)
        return

    # FIXME: data -> deployable, and app_info mandatory
    def _handle_policy_decision(data, appname, verify, access_decision, org_cb, security=None):
        if not access_decision:
            _log.error("Access denied")
            # This error reason is detected in calvin control and gives proper REST response
            _exit_with_error(org_cb)
            return
        if 'app_info' not in data and 'script' in data:
            deployable, issuetracker = compile_script(data['script'], appname)
        elif 'app_info' in data:
            deployable = data['app_info']
            issuetracker = IssueTracker()
        else:
            _log.error("Neither app_info or script supplied")
            # This error reason is detected in calvin control and gives proper REST response
            _exit_with_error(org_cb)
            return
        org_cb(deployable, issuetracker, security=security)

    #
    # Actual code for compile_script
    #
    # FIXME: if node is None we bypass security even if enabled. Is that the intention?
    if security_enabled():
        # FIXME: If cb is None, we will return from this method with None instead of a tuple, failing silently
        if security:
            sec = security
        else:
            sec = Security(node)


        verified, signer = sec.verify_signature_content(content, "application")
        if not verified:
            # Verification not OK if sign or cert not OK.
            _log.error("Failed application verification")
            # This error reason is detected in calvin control and gives proper REST response
            _exit_with_error(cb)
            return
        sec.check_security_policy(
            CalvinCB(_handle_policy_decision, data, appname, verify, security=security, org_cb=cb),
            element_type = "application",
            element_value = signer
        )
        return

    #
    # We get here if node is None, or security is disabled
    #
    # This used to be
    # _handle_policy_decision(data, filename, verify, access_decision=True, security=None, org_cb=cb)
    # but since _handle_policy_decision is called with access_decision=True, security=None only compile_script would be called
    if 'app_info' in data:
        deployable = data['app_info']
        issuetracker = IssueTracker()
    cb(deployable, issuetracker, security=None)


# FIXME: Check integrity according to policy
# USED BY: GUI, CSWEB, CSCONTROL
@handler(method="POST", path="/deploy")
@authentication_decorator
def handle_deploy(self, handle, connection, match, data, hdr):
    """
    POST /deploy
    Compile and deploy a calvin script to this calvin node
    Apply deployment requirements to actors of an application
    and initiate migration of actors accordingly
    Body:
    {
        "app_info": ...
        "app_info_signature": <hex encoded signature based on app_info (JSON, compact, sorted)
        "deploy_info": ...
    }

    Response status code: OK, CREATED, BAD_REQUEST, UNAUTHORIZED or INTERNAL_ERROR
    Response: {"application_id": <application-id>,
               "actor_map": {<actor name with namespace>: <actor id>, ...}
               "placement": {<actor_id>: <node_id>, ...},
               "requirements_fulfilled": True/False}
    Failure response: {'errors': <compilation errors>,
                       'warnings': <compilation warnings>,
                       'exception': <exception string>}
    """

    try:
        # FIXME: Clean up deployer next
        d = Deployer(
                deployable=data,
                node=self.node,
                security=self.security,
                verify=True,
                cb=CalvinCB(self.handle_deploy_cb, handle, connection)
            )
        print self.node.id, "Deployer instantiated"
        d.deploy()
    except Exception as e:
        print "Deployer failed"
        self.send_response(
            handle,
            connection,
            json.dumps({'exception': str(e)}),
            status=calvinresponse.INTERNAL_ERROR
        )

@register
def handle_deploy_cb(self, handle, connection, status, deployer, **kwargs):
    _log.analyze(self.node.id, "+ DEPLOYED", {'status': status.status})
    if status:
        print "DEPLOY STATUS", str(status)
        self.send_response(handle, connection,
                           json.dumps({'application_id': deployer.app_id,
                                       'actor_map': deployer.actor_map,
                                       'replication_map': deployer.replication_map,
                                       'placement': kwargs.get('placement', None),
                                       'requirements_fulfilled': status.status == calvinresponse.OK}
                                      ) if deployer.app_id else None,
                           status=status.status)
    else:
        self.send_response(handle, connection, None, status=status.status)


# USED BY: GUI, CSWEB, CSCONTROL
@handler(method="POST", path="/application/{application_id}/migrate")
@authentication_decorator
def handle_post_application_migrate(self, handle, connection, match, data, hdr):
    """
    POST /application/{application-id}/migrate
    Update deployment requirements of application application-id
    and initiate migration of actors.
    Body:
    {
        "deploy_info":
           {"requirements": {
                "<actor instance 1 name>": [ {"op": "<matching rule name>",
                                              "kwargs": {<rule param key>: <rule param value>, ...},
                                              "type": "+" or "-" for set intersection or set removal, respectively
                                              }, ...
                                           ],
                ...
                            }
           }
    }
    For more details on deployment information see application deploy.
    Response status code: OK, INTERNAL_ERROR or NOT_FOUND
    Response: none
    """
    app_id = match.group(1)
    try:
        self.node.app_manager.migrate_with_requirements(app_id,
                                               deploy_info=data["deploy_info"] if "deploy_info" in data else None,
                                               move=data["move"] if "move" in data else False,
                                               cb=CalvinCB(self.handle_post_application_migrate_cb, handle, connection))
    except:
        _log.exception("App migration failed")
        self.send_response(handle, connection, None, status=calvinresponse.INTERNAL_ERROR)

@register
def handle_post_application_migrate_cb(self, handle, connection, status, **kwargs):
    _log.analyze(self.node.id, "+ MIGRATED", {'status': status.status})
    self.send_response(handle, connection, None, status=status.status)

# DEPRECATED
@handler(method="POST", path="/disconnect")
@authentication_decorator
def handle_disconnect(self, handle, connection, match, data, hdr):
    """
    POST /disconnect
    Disconnect a port.
    If port fields are empty, all ports of the actor are disconnected
    Body:
    {
        "actor_id": <actor-id>,
        "port_name": <port-name>,
        "port_dir": <in/out>,
        "port_id": <port-id>
    }
    Response status code: OK, INTERNAL_ERROR or NOT_FOUND
    Response: none
    """
    actor_id = data.get('actor_id', None)
    port_name = data.get('port_name', None)
    port_dir = data.get('port_dir', None)
    port_id = data.get('port_id', None)
    # Convert type of disconnect as string to enum value
    # Allowed values TEMPORARY, TERMINATE, EXHAUST
    terminate = data.get('terminate', "TEMPORARY")
    try:
        terminate = DISCONNECT.__getattribute__(DISCONNECT, terminate)
    except:
        terminate = DISCONNECT.TEMPORARY

    _log.debug("disconnect(actor_id=%s, port_name=%s, port_dir=%s, port_id=%s)" %
               (actor_id if actor_id else "", port_name if port_name else "",
                port_dir if port_dir else "", port_id if port_id else ""))
    self.node.pm.disconnect(actor_id=actor_id, port_name=port_name,
                       port_dir=port_dir, port_id=port_id, terminate=terminate,
                       callback=CalvinCB(self.handle_disconnect_cb, handle, connection))

# DEPRECATED
@register
def handle_disconnect_cb(self, handle, connection, **kwargs):
    status = kwargs.get('status', None)
    _log.analyze(self.node.id, "+ DISCONNECTED", {'status': status.status}, tb=True)
    self.send_response(handle, connection, None, status=status.status)
