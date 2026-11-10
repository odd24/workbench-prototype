"""Pure category membership and order planning shared by write entry points."""

from dataclasses import dataclass

from .assets import AttachmentRepository
from .security import validate_category_name


FAMILIES = {'document_category', 'concept_map_category', 'project_attachment_category'}
OPERATIONS = {'create', 'rename', 'delete', 'reorder'}
DEFAULT_NAME = '未分类'
PROJECT_ASSETS = 'project_attachment_category'


def category_name(family, value, *, destination=False):
    if family not in FAMILIES or not isinstance(value, str):
        raise ValueError('分类体系或名称无效')
    name = (AttachmentRepository._asset_category(value, allow_empty=True) if family == PROJECT_ASSETS
            else validate_category_name(value, default=''))
    if not name or name != value or name == '*' or destination and name == DEFAULT_NAME:
        raise ValueError('请选择原样有效的具体分类名称')
    return name


@dataclass(frozen=True)
class CategoryChange:
    family: str
    operation: str
    name: str
    destination: str | None
    before: tuple[str, ...]
    after: tuple[str, ...]

    def member_category(self, category):
        if self.operation in {'rename', 'delete'} and category == self.name:
            return self.destination
        return category


def plan_categories(family, operation, names, name, *, new_name=None, anchor=None, position=None):
    if family not in FAMILIES or operation not in OPERATIONS:
        raise ValueError('分类体系或操作不受支持')
    before = tuple(names)
    if len(before) != len(set(before)) or any(category_name(family, value) != value for value in before):
        raise ValueError('原分类集合存在重复或无法完整核验的名称')
    category_name(family, name, destination=operation == 'create')
    system_default = '' if family == PROJECT_ASSETS else DEFAULT_NAME
    if operation == 'create':
        if name in before or any(value is not None for value in (new_name, anchor, position)):
            raise ValueError('新分类必须使用未占用名称')
        after = [*before, name]
        destination = name
    else:
        if name not in before:
            raise FileNotFoundError('目标分类不存在')
        if name == system_default:
            raise ValueError('系统默认分类不能改名、删除或移动')
        if operation == 'rename':
            destination = category_name(family, new_name, destination=True)
            if destination in before or anchor is not None or position is not None:
                raise ValueError('改名目标必须使用未占用名称')
            after = [destination if value == name else value for value in before]
        elif operation == 'delete':
            if any(value is not None for value in (new_name, anchor, position)):
                raise ValueError('删除只能迁入系统默认分类')
            destination = system_default
            after = [value for value in before if value != name]
            if system_default and system_default not in after:
                after.append(system_default)
        else:
            category_name(family, anchor)
            if new_name is not None or anchor == name or anchor not in before or position not in {'before', 'after'} or anchor == system_default and position == 'after':
                raise ValueError('重排需要其它现有分类锚点及有效相对位置')
            destination = None
            after = [value for value in before if value != name]
            after.insert(after.index(anchor) + (position == 'after'), name)
    if system_default and system_default in after:
        after = [value for value in after if value != system_default] + [system_default]
    return CategoryChange(family, operation, name, destination, before, tuple(after))
