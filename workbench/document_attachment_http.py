"""Ordinary document upload transport; stream IO never holds repository locks."""

import re
import socket
from urllib.parse import parse_qs, unquote, urlparse

from .agent_security import AgentError
from .write_coordinator import RevisionConflict


def is_upload_route(path):
    return re.fullmatch(r'/api/documents/DOC-\d+/attachments/uploads/[a-f0-9-]{36}', path) is not None


def dispatch(handler):
    parsed = urlparse(handler.path)
    path = unquote(parsed.path)
    maintenance = path in {'/api/document-uploads', '/api/document-uploads/recover', '/api/document-uploads/cleanup', '/api/document-uploads/abandon'}
    if not is_upload_route(path) and not maintenance:
        return False
    repository = handler.repository
    document_id, key = (None, None) if maintenance else (path.split('/')[3], path.rsplit('/', 1)[-1])
    def short(action):
        with handler.repository_switch_lock, repository.write_lock:
            if handler.repository is not repository:
                raise RevisionConflict('工作空间已切换，请查询原空间上传操作')
            return action()
    try:
        if maintenance:
            if handler.command == 'GET' and path == '/api/document-uploads':
                result = repository.document_uploads.report()
            elif handler.command == 'POST' and path.endswith(('/recover', '/cleanup')):
                if handler._body():
                    raise ValueError('维护操作不接受额外字段')
                repository.document_uploads.maintain(short, cleanup=path.endswith('/cleanup'))
                result = repository.document_uploads.report()
            elif handler.command == 'POST' and path.endswith('/abandon'):
                body = handler._body()
                if set(body) != {'operation_id', 'document_id', 'approved'} or body['approved'] is not True:
                    raise ValueError('需要明确确认原上传操作标识')
                if body['document_id'] is None:
                    result = repository.document_uploads.abandon_empty(body['operation_id'], short)
                else:
                    result = repository.document_uploads.abandon(body['document_id'], body['operation_id'], short)
            else:
                raise ValueError('上传维护方法无效')
        elif handler.command == 'GET':
            result = repository.document_uploads.query(document_id, key, short)
        elif handler.command == 'POST':
            handler.close_connection = True  # No unconsumed body can become another request.
            lengths = handler.headers.get_all('Content-Length', [])
            if handler.headers.get('Transfer-Encoding') or len(lengths) != 1 or not re.fullmatch(r'\d+', lengths[0]):
                raise ValueError('上传需要唯一Content-Length，不接受分块传输')
            length = handler._content_length(104857600)
            query = parse_qs(parsed.query)
            if set(query) != {'name', 'expected_revision'} or any(len(v) != 1 for v in query.values()):
                raise ValueError('上传参数无效')
            handler.connection.settimeout(5)
            result = repository.document_uploads.receive(document_id, key, query['name'][0], length, query['expected_revision'][0], handler.rfile, short)
        else:
            return False
        handler._json(result, 200 if maintenance or handler.command == 'GET' else 201)
    except (socket.timeout, TimeoutError):
        handler._json({'error':'上传读取超时，请查询原操作'}, 408)
    except FileNotFoundError:
        handler._json({'error':'文档或上传操作不存在'}, 404)
    except FileExistsError as error:
        handler._json({'error':str(error)}, 409)
    except AgentError as error:
        handler._json({'error':str(error), **error.payload()}, error.status)
    except (ValueError, TypeError) as error:
        handler._json({'error':str(error)}, 400)
    except OSError:
        handler._json({'error':'上传尚未完成，请查询原操作'}, 503)
    return True
