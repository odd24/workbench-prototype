"""Pure project preparation; publication belongs to the approved execution."""

import json
import re
from dataclasses import dataclass

from .configuration import ConfigurationRepository
from .markdown_io import load_markdown_text
from .project_identity import controlled, disk_occupied, identity_key, load_unique_json, next_project_id, read_bounded
from .projects import PROJECT_DIRECTORIES, project_readme
from .write_coordinator import content_revision


PROJECT_FIELDS = ('name', 'description', 'status', 'color', 'workflow_template')
PROJECT_STATUS = {'active', 'paused', 'archived'}
SORT_MODES = {'custom', 'updated', 'name', 'created', 'record_count'}
TIME_PLACEHOLDER = '批准受理时由服务端填写'


def normalize_project(content):
    if not isinstance(content, dict) or set(content) - set(PROJECT_FIELDS) or not isinstance(content.get('name'), str):
        raise ValueError('项目候选只接受名称、描述、状态、颜色和现有工作流模板')
    result = {'name':content['name'], 'description':'', 'status':'active', 'color':'#4d78e8', 'workflow_template':'standard', **content}
    if any(not isinstance(value, str) for value in result.values()):
        raise ValueError('项目字段必须为文本')
    if re.search(r'[\x00-\x1f\x7f\u0085\u2028\u2029]', result['name']):
        raise ValueError('项目名称必须为单行文本')
    result['name'] = result['name'].strip()
    result['description'] = result['description'].strip()
    if not result['name'] or len(result['name']) > 160 or len(result['description'].encode('utf-8')) > 65536 or '\x00' in result['description']:
        raise ValueError('项目名称或描述不符合长度与字符要求')
    if result['status'] not in PROJECT_STATUS or not re.fullmatch(r'#[0-9a-fA-F]{6}', result['color']):
        raise ValueError('项目状态或颜色无效')
    if not result['workflow_template'] or len(result['workflow_template']) > 160:
        raise ValueError('工作流模板标识无效')
    # Reject legacy scalar coercion rather than previewing metadata different
    # from what the existing repository will read after publication.
    meta, preview = project_readme('preview', result, TIME_PLACEHOLDER)
    if load_markdown_text(preview)[0] != meta:
        raise ValueError('项目字段无法用现有格式无损保存')
    return result


def project_collection(root):
    projects = []
    keys = set()
    for path in (root / 'projects').glob('*/README.md'):
        raw = read_bounded(controlled(root, path))
        meta, _ = load_markdown_text(raw.decode('utf-8'))
        if meta.get('type') != 'project':
            continue
        key = identity_key(meta['id'])
        if meta['id'] != path.parent.name or key in keys or not isinstance(meta.get('created', ''), str):
            raise ValueError('正式项目集合身份或排序证据不一致')
        keys.add(key)
        projects.append({'id':meta['id'], 'created':meta.get('created', ''), 'revision':content_revision(raw)})
    return projects


@dataclass(frozen=True)
class PreparedProjectCreate:
    project_id: str
    fields: dict
    workflow: dict
    workflow_digest: str
    projects: list
    sort_before: bytes
    sort_after: bytes
    sort_mode: str
    visible_before: list
    visible_after: list

    @property
    def relative_path(self):
        return f'projects/{self.project_id}'

    @property
    def directories(self):
        return PROJECT_DIRECTORIES

    def readme(self, stamp=TIME_PLACEHOLDER):
        return project_readme(self.project_id, self.fields, stamp)


def prepare_project(repository, content, *, occupied=(), project_id=None):
    root = repository.root
    fields = normalize_project(content)
    used = disk_occupied(root) | set(occupied)
    if project_id is None:
        project_id = next_project_id(fields['name'], used)
    elif identity_key(project_id) in used:
        raise FileExistsError('固定项目身份已占用，请重新建立提案并预览')
    controlled(root, root / 'projects' / project_id)
    template_raw = read_bounded(controlled(root, root / 'config/workflow-templates.json'))
    templates = load_unique_json(template_raw)
    if not isinstance(templates, list) or any(not isinstance(t, dict) or not isinstance(t.get('id'), str) for t in templates) or len({t['id'] for t in templates}) != len(templates):
        raise ValueError('工作流模板证据损坏')
    selected = next((t for t in templates if t['id'] == fields['workflow_template']), None)
    if not selected or not isinstance(selected.get('name'), str) or not selected['name']:
        raise ValueError('需要选用现有有效工作流模板')
    repository._configuration_repository._validate_statuses(selected.get('statuses'))
    sort_raw = read_bounded(controlled(root, root / 'config/project-sort.json'))
    sorting = load_unique_json(sort_raw)
    if not isinstance(sorting, dict) or set(sorting) != {'mode', 'order'} or sorting['mode'] not in SORT_MODES or not isinstance(sorting['order'], list) or any(not isinstance(key, str) for key in sorting['order']):
        raise ValueError('项目排序证据未知或损坏')
    projects = project_collection(root)
    before, after = [], []
    sort_after = sort_raw
    if sorting['mode'] == 'custom':
        positions = {key:index for index, key in enumerate(sorting['order'])}
        before = [item['id'] for item in sorted(projects, key=lambda item: (positions.get(item['id'], 999999), item['created']))]
        after = [*before, project_id]
        value = ConfigurationRepository.canonical_project_sort({'mode':'custom', 'order':after}, [*projects, {'id':project_id}])
        sort_after = json.dumps(value, ensure_ascii=False, indent=2).encode('utf-8')
    return PreparedProjectCreate(project_id, fields, selected, content_revision(template_raw), projects,
                                 sort_raw, sort_after, sorting['mode'], before, after)
