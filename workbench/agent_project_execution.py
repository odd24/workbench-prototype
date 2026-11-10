"""Static project-create plans and phases for the single ProposalStore."""

import re
from datetime import datetime
from urllib.parse import urlencode

from .agent_execution import fingerprint
from .agent_project_authorization import can_create_project
from .agent_security import allows
from .persistence import atomic_write_bytes, atomic_write_json
from .project_directory import probe_publication, publish_project, stage_project, verify_project
from .project_identity import controlled, valid_new_id, load_unique_json, read_bounded
from .project_prepared import SORT_MODES, normalize_project
from .projects import PROJECT_DIRECTORIES, project_readme
from .write_coordinator import content_revision


STEPS = ['project_stage', 'project_publish', 'project_sort', 'receipt']
PHASES = (
    ['pending', 'pending', 'pending', 'pending'],
    ['applying', 'pending', 'pending', 'pending'],
    ['completed', 'pending', 'pending', 'pending'],
    ['completed', 'applying', 'pending', 'pending'],
    ['completed', 'completed', 'applying', 'pending'],
    ['completed', 'completed', 'completed', 'applying'],
    ['completed', 'completed', 'completed', 'completed'],
)


def proposal_allows(client, proposal, *, writing=False):
    if proposal['kind'] != 'project':
        return allows(client, proposal['access_target'])
    if not writing and proposal['state'] == 'committed':
        return client.get('enabled') is True and 'read' in client['scopes']
    return can_create_project(client)


def web_path(project_id):
    return '/?' + urlencode({'item':'project', 'itemId':project_id})


def logical_plan(proposal):
    return {'handler':'project_create@1', 'kind':'project', 'operation':'create',
            'target':proposal['access_target'], 'steps':STEPS.copy(), 'source_bindings':[],
            'candidate_digest':fingerprint(proposal['normalized_content']) if 'normalized_content' in proposal else proposal['execution_plan']['candidate_digest'],
            'sort_plan_digest':proposal['dependencies']['sort_plan_digest']}


def _hash(value):
    return isinstance(value, str) and re.fullmatch(r'[0-9a-f]{64}', value)


def validate_context(proposal):
    key = proposal['target_id']
    if proposal['operation'] != 'create' or proposal['confirmation_mode'] != 'local_web' or proposal['base_revision'] is not None or valid_new_id(key) != key.casefold():
        raise ValueError('项目创建身份或确认方式无效')
    if proposal['access_target'] != {'type':'project', 'id':key}:
        raise ValueError('项目固定目标不一致')
    dependencies = proposal['dependencies']
    if set(dependencies) != {'schema_version', 'workflow_digest', 'collection_digest', 'sort_plan_digest', 'sort_before_digest', 'sort_after_digest'} or type(dependencies['schema_version']) is not int or dependencies['schema_version'] != 1 or any(not _hash(value) for name, value in dependencies.items() if name != 'schema_version'):
        raise ValueError('项目创建依赖不一致')
    if not proposal.get('content_cleaned'):
        content = proposal['normalized_content']
        details = proposal['project_sort_details']
        if set(details) != {'mode', 'raw_before', 'raw_after', 'visible_before', 'visible_after'} or details['mode'] not in SORT_MODES or fingerprint(details) != dependencies['sort_plan_digest']:
            raise ValueError('项目排序计划不一致')
        for side in ('before','after'):
            if content_revision(details['raw_' + side].encode('utf-8')) != dependencies['sort_' + side + '_digest']:
                raise ValueError('项目排序原字节摘要不一致')
        if details['mode'] == 'custom':
            if details['visible_after'] != [*details['visible_before'], key] or key in details['visible_before'] or load_unique_json(details['raw_after'].encode()) != {'mode':'custom','order':details['visible_after']}:
                raise ValueError('项目自定义排序变化不属于批准项目')
        elif details['visible_before'] or details['visible_after'] or details['raw_before'] != details['raw_after']:
            raise ValueError('项目自动排序不允许改写配置')
        fields = normalize_project(content['fields'])
        from .project_prepared import TIME_PLACEHOLDER
        meta, raw = project_readme(key, fields, TIME_PLACEHOLDER)
        if fields != content['fields'] or content['metadata'] != meta or content['readme'] != raw or content['directories'] != list(PROJECT_DIRECTORIES) or content['project_id'] != key or content['title'] != fields['name'] or content['sorting'] != sort_summary(details['mode']):
            raise ValueError('项目候选与固定目录、说明或排序不一致')
    if proposal['execution_plan'] != logical_plan(proposal) or proposal['plan_digest'] != fingerprint(proposal['execution_plan']):
        raise ValueError('项目逻辑执行计划不一致')


