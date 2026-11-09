"""Scoped attachment proposals and static attachment@1 execution contracts."""

import hashlib
import json
import re
import uuid
import mimetypes
import os
from pathlib import Path

from .agent_security import AgentError, require_scope
from .agent_upload_policy import authorized_owner, active_policies
from .agent_execution import fingerprint, authorization_revision
from .write_coordinator import content_revision, PreparedMarkdownWrite
from .attachment_prepared import PreparedAttachment, categories, serialize_attachment_candidate as serialized, raw_markdown_body, COMMIT_TIME
from .security import validate_archive_member, validate_portable_filename


STEPS = ['binary_copy', 'binary_publish', 'history_snapshot', 'metadata_write', 'upload_consume']
FIELDS = {'owner_kind', 'owner_id', 'upload_id', 'display_name', 'category', 'insert_link'}


def consumption_id(operation_id):
    return hashlib.sha256(operation_id.encode()).hexdigest()


def relative_paths(view):
    binary = Path(validate_archive_member(view['binary_relative']))
    metadata = Path(validate_archive_member(view['metadata_relative']))
    kind = view['owner_kind']
    expected = ('projects', view['project_id'], 'assets', 'library' if kind == 'project' else 'images' if view['attachment']['mime'].startswith('image/') else 'files', view['attachment']['name'])
    if binary.parts != expected:
        raise ValueError('附件二进制目标不属于指定归属')
    if kind == 'project':
        valid = metadata.parts == ('projects', view['owner_id'], 'assets', 'index.json') and view['owner_id'] == view['project_id']
        relative = binary.relative_to(Path('projects') / view['project_id']).as_posix()
    else:
        valid = len(metadata.parts) == 4 and metadata.parts[:3] == ('projects', view['project_id'], {'issue':'issues', 'todo':'todos', 'info':'infos'}[kind]) and metadata.name.startswith(view['owner_id'] + '-') and metadata.suffix == '.md'
        relative = Path(os.path.relpath(binary, metadata.parent)).as_posix()
    if not valid or view['attachment']['path'] != relative:
        raise ValueError('附件元数据目标或相对链接不属于归属')
    return binary, metadata


def logical_plan(proposal):
    view = proposal.get('normalized_content')
    if view is None:
        return proposal['execution_plan']
    return {'handler':'attachment@1', 'kind':'attachment', 'operation':'create',
            'target':{'id':proposal['target_id'], **proposal['access_target']},
            'candidate_digest':fingerprint(view), 'steps':STEPS.copy(),
            'source_bindings':[{'upload_id':view['upload_id'], 'owner_revision':proposal['base_revision'],
                                'bytes':view['attachment']['size'], 'sha256':view['attachment']['sha256']}]}


