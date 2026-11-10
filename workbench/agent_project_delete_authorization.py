"""Fresh exact project cascade grants and their standalone attachment evidence."""

import hashlib
import re
import secrets
import time

from .agent_security import AgentError, allows
from .deletion_inventory import fingerprint
from .project_identity import valid_new_id


FIELDS = {'capability':'projects.delete', 'operations':['delete'], 'minimum_confirmation_mode':'local_web'}
ASSET_ID = re.compile(r'ASSET-(?:[0-9a-f]{32}|[0-9]+(?:-[0-9]+)?)')
SHA256 = re.compile(r'[0-9a-f]{64}')


def grant_value(grants=None):
    return {'schema_version':1, 'grants':[] if grants is None else grants}


def normalize_project_delete_grants(value):
    if not isinstance(value, dict) or set(value) != {'schema_version', 'grants'} or type(value['schema_version']) is not int or value['schema_version'] != 1 or not isinstance(value['grants'], list) or len(value['grants']) > 100:
        raise ValueError('项目级联授权格式无效')
    projects = set()
    result = []
    for grant in value['grants']:
        if not isinstance(grant, dict) or set(grant) != {*FIELDS, 'project_id', 'assets'} or any(grant[key] != expected for key, expected in FIELDS.items()):
            raise ValueError('项目级联授权只支持 projects.delete/delete/local_web')
        key = valid_new_id(grant['project_id'])
        if grant['project_id'] == '*' or key in projects or not isinstance(grant['assets'], list) or len(grant['assets']) > 4096:
            raise ValueError('项目级联授权必须选择各个具体项目')
        projects.add(key)
        assets = {}
        for asset in grant['assets']:
            if not isinstance(asset, dict) or set(asset) != {'id', 'evidence'} or not isinstance(asset['id'], str) or not ASSET_ID.fullmatch(asset['id']) or asset['id'] in assets or not isinstance(asset['evidence'], str) or not SHA256.fullmatch(asset['evidence']):
                raise ValueError('项目级联授权附件证据无效')
            assets[asset['id']] = asset
        result.append({**FIELDS, 'project_id':grant['project_id'], 'assets':[assets[key] for key in sorted(assets)]})
    return grant_value(sorted(result, key=lambda grant:grant['project_id']))


def client_project_delete_grants(client):
    if client.get('authorization_schema_version', 1) != 8:
        if 'project_delete_grants' in client:
            raise AgentError('invalid_configuration', '旧授权不能包含生效的项目级联删除授权', 503)
        return grant_value()
    try:
        return normalize_project_delete_grants(client['project_delete_grants'])
    except (KeyError, TypeError, ValueError):
        raise AgentError('invalid_configuration', '项目级联删除授权格式无效', 503) from None


def project_delete_grant(client, project_id):
    if client.get('enabled') is not True or not {'read', 'propose', 'commit'} <= set(client.get('scopes', ())) or not allows(client, {'project_id':project_id}):
        return None
    return next((grant for grant in client_project_delete_grants(client)['grants'] if grant['project_id'] == project_id), None)


def asset_evidence(assets):
    return sorted(({'id':asset['id'], 'evidence':fingerprint(asset)} for asset in assets), key=lambda item:item['id'])


def upgraded_project_delete_client(before, grants):
    from .agent_project_authorization import grant_value as create_grant
    after = {**before, 'authorization_schema_version':8,
             'project_delete_grants':normalize_project_delete_grants(grants),
             'management_revision':before.get('management_revision', 0) + 1}
    for field in ('concept_map_grants', 'delete_grants'):
        after.setdefault(field, {'schema_version':1, 'grants':[]})
    after.setdefault('project_create_grant', create_grant(False))
    return after


def grant_details(root, project_id, asset_ids):
    from .project_delete_tree import classify_tree, read_tree
    try:
        valid_new_id(project_id)
        if not isinstance(asset_ids, list) or len(asset_ids) > 4096 or len(asset_ids) != len(set(asset_ids)) or any(not ASSET_ID.fullmatch(key) for key in asset_ids):
            raise ValueError('项目附件选择无效')
        tree = read_tree(root, root / 'projects' / project_id)
        project, _, assets, _ = classify_tree(root, project_id, tree)
        selected = [asset for asset in assets if asset['id'] in asset_ids]
        if len(selected) != len(asset_ids):
            raise ValueError('选择的附件已变化')
        return {'project_id':project_id, 'title':project['title'], 'tree_digest':tree.physical_digest,
                'selected_assets':selected, 'unselected_assets':[asset for asset in assets if asset['id'] not in asset_ids]}
    except (OSError, ValueError, TypeError, KeyError, AgentError):
        raise AgentError('resource_changed', '无法核验原项目或附件选择，请在本机核查', 409) from None


def replacement_grants(before, details):
    previous = client_project_delete_grants(before)['grants']
    new = {**FIELDS, 'project_id':details['project_id'], 'assets':asset_evidence(details['selected_assets'])}
    return grant_value([grant for grant in previous if grant['project_id'] != new['project_id']] + [new])