def sort_summary(mode):
    return {'mode':mode, 'position':'末尾' if mode == 'custom' else '按原规则计算',
            'rule':'保留所有现存项目相对顺序，补齐未列项目并清理失效/重复编号，新项目置末' if mode == 'custom' else '排序配置原字节保留'}


def concrete_plan(manifest, proposal):
    return {'handler':'project_create@1', 'proposal_plan_digest':proposal['plan_digest'], 'steps':STEPS.copy(),
            **{key:manifest[key] for key in ('item_id','relative_path','readme_digest','accepted_at')},
            'sort_plan_digest':proposal['dependencies']['sort_plan_digest']}


def paths(store, manifest):
    root = store.repository.root
    directory = store.operations / manifest['operation_id']
    return root, directory, controlled(root, directory / 'project-stage'), controlled(root, root / manifest['relative_path'])


def validate_execution(store, manifest, proposal, snapshots=False):
    validate_context(proposal)
    if type(manifest.get('execution_schema_version')) is not int or manifest['execution_schema_version'] != 5 or manifest['kind'] != 'project' or manifest['operation'] != 'create' or manifest['client_id'] != proposal['client_id'] or manifest['item_id'] != proposal['target_id'] or manifest['relative_path'] != f"projects/{proposal['target_id']}":
        raise ValueError('项目执行身份不一致')
    for key in ('authorization_revision','dependencies','preview_digest','confirmation_mode','digest_algorithm','access_target','approval'):
        if manifest.get(key) != proposal.get(key):
            raise ValueError('项目执行依赖或批准不一致')
    if not manifest['approval'] or manifest['confirmation'] != {'mode':'local_web'} or not _hash(manifest['readme_digest']) or manifest['accepted_at'] != manifest['approval']['approved_at']:
        raise ValueError('项目创建必须绑定原网页批准时间')
    datetime.fromisoformat(manifest['accepted_at'])
    if manifest['execution_plan'] != concrete_plan(manifest, proposal) or manifest['execution_plan_digest'] != fingerprint(manifest['execution_plan']):
        raise ValueError('项目执行计划摘要不一致')
    phase = PHASES.index(manifest['step_states'])
    if (manifest['state'] == 'prepared' and phase != 0 or manifest['state'] == 'committed' and phase != 6 or
            manifest['state'] in {'applying','recovery_required'} and not 1 <= phase <= 5 or
            manifest['state'] == 'abandoned' and manifest.get('manual_review_required') is not True):
        raise ValueError('项目执行状态无效')
    physical = manifest.get('stage_identity')
    if phase < 2 and physical is not None or phase >= 2 and (not isinstance(physical, dict) or set(physical) != {'volume','index','created'} or any(type(value) is not int or value < 0 for value in physical.values())):
        raise ValueError('项目目录物理身份证据不一致')
    if phase >= 2 and manifest.get('stage_evidence') != fingerprint([manifest['execution_plan_digest'], physical]):
        raise ValueError('项目暂存身份证据摘要不一致')
    receipt = manifest['receipt']
    expected = {'proposal_id':proposal['proposal_id'], 'version':proposal['version'], 'kind':'project',
                'item_id':proposal['target_id'], 'project_id':proposal['target_id'], 'web_path':web_path(proposal['target_id']),
                'revision':manifest['readme_digest'], 'committed_at':manifest['accepted_at'], 'plan_digest':proposal['plan_digest'],
                'execution_plan_digest':manifest['execution_plan_digest'], 'approval':manifest['approval']}
    if set(receipt) != set(expected) | {'title'} or any(receipt[k] != value for k,value in expected.items()) or not isinstance(receipt['title'], str):
        raise ValueError('原项目回执与操作不一致')
    if not proposal.get('content_cleaned'):
        if proposal['normalized_content']['title'] != receipt['title']:
            raise ValueError('项目标题与原回执不一致')
        if store is not None:
            from .agent_proposals import digest
            if digest(store.preview_payload(proposal)) != manifest['preview_digest']:
                raise ValueError('项目原预览摘要不一致')
        _, raw = project_readme(proposal['target_id'], proposal['normalized_content']['fields'], manifest['accepted_at'])
        if content_revision(raw.encode('utf-8')) != manifest['readme_digest']:
            raise ValueError('项目 README 摘要不一致')
        if snapshots:
            root, directory, _, _ = paths(store, manifest)
            if read_bounded(controlled(root, directory / 'after.md')) != raw.encode('utf-8'):
                raise ValueError('项目 README 快照与原批准不一致')
            for side in ('before','after'):
                if read_bounded(controlled(root, directory / f'sort-{side}.json')) != proposal['project_sort_details']['raw_' + side].encode('utf-8'):
                    raise ValueError('项目排序快照与原批准不一致')