def validate_dependencies(proposal):
    deps = proposal['dependencies']
    if not isinstance(deps, dict) or set(deps) != {'schema_version', 'owner', 'owner_revision', 'category_revision', 'upload_id', 'policy_id', 'source_sha256'} or deps['schema_version'] != 2:
        raise ValueError('附件依赖格式无效')
    for name in ('owner_revision', 'category_revision', 'source_sha256'):
        if not isinstance(deps[name], str) or not re.fullmatch('[a-f0-9]{64}', deps[name]):
            raise ValueError('附件依赖摘要无效')
    for name in ('upload_id', 'policy_id'):
        if str(uuid.UUID(deps[name])) != deps[name]:
            raise ValueError('附件依赖身份无效')
    if deps['owner_revision'] != proposal['base_revision'] or proposal['operation'] != 'create' or proposal['execution_plan'] != logical_plan(proposal) or proposal['plan_digest'] != fingerprint(proposal['execution_plan']):
        raise ValueError('附件计划绑定无效')
    plan = proposal['execution_plan']
    if set(plan) != {'handler', 'kind', 'operation', 'target', 'candidate_digest', 'steps', 'source_bindings'} or plan['handler'] != 'attachment@1' or plan['kind'] != 'attachment' or plan['operation'] != 'create' or plan['steps'] != STEPS or plan['target'] != {'id':proposal['target_id'], **proposal['access_target']} or not isinstance(plan['candidate_digest'], str) or not re.fullmatch('[a-f0-9]{64}', plan['candidate_digest']) or not isinstance(plan['source_bindings'], list) or len(plan['source_bindings']) != 1:
        raise ValueError('附件静态处理器或来源计划无效')
    source = plan['source_bindings'][0]
    if set(source) != {'upload_id', 'owner_revision', 'bytes', 'sha256'} or source['upload_id'] != deps['upload_id'] or source['owner_revision'] != deps['owner_revision'] or source['sha256'] != deps['source_sha256'] or type(source['bytes']) is not int or not 0 <= source['bytes'] <= 104857600:
        raise ValueError('附件静态来源身份无效')
    if proposal.get('content_cleaned'):
        return
    view = proposal['normalized_content']
    expected = {'owner_kind', 'owner_id', 'project_id', 'title', 'attachment', 'binary_relative', 'metadata_relative',
                'metadata_before', 'metadata_after', 'body', 'insert_link', 'category_revision', 'unparsed_binary',
                'upload_id', 'policy_id', 'display_name', 'category', 'source'}
    if set(view) != expected or view['owner_kind'] not in {'project', 'issue', 'todo', 'info'} or view['owner_id'] != proposal['target_id'] or type(view['insert_link']) is not bool or view['unparsed_binary'] is not True:
        raise ValueError('附件候选字段无效')
    if view['upload_id'] != deps['upload_id'] or view['policy_id'] != deps['policy_id'] or view['attachment']['sha256'] != deps['source_sha256'] or view['category_revision'] != deps['category_revision']:
        raise ValueError('附件候选依赖无效')
    asset = view['attachment']
    fields = {'name', 'path', 'size', 'mime', 'category', 'id', 'sha256'} | ({'created'} if view['owner_kind'] == 'project' else set())
    if not isinstance(asset, dict) or set(asset) != fields or validate_portable_filename(asset['name']) != asset['name'] or validate_portable_filename(view['display_name']) != view['display_name'] or asset['mime'] != (mimetypes.guess_type(asset['name'])[0] or 'application/octet-stream'):
        raise ValueError('附件元数据不是领域归一化结果')
    if view['owner_kind'] == 'project' and asset['created'] != COMMIT_TIME:
        raise ValueError('项目附件创建时间必须由提交定稿')
    relative_paths(view)
    source_info = view['source']
    if not isinstance(source_info, dict) or set(source_info) != {'filename', 'source', 'sha256', 'bytes'} or source_info['sha256'] != asset['sha256'] or source_info['bytes'] != asset['size']:
        raise ValueError('附件来源摘要不一致')
    validate_portable_filename(source_info['filename'])
    source = source_info['source']
    if source != {'mode':'stream'}:
        if not isinstance(source, dict) or set(source) != {'mode', 'file_id', 'source_revision'} or source['mode'] != 'file' or str(uuid.UUID(source['file_id'])) != source['file_id'] or not re.fullmatch('[a-f0-9]{64}', source['source_revision']):
            raise ValueError('附件来源身份无效')
    if asset['id'] != 'ASSET-' + uuid.UUID(view['upload_id']).hex or asset['category'] != view['category'] or not isinstance(asset['name'], str) or type(asset['size']) is not int or not 0 <= asset['size'] <= 104857600:
        raise ValueError('附件身份无效')
    expected_access = {'project_id':view['project_id']} if view['owner_kind'] == 'project' else {'type':view['owner_kind'], 'project_id':view['project_id']}
    if proposal['access_target'] != expected_access:
        raise ValueError('附件访问范围无效')
    if view['owner_kind'] == 'project':
        if view['insert_link'] or view['body'] != '' or view['metadata_after'] != view['metadata_before'] + [asset]:
            raise ValueError('项目附件索引候选无效')
    else:
        meta = view['metadata_after']
        if meta.get('id') != view['owner_id'] or meta.get('type') != view['owner_kind'] or meta.get('project_id') != view['project_id']:
            raise ValueError('记录附件候选无效')
        previous = view['metadata_before']
        base = proposal['base_content']
        from .assets import AttachmentRepository
        expected_body = AttachmentRepository.append_attachment_link(base['body'], asset) if view['insert_link'] else base['body']
        if base.get('metadata_before') != previous or base.get('metadata_after') != previous or view['body'] != expected_body or meta.get('updated') != COMMIT_TIME:
            raise ValueError('附件正文只能保留原文或由公共助手追加链接')
        # The domain is allowed to update only attachments and updated time.
        if {k:v for k,v in meta.items() if k not in {'attachments', 'updated'}} != {k:v for k,v in previous.items() if k not in {'attachments', 'updated'}}:
            raise ValueError('附件不能修改其他记录元数据')
        items = [json.loads(item) if isinstance(item, str) else item for item in meta['attachments']]
        old = [json.loads(item) if isinstance(item, str) else item for item in previous.get('attachments', [])]
        if items != old + [asset]:
            raise ValueError('记录附件元数据不一致')


def upload_references(store, upload_id):
    store.preflight()
    references = []
    for path in store.proposals.glob('*.json'):
        proposal = store._load(path.stem, expire=False)
        if proposal['kind'] != 'attachment' or not any(source['upload_id'] == upload_id for source in proposal['execution_plan']['source_bindings']):
            continue
        journals = list(store.operations.glob(proposal['proposal_id'] + '-*/manifest.json'))
        if proposal['state'] not in {'cancelled', 'expired'} or journals:
            references.append(proposal)
    if len(references) > 1:
        raise AgentError('recovery_required', '暂存被多个提案引用，保留现场', 503)
    return references