def validate_delete_grant_intent(value):
    if value.get('operation_family') != 'project_delete':
        return
    from .agent_management import digest
    try:
        action, selection = value['project_delete_action'], value['project_delete_selection']
        if value['schema_version'] != 8 or action not in {'approve', 'revoke'} or not SHA256.fullmatch(value['project_delete_digest']):
            raise ValueError()
        if action == 'approve':
            if set(selection) != {'project_id', 'tree_digest', 'assets'} or not SHA256.fullmatch(selection['tree_digest']):
                raise ValueError()
            selected = normalize_project_delete_grants(grant_value([{**FIELDS, 'project_id':selection['project_id'], 'assets':selection['assets']}]))['grants'][0]
        elif selection is not None:
            raise ValueError()
        if value['state'] not in {'prepared', 'recovery_required'}:
            return
        before, after = value['before_client'], value['after_client']
        if action == 'approve':
            if before.get('enabled') is not True or not {'read', 'propose', 'commit'} <= set(before['scopes']) or not allows(before, {'project_id':selected['project_id']}):
                raise ValueError()
            grants = grant_value([grant for grant in client_project_delete_grants(before)['grants'] if grant['project_id'] != selected['project_id']] + [selected])
        else:
            if before.get('authorization_schema_version') != 8:
                raise ValueError()
            grants = grant_value()
        if before['client_id'] != value['client_id'] or after != upgraded_project_delete_client(before, grants) or value['before_config'] != value['after_config'] or digest(after['project_delete_grants']) != value['project_delete_digest']:
            raise ValueError()
    except (ValueError, TypeError, KeyError, AgentError):
        raise AgentError('management_recovery_required', '项目级联授权意图和证据不一致', 503) from None


class ProjectDeleteGrantManagement:
    def __init__(self, runtime):
        from .agent_delete_authorization import DeleteGrantManagement
        self.runtime = runtime
        self.management = DeleteGrantManagement(runtime)
        self.security = self.management.security
        self.repository = runtime.repository

    def list(self, key):
        from .agent_management import client_version
        client = self.management.client(key, enabled=False)
        return {'workspace_id':self.security.workspace_id, 'client_id':key, 'expected_version':client_version(client),
                'grants':client_project_delete_grants(client),
                'projects':[{'id':item['id'], 'name':item['name']} for item in self.repository.list_projects()
                            if allows(client, {'project_id':item['id']})]}

    def _check(self, payload, keys):
        if not isinstance(payload, dict) or set(payload) != {'workspace_id', 'expected_version', *keys} or payload['workspace_id'] != self.security.workspace_id or not isinstance(payload['expected_version'], str) or not SHA256.fullmatch(payload['expected_version']):
            raise AgentError('invalid_request', '项目级联授权参数无效')

    def preview(self, key, payload):
        from .agent_delete_service import checked_preview
        from .agent_management import credential_lock
        self._check(payload, ('project_id', 'asset_ids'))
        with self.repository.write_lock, credential_lock(self.security.config_dir):
            client = self.management.client(key, payload['expected_version'])
            if not {'read', 'propose', 'commit'} <= set(client['scopes']) or not allows(client, {'project_id':payload['project_id']}):
                raise AgentError('forbidden', '项目级联删除需原项目读取及完整基本权限', 403)
            details = grant_details(self.repository.root, payload['project_id'], payload['asset_ids'])
            preview = {**self.list(key), 'client_name':client['name'], 'selection':details,
                       'after':normalize_project_delete_grants(replacement_grants(client, details)),
                       'disclosure':'只更新所选项目的级联删除授权。未明确选中的独立附件将阻止删除。每个实际子记录另需已有读、删权，每次移动都须单独完整预览并在本机批准。授权变化使原版本绑定的暂存和附件策略失效。'}
            token = secrets.token_hex(32)
            signature = fingerprint(preview)
            result = checked_preview({**preview, 'preview_id':token, 'preview_digest':signature})
            now = time.monotonic()
            tickets = self.runtime.preview_tickets
            for old, ticket in list(tickets.items()):
                if ticket.get('expires', ticket.get('file_expiry', float('inf'))) <= now:
                    del tickets[old]
            if len(tickets) >= 1000:
                raise AgentError('preview_limit', '管理预览过多，请稍后重试', 429)
            tickets[token] = {'project_delete_preview':preview, 'digest':signature, 'session':self.runtime._token,
                              'runtime_version':self.runtime.status()['version'], 'expires':now + 600}
            return result

    def approve(self, key, payload):
        from .agent_management import credential_lock
        self._check(payload, ('preview_id', 'preview_digest', 'request_id', 'approved'))
        if payload['approved'] is not True or any(not isinstance(payload[key], str) or not SHA256.fullmatch(payload[key]) for key in ('preview_id', 'preview_digest')) or not isinstance(payload['request_id'], str) or not re.fullmatch(r'[A-Za-z0-9._:-]{1,100}', payload['request_id']):
            raise AgentError('invalid_request', '必须明确批准当前项目级联授权预览')
        params = {'approval_digest':payload['preview_digest']}
        with self.repository.write_lock, credential_lock(self.security.config_dir):
            manager = self.security.manager()
            operation_id = hashlib.sha256(payload['request_id'].encode()).hexdigest()
            if not (manager.directory / f'{operation_id}.json').exists():
                ticket = self.runtime.preview_tickets.get(payload['preview_id'], {})
                preview = ticket.get('project_delete_preview', {})
                if ticket.get('expires', 0) <= time.monotonic() or ticket.get('session') != self.runtime._token or ticket.get('runtime_version') != self.runtime.status()['version'] or ticket.get('digest') != payload['preview_digest'] or fingerprint(preview) != payload['preview_digest'] or preview.get('client_id') != key or preview.get('expected_version') != payload['expected_version']:
                    raise AgentError('preview_expired', '项目级联授权预览失效，请重新完整预览', 409)
                self.management.client(key, payload['expected_version'])
                details = preview['selection']
                params['selection'] = {'project_id':details['project_id'], 'tree_digest':details['tree_digest'],
                                       'assets':asset_evidence(details['selected_assets'])}
            return manager.run('project_delete_grant', params, key, payload['expected_version'], payload['request_id'])

    def revoke(self, key, payload):
        self._check(payload, ('request_id',))
        with self.repository.write_lock:
            return self.security.manager().run('project_delete_grant_revoke', {}, key, payload['expected_version'], payload['request_id'])