def apply_steps(store, manifest, proposal):
    root, directory, stage, target = paths(store, manifest)
    path = directory / 'manifest.json'
    readme = read_bounded(controlled(root, directory / 'after.md'))
    phase = PHASES.index(manifest['step_states'])

    def checkpoint(next_phase, label):
        manifest.update(state='applying', step_states=PHASES[next_phase].copy())
        atomic_write_json(path, manifest)
        store.checkpoint(label)

    if phase < 3:
        if target.exists() or phase == 1:
            raise ValueError('项目暂存或正式目标证据不明，保留现场')
        store._current_authorization(proposal)
        probe_publication(root, stage, target)
        if phase == 0:
            if stage.exists():
                raise ValueError('暂存目录已被占用，不能接管')
            checkpoint(1, 'project_stage_applying')
            physical = stage_project(root, stage, readme)
            store.checkpoint('project_staged')
            manifest.update(stage_identity=physical, stage_evidence=fingerprint([manifest['execution_plan_digest'], physical]))
            checkpoint(2, 'project_stage_logged')
        checkpoint(3, 'project_publish_applying')
        publish_project(root, stage, target, readme, manifest['stage_identity'], lambda:store._current_authorization(proposal))
        store.checkpoint('project_published')
    if stage.exists() or not target.exists():
        raise ValueError('没有已发布原项目的唯一证据，禁止重新发布')
    verify_project(root, target, readme, manifest['stage_identity'])
    if phase < 4:
        checkpoint(4, 'project_sort_applying')
    sort = controlled(root, root / 'config/project-sort.json')
    before = read_bounded(controlled(root, directory / 'sort-before.json'))
    after = read_bounded(controlled(root, directory / 'sort-after.json'))
    current = read_bounded(sort)
    if current not in (before, after):
        raise ValueError('项目排序出现第三方版本，保留已发布项目及排序')
    if current != after:
        if phase >= 5:
            raise ValueError('已完成项目排序后来发生变化，不重写')
        atomic_write_bytes(sort, after)
    store.checkpoint('project_sort_written')
    checkpoint(5, 'project_sort_logged')


def recovery_evidence(store, manifest, proposal):
    validate_execution(store, manifest, proposal, snapshots=True)
    root, directory, stage, target = paths(store, manifest)
    readme = read_bounded(controlled(root, directory / 'after.md'))
    current = content_revision(read_bounded(controlled(root, root / 'config/project-sort.json')))
    deps = proposal['dependencies']
    sort_state = 'unchanged' if deps['sort_before_digest'] == deps['sort_after_digest'] == current else (
        'after' if current == deps['sort_after_digest'] else 'before' if current == deps['sort_before_digest'] else 'foreign')
    state = 'absent' if not target.exists() else 'unverified'
    if state == 'unverified' and manifest.get('stage_identity') and not stage.exists():
        try:
            verify_project(root, target, readme, manifest['stage_identity'])
            state = 'published_original'
        except (ValueError, OSError):
            pass
    return {'operation_id':manifest['operation_id'], 'kind':'project', 'relative_path':manifest['relative_path'],
            'step_states':manifest['step_states'], 'project_state':state, 'sorting_state':sort_state,
            'stage_exists':stage.exists(), 'sorting_revision':current}
