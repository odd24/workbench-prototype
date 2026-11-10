"""Native no-replacement publication for an exact, privately staged project."""

from .agent_file_handles import LocalFileHandle, lexical_path
from .agent_security import AgentError
from .persistence import atomic_write_bytes
from .project_identity import controlled, read_bounded
from .projects import PROJECT_DIRECTORIES


class _ProjectDirectoryHandle(LocalFileHandle):
    """Internal directory leaf only; Agent file authorization still rejects it."""

    def _open_leaf(self):
        return self._open(self.path, directory=True, directory_delete=self.delete_allowed)

    def identity(self):
        return self._identity(directory=True)


def physical_identity(handle):
    value = handle.identity()
    return {name:value[name] for name in ('volume', 'index', 'created')}


def _assert_tree(root, folder, readme):
    expected = set(PROJECT_DIRECTORIES) | {'assets', 'README.md'}
    observed = set()
    for path in folder.rglob('*'):
        relative = path.relative_to(folder).as_posix()
        if relative not in expected or relative in observed:
            raise ValueError('项目目录包含未知成员')
        checked = controlled(root, path)
        if relative == 'README.md':
            if not checked.is_file() or read_bounded(checked) != readme:
                raise ValueError('项目 README 与批准计划不一致')
        elif not checked.is_dir():
            raise ValueError('项目空目录结构与批准计划不一致')
        observed.add(relative)
    if observed != expected:
        raise ValueError('项目目录未完整组装')


def probe_publication(root, stage, destination):
    # Validate complete leaf names up front, not after creating private stage.
    for path in (stage, destination, stage / 'README.md', destination / 'README.md',
                 *(stage / child for child in PROJECT_DIRECTORIES), *(destination / child for child in PROJECT_DIRECTORIES)):
        lexical_path(str(controlled(root, path)))
    with _ProjectDirectoryHandle(str(stage.parent)) as source_parent, _ProjectDirectoryHandle(str(destination.parent)) as destination_parent:
        if physical_identity(source_parent)['volume'] != physical_identity(destination_parent)['volume']:
            raise AgentError('unsupported_volume', '项目暂存与正式目录必须位于同一固定NTFS卷', 409)


def workspace_supported(root):
    try:
        agent = controlled(root, root / '.agent')
        projects = controlled(root, root / 'projects')
        with _ProjectDirectoryHandle(str(agent)) as source, _ProjectDirectoryHandle(str(projects)) as destination:
            return physical_identity(source)['volume'] == physical_identity(destination)['volume']
    except (AgentError, ValueError, OSError):
        return False


def stage_project(root, stage, readme):
    stage = controlled(root, stage)
    stage.mkdir(exist_ok=False)
    for directory in PROJECT_DIRECTORIES:
        (stage / directory).mkdir(parents=True, exist_ok=False)
    atomic_write_bytes(stage / 'README.md', readme)
    return verify_project(root, stage, readme)


def verify_project(root, folder, readme, identity=None):
    folder = controlled(root, folder)
    with _ProjectDirectoryHandle(str(folder)) as handle:
        actual = physical_identity(handle)
        if identity is not None and actual != identity:
            raise ValueError('项目目录物理身份与批准操作不一致')
        _assert_tree(root, folder, readme)
        if actual != physical_identity(handle):
            raise ValueError('项目目录核验期间身份变化')
        return actual


def publish_project(root, stage, destination, readme, identity, permit):
    stage, destination = controlled(root, stage), controlled(root, destination)
    with _ProjectDirectoryHandle(str(stage), read=True, delete=True) as handle:
        if physical_identity(handle) != identity:
            raise ValueError('项目暂存身份已改变')
        _assert_tree(root, stage, readme)
        permit()
        _assert_tree(root, stage, readme)
        if physical_identity(handle) != identity:
            raise ValueError('项目暂存身份已改变')
        try:
            handle.rename_verified(destination)
        except AgentError as error:
            if error.code == 'attachment_publish_conflict':
                raise AgentError('project_publish_conflict', '项目目标已占用或路径变化，未覆盖任何目录', 409) from None
            raise
    verify_project(root, destination, readme, identity)