class AttachmentService:
    def __init__(self, service):
        self.service, self.repository, self.security, self.store, self.uploads = service, service.repository, service.security, service.store, service.uploads

    def policy(self, client, kind, key, policy_id=None):
        from .agent_file_handles import SUPPORTED
        if not SUPPORTED:
            raise AgentError('unsupported_platform', '正式附件仅支持已验证的Windows本机NTFS', 503)
        require_scope(client, 'read')
        if kind not in {'project', 'issue', 'todo', 'info'}:
            raise AgentError('invalid_owner', '正式附件仅支持既有记录和项目')
        authorized_owner(self.repository, client, kind, key)
        policies = active_policies(self.repository, self.security, client)
        for policy in policies:
            if policy.get('attachment_write') and policy['owner_kind'] == kind and policy['owner_id'] == key and (policy_id is None or policy['policy_id'] == policy_id):
                return policy
        raise AgentError('forbidden', '需要为具体目标明确共同批准暂存与附件创建权限', 403)

    def target(self, client, kind, key):
        policy = self.policy(client, kind, key)
        owner, _path, before, items = self.repository.attachment_target(kind, key)
        project_id = key if kind == 'project' else owner['project_id']
        project_items = self.repository.attachment_target('project', project_id)[3]
        names, _revision = categories(self.repository._attachment_repository, project_id, project_items + ([] if kind == 'project' else items))
        return {'owner_kind':kind, 'owner_id':key, 'title':owner.get('title', owner.get('name')),
                'revision':content_revision(before or b''), 'attachments':items, 'categories':names,
                'policy_id':policy['policy_id'], 'binary_download':False}

    def normalize(self, client, content, target_id, base_revision, proposal=None):
        if not isinstance(content, dict) or set(content) != FIELDS or content['owner_id'] != target_id or not isinstance(base_revision, str) or not re.fullmatch('[a-f0-9]{64}', base_revision) or type(content['insert_link']) is not bool:
            raise AgentError('invalid_content', '附件提案需完整归属、暂存、名称、分类、链接选择及目标版本')
        for scope in ('read', 'propose', 'commit'):
            require_scope(client, scope)
        value = self.uploads.load(content['upload_id'])
        policy = self.policy(client, content['owner_kind'], target_id, value['policy_id'])
        self.uploads.authorize(client, value)
        if value['state'] != 'ready' or value['removed'] or value['error'] or value['consumption'] is not None:
            raise AgentError('upload_unavailable', '需要完整可用且未消费的ready暂存', 409)
        self.uploads.protected(value)
        references = self.upload_references(value['upload_id'])
        if any(item['proposal_id'] != (proposal or {}).get('proposal_id') for item in references):
            raise AgentError('upload_in_use', '暂存已绑定另一有效提案', 409)
        reserved = []
        for path in self.store.proposals.glob('*.json'):
            old = self.store._load(path.stem, expire=False)
            if old['kind'] == 'attachment' and old['proposal_id'] != (proposal or {}).get('proposal_id') and old['state'] not in {'cancelled', 'expired', 'committed'}:
                reserved.append(old['normalized_content']['binary_relative'])
        try:
            draft = self.repository.prepare_attachment_create(content['owner_kind'], target_id, content['display_name'], value['declared_bytes'], value['declared_sha256'], content['category'], content['insert_link'], base_revision, 'ASSET-' + uuid.UUID(value['upload_id']).hex, reserved=reserved, managed_time=COMMIT_TIME)
        except FileExistsError:
            raise AgentError('revision_conflict', '附件目标已变化，请重新完整预览', 409) from None
        from .agent_file_handles import deny_sensitive
        deny_sensitive(str(draft.binary_path))
        view = {**draft.view, **content, 'policy_id':policy['policy_id'], 'source':{'filename':value['filename'], 'source':value['source'], 'sha256':value['declared_sha256'], 'bytes':value['declared_bytes']}}
        base_body = raw_markdown_body(draft.before) if content['owner_kind'] != 'project' else ''
        base = {'body':base_body, 'metadata_before':view['metadata_before'], 'metadata_after':view['metadata_before']}
        if len(json.dumps([view, base], ensure_ascii=False).encode('utf-8')) > 262144:
            raise AgentError('content_too_large', '附件目标正文与完整元数据预览合计超过256KiB，未截断或创建提案', 413)
        return view, base

    def dependencies(self, client, view, revision):
        owner = authorized_owner(self.repository, client, view['owner_kind'], view['owner_id'])
        return {'schema_version':2, 'owner':owner, 'owner_revision':revision, 'category_revision':view['category_revision'],
                'upload_id':view['upload_id'], 'policy_id':view['policy_id'], 'source_sha256':view['attachment']['sha256']}

    def upload_references(self, upload_id):
        return upload_references(self.store, upload_id)

    def synchronize_binding(self, upload_id):
        references = self.upload_references(upload_id)
        value = self.uploads.load(upload_id)
        if references:
            proposal = references[0]
            expected = {'schema_version':1, 'proposal_id':proposal['proposal_id'], 'version':proposal['version'], 'owner_revision':proposal['base_revision']}
            if value['binding'] is not None and value['binding']['proposal_id'] != proposal['proposal_id']:
                raise AgentError('recovery_required', '暂存绑定镜像不一致', 503)
            value['binding'] = expected
        elif value['consumption'] is None and value['binding'] is not None:
            self.uploads.protected(value)
            return
        self.uploads.write(value)

    def prepare_submission(self, client, proposal, allow_published=False):
        view = proposal['normalized_content']
        policy = self.policy(client, view['owner_kind'], view['owner_id'], view['policy_id'])
        if policy['attachment_write']['minimum_confirmation_mode'] == 'local_web' and proposal['confirmation_mode'] != 'local_web':
            raise AgentError('confirmation_required', '此目标要求本机网页独立批准', 409)
        if authorization_revision(client) != proposal['authorization_revision']:
            raise AgentError('authorization_changed', '授权已变化，请重新整理及完整预览', 409)
        value = self.uploads.load(view['upload_id'])
        self.uploads.authorize(client, value)
        expected_source = {'filename':value['filename'], 'source':value['source'], 'sha256':value['declared_sha256'], 'bytes':value['declared_bytes']}
        if view['source'] != expected_source or view['policy_id'] != value['policy_id'] or view['attachment']['sha256'] != value['declared_sha256'] or view['attachment']['size'] != value['declared_bytes']:
            raise AgentError('source_changed', '附件来源不属于已预览暂存', 409)
        if value['state'] != 'ready' or value['removed'] or value['error'] or value['consumption']:
            raise AgentError('upload_unavailable', '原暂存不可用', 409)
        expected_binding = {'schema_version':1, 'proposal_id':proposal['proposal_id'], 'version':proposal['version'], 'owner_revision':proposal['base_revision']}
        if value['binding'] != expected_binding:
            raise AgentError('recovery_required', '暂存绑定需要恢复', 503)
        owner, path, before, items = self.repository.attachment_target(view['owner_kind'], view['owner_id'])
        if content_revision(before or b'') != proposal['base_revision']:
            raise AgentError('revision_conflict', '目标正文或索引已变化', 409)
        project_items = self.repository.attachment_target('project', view['project_id'])[3]
        _names, category_revision = categories(self.repository._attachment_repository, view['project_id'], project_items + ([] if view['owner_kind'] == 'project' else items))
        if view['category'] and view['category'] not in _names or category_revision != view['category_revision'] or self.dependencies(client, view, proposal['base_revision']) != proposal['dependencies']:
            raise AgentError('dependency_changed', '目标或分类依赖已变化', 409)
        target = self.repository.root / view['binary_relative']
        if target.exists() and not allow_published:
            raise AgentError('attachment_name_conflict', '预览中的最终名称已被占用，请修订后重新预览', 409)
        after = serialized(view)
        record_write = None if view['owner_kind'] == 'project' else PreparedMarkdownWrite(path, view['owner_id'], after.decode('utf-8'), before)
        return PreparedAttachment(target, path, before, after, view, record_write)


    def get_proposal(self, client, proposal_id, guard=None):
        from .agent_attachment_execution import AttachmentExecution
        execution = AttachmentExecution(self.service)
        require_scope(client, 'read')
        execution.recover(proposal_id, guard)
        def current():
            proposal = self.store.owned(client, proposal_id)
            self.service._enforce_confirmation_policy(client, proposal)
            result = self.store.public(proposal)
            if proposal['state'] == 'committed':
                view = proposal.get('normalized_content', proposal['receipt'])
                try:
                    _owner, _path, before, items = self.repository.attachment_target(view['owner_kind'], view['owner_id'])
                    values = [json.loads(item) if isinstance(item, str) else item for item in items]
                    revision = content_revision(before or b'')
                    result['current_item'] = {'exists':any(item.get('id') == proposal['receipt']['item_id'] for item in values),
                                              'revision':revision, 'changed_since_commit':revision != proposal['receipt']['revision']}
                except (FileNotFoundError, ValueError):
                    result['current_item'] = {'exists':False}
            return result
        return execution.short(current, guard)
