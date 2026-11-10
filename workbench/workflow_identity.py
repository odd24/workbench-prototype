"""Stable template incarnations and one-use name generations."""

import uuid
from dataclasses import dataclass

from .project_identity import load_unique_json
from .workflow_changes import _identifier, _label, validate_catalogue
from .workflow_prepared import WorkflowFile, encoded, read_raw
from .write_coordinator import RevisionConflict


FENCE = 'config/workflow-identities-fence.json'
LEDGER = 'config/workflow-identities.json'


def _identity(epoch, key):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f'workbench/workflow/v1/{epoch}/{key}'))


def _uuid(value):
    return isinstance(value, str) and str(uuid.UUID(value)) == value


@dataclass(frozen=True)
class WorkflowIdentity:
    epoch: str | None
    fence: bytes | None
    ledger: bytes | None
    active: dict
    names: dict
    generations: dict
    retired: tuple

    def plan(self, candidate, epoch):
        indexed = validate_catalogue(candidate)
        if set(indexed) & set(self.retired):
            raise ValueError('已退役的工作流 ID 不可重用')
        names = {key:item['name'] for key,item in indexed.items()}
        if names == self.names and self.epoch:
            return ()
        epoch = self.epoch or epoch
        if not _uuid(epoch):
            raise ValueError('工作流身份世代无效')
        active = {key:self.active.get(key, _identity(epoch, key)) for key in names}
        retired = sorted(set(self.retired) | (self.active.keys() - names.keys()))
        old, new = {name:key for key,name in self.names.items()}, {name:key for key,name in names.items()}
        generations = self.generations.copy()
        for name in old.keys() | new.keys():
            if old.get(name) != new.get(name):
                generations[name] = generations.get(name, 0) + 1
        fence = self.fence or encoded({'schema_version':1, 'epoch':epoch})
        ledger = encoded({'schema_version':1, 'epoch':epoch, 'active':active, 'names':names,
                          'generations':generations, 'retired':retired})
        result = [WorkflowFile(LEDGER, self.ledger, ledger)]
        if self.fence is None:
            result.insert(0, WorkflowFile(FENCE, None, fence))
        if len(ledger) > 1048576:
            raise ValueError('工作流身份记录超出完整核验上限')
        return tuple(result)


def load_identities(root, catalogue):
    names = {key:row['name'] for key,row in validate_catalogue(catalogue).items()}
    fence, ledger = read_raw(root, FENCE), read_raw(root, LEDGER)
    if fence is None and ledger is None:
        return WorkflowIdentity(None, None, None, {key:_identity('legacy', key) for key in names},
                                names, dict.fromkeys(names.values(), 1), ())
    if fence is None or ledger is None:
        raise RevisionConflict('工作流身份配对证据不完整')
    mark, value = load_unique_json(fence), load_unique_json(ledger)
    if (not isinstance(mark, dict) or set(mark) != {'schema_version', 'epoch'} or type(mark['schema_version']) is not int
            or mark['schema_version'] != 1 or not _uuid(mark['epoch']) or not isinstance(value, dict)
            or set(value) != {'schema_version','epoch','active','names','generations','retired'}
            or type(value['schema_version']) is not int or value['schema_version'] != 1 or value['epoch'] != mark['epoch']):
        raise ValueError('工作流身份格式不受支持')
    active, saved, generations, retired = (value[key] for key in ('active','names','generations','retired'))
    if (not all(isinstance(item, dict) for item in (active, saved, generations)) or not isinstance(retired, list)
            or saved.keys() != active.keys() or any(not isinstance(name, str) for name in saved.values())
            or not set(saved.values()) <= generations.keys()
            or any(_identifier(key) != key or not _uuid(identity) for key,identity in active.items())
            or len(set(active.values())) != len(active)
            or any(_label(name) != name or type(version) is not int or version < 1 for name,version in generations.items())
            or any(_identifier(key) != key for key in retired) or len(set(retired)) != len(retired)
            or set(active) & set(retired)):
        raise ValueError('工作流身份、名称代次或墓碑无效')
    if names != saved:
        raise RevisionConflict('工作流目录与原身份记录不一致')
    return WorkflowIdentity(mark['epoch'], fence, ledger, active, names, generations, tuple(retired))
