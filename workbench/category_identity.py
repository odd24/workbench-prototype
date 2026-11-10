"""Category incarnations and name generations, without a second catalogue."""

import json
import uuid
from dataclasses import dataclass

from .category_changes import FAMILIES, PROJECT_ASSETS, category_name
from .project_identity import controlled, load_unique_json, read_bounded, valid_new_id
from .write_coordinator import RevisionConflict


IDENTITY_PATH = 'config/category-identities.json'
FENCE_PATH = 'config/category-identities-fence.json'


def namespace_key(family, project_id):
    if family not in FAMILIES or family == PROJECT_ASSETS and project_id is None or family != PROJECT_ASSETS and project_id is not None:
        raise ValueError('分类归属身份无效')
    if project_id is not None:
        valid_new_id(project_id)
    return json.dumps([family, project_id], ensure_ascii=False, separators=(',', ':'))


def _uuid(value):
    return isinstance(value, str) and str(uuid.UUID(value)) == value


def _encoding(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2).encode('utf-8')


def _identity(key, name, epoch, generation):
    identity = json.dumps(['workbench/category/v1', epoch, key, name, generation], ensure_ascii=False)
    return str(uuid.uuid5(uuid.NAMESPACE_URL, identity))


def _validate_namespace(key, value):
    family, project_id = json.loads(key)
    if key != namespace_key(family, project_id) or not isinstance(value, dict) or set(value) != {'active', 'generations', 'retired'}:
        raise ValueError('分类身份作用域格式无效')
    active, generations, retired = value['active'], value['generations'], value['retired']
    if not isinstance(active, dict) or not isinstance(generations, dict) or not isinstance(retired, list) or not active.keys() <= generations.keys():
        raise ValueError('分类代次或墓碑无效')
    if any(category_name(family, name) != name or type(generation) is not int or generation < 1 for name, generation in generations.items()):
        raise ValueError('分类名称代次无效')
    ids = [*active.values(), *retired]
    if any(not _uuid(identity) for identity in ids) or len(set(ids)) != len(ids):
        raise ValueError('分类身份重复或损坏')


@dataclass(frozen=True)
class CategoryIdentities:
    fence_before: bytes | None
    ledger_before: bytes | None
    epoch: str | None
    namespaces: dict

    def scope(self, key, names):
        if key not in self.namespaces:
            # Existing identities remain stable while other namespaces first
            # acquire a sidecar. Workspace credentials supply the outer scope.
            return {'active':{name:_identity(key, name, 'legacy', 1) for name in names},
                    'generations':dict.fromkeys(names, 1), 'retired':[]}
        value = self.namespaces[key]
        if set(names) != set(value['active']):
            raise RevisionConflict('分类目录与原身份代次不一致，请核查外部修改')
        return value

    def plan(self, change, project_id, bootstrap_epoch):
        key = namespace_key(change.family, project_id)
        scope = self.scope(key, change.before)
        active, generations, retired = scope['active'].copy(), scope['generations'].copy(), scope['retired'].copy()
        epoch = self.epoch or bootstrap_epoch
        if not _uuid(epoch):
            raise ValueError('分类身份版本标记无效')
        name, destination = change.name, change.destination
        if change.operation in {'rename', 'delete'}:
            old_id = active.pop(name)
            generations[name] += 1
            if change.operation == 'rename':
                generations[destination] = generations.get(destination, 0) + 1
                active[destination] = old_id
            else:
                retired.append(old_id)
        for added in change.after:
            if added not in active:
                generation = generations.get(added, 0) + 1
                generations[added] = generation
                active[added] = _identity(key, added, epoch, generation)
        after = {'active':active, 'generations':generations, 'retired':retired}
        if set(active) != set(change.after):
            raise ValueError('分类候选和身份计划集合不一致')
        return after, *self._encode_scope(key, after, epoch)

    def replace(self, family, project_id, before, after, bootstrap_epoch):
        key = namespace_key(family, project_id)
        scope = self.scope(key, before)
        active, generations, retired = scope['active'].copy(), scope['generations'].copy(), scope['retired'].copy()
        epoch = self.epoch or bootstrap_epoch
        for name in sorted(set(before) - set(after)):
            retired.append(active.pop(name))
            generations[name] += 1
        for name in sorted(set(after) - set(before)):
            generation = generations.get(name, 0) + 1
            generations[name] = generation
            active[name] = _identity(key, name, epoch, generation)
        return self._encode_scope(key, {'active':active, 'generations':generations, 'retired':retired}, epoch)

    def _encode_scope(self, key, after, epoch):
        _validate_namespace(key, after)
        fence = self.fence_before or _encoding({'schema_version':1, 'epoch':epoch})
        ledger = _encoding({'schema_version':1, 'epoch':epoch, 'namespaces':{**self.namespaces, key:after}})
        if len(ledger) > 1048576:
            raise ValueError('分类身份账本超过完整核验上限')
        return fence, ledger


def load_category_identities(root):
    fence_path, ledger_path = (controlled(root, root / path) for path in (FENCE_PATH, IDENTITY_PATH))
    fence_raw = read_bounded(fence_path) if fence_path.exists() else None
    ledger_raw = read_bounded(ledger_path) if ledger_path.exists() else None
    if fence_raw is None and ledger_raw is None:
        return CategoryIdentities(None, None, None, {})
    if fence_raw is None or ledger_raw is None:
        raise ValueError('分类身份门槛或账本缺失，需核查原操作')
    fence, ledger = load_unique_json(fence_raw), load_unique_json(ledger_raw)
    if not isinstance(fence, dict) or set(fence) != {'schema_version', 'epoch'} or type(fence['schema_version']) is not int or fence['schema_version'] != 1 or not _uuid(fence['epoch']):
        raise ValueError('分类身份门槛格式未知')
    if not isinstance(ledger, dict) or set(ledger) != {'schema_version', 'epoch', 'namespaces'} or type(ledger['schema_version']) is not int or ledger['schema_version'] != 1 or ledger['epoch'] != fence['epoch'] or not isinstance(ledger['namespaces'], dict):
        raise ValueError('分类身份账本格式或代次不一致')
    for key, value in ledger['namespaces'].items():
        _validate_namespace(key, value)
    return CategoryIdentities(fence_raw, ledger_raw, fence['epoch'], ledger['namespaces'])
