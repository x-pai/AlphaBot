"""Binding ownership, migration, transport gating and QQ protocol regression tests."""
import hashlib
from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base, get_db
from app.core.config import settings
from app.models.user import User
from app.models.channel import ChannelBinding, ChannelBindingCode, ChannelTarget
from app.models.task import ScheduledTask
from app.services import channel_service as service
from app.services import qq_service as qq
from app.services.channel_migration import migrate_channels
from app.api.routes.channels import router, unbind
from app.api.routes.user import get_current_user

@pytest.fixture
def channel_db(monkeypatch):
    engine = create_engine('sqlite://', poolclass=StaticPool, connect_args={'check_same_thread': False})
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as db:
        db.add_all([User(id=101, username='alice', email='alice@test', hashed_password='unused'), User(id=102, username='bob', email='bob@test', hashed_password='unused')])
        db.commit()
        monkeypatch.setattr(settings, 'QQ_BOT_ENABLED', True)
        monkeypatch.setattr(settings, 'QQ_BOT_APP_ID', 'app1')
        monkeypatch.setattr(settings, 'QQ_BOT_APP_SECRET', SecretStr('test-secret'))
        monkeypatch.setattr(settings, 'TELEGRAM_BOT_TOKEN', '123:secret')
        monkeypatch.setattr(settings, 'TELEGRAM_ENABLED', True)
        monkeypatch.setattr(settings, 'FEISHU_APP_ID', 'feishu-app')
        service._attempts.clear()
        yield db
    engine.dispose()

def bind(db, user=101, channel='qq', sender='openid', target='openid', kind='private'):
    code = service.create_code(db, user, channel, kind)['code']
    return service.bind_message(db, channel, sender, target, kind, f'绑定 {code}')

def test_code_single_use_and_hash_only(channel_db):
    db = channel_db
    raw = service.create_code(db, 101, 'qq', 'private')['code']
    record = db.query(ChannelBindingCode).one()
    assert record.digest == hashlib.sha256(raw.encode()).hexdigest()
    assert record.digest != raw
    assert '绑定成功' in service.bind_message(db, 'qq', 'openid', 'openid', 'private', f'绑定 {raw}')
    assert '无效' in service.bind_message(db, 'qq', 'openid', 'openid', 'private', f'绑定 {raw}')
    assert service.resolve_user(db, 'qq', 'openid').id == 101
    assert db.query(ChannelTarget).one().user_id == 101

def test_expiry_and_channel_scope(channel_db):
    db = channel_db
    raw = service.create_code(db, 101, 'qq', 'private')['code']
    assert '无效' in service.bind_message(db, 'telegram', 'openid', 'openid', 'private', f'绑定 {raw}')
    db.query(ChannelBindingCode).one().expires_at = datetime.utcnow() - timedelta(seconds=1)
    db.commit()
    assert '过期' in service.bind_message(db, 'qq', 'openid', 'openid', 'private', f'绑定 {raw}')

def test_identity_conflict_does_not_consume_code(channel_db):
    assert '成功' in bind(channel_db)
    assert '不能覆盖' in bind(channel_db, user=102)
    assert service.resolve_user(channel_db, 'qq', 'openid').id == 101
    assert channel_db.query(ChannelBindingCode).filter_by(user_id=102).one().consumed_at is None

def test_group_requires_bound_requester(channel_db):
    assert '请先私聊' in bind(channel_db, target='group1', kind='group')
    bind(channel_db)
    assert '成功' in bind(channel_db, target='group1', kind='group')
    assert '不能覆盖' in bind(channel_db, user=102, target='group1', kind='group')

def test_unbind_revokes_targets_and_no_auto_rebind(channel_db):
    bind(channel_db)
    binding = channel_db.query(ChannelBinding).one()
    unbind(binding.id, channel_db, channel_db.get(User, 101))
    assert service.resolve_user(channel_db, 'qq', 'openid') is None
    assert channel_db.query(ChannelTarget).count() == 0
    assert '成功' in bind(channel_db, user=102)
    assert service.resolve_user(channel_db, 'qq', 'openid').id == 102

def test_bot_rotation_and_cross_user_denied(channel_db, monkeypatch):
    bind(channel_db)
    target = channel_db.query(ChannelTarget).one()
    with pytest.raises(ValueError):
        service.owned_target(channel_db, 102, target.id)
    monkeypatch.setattr(settings, 'QQ_BOT_APP_ID', 'replacement')
    assert service.resolve_user(channel_db, 'qq', 'openid') is None
    with pytest.raises(ValueError):
        service.owned_target(channel_db, 101, target.id)

def test_attempt_limit(channel_db):
    for _ in range(5):
        service.bind_message(channel_db, 'qq', 'bad', 'bad', 'private', '绑定 invalid')
    assert '次数过多' in service.bind_message(channel_db, 'qq', 'bad', 'bad', 'private', '绑定 invalid')

def test_events_deduplicated(channel_db):
    assert service.claim_event(channel_db, 'qq', 'message1')
    assert not service.claim_event(channel_db, 'qq', 'message1')
    assert service.claim_event(channel_db, 'telegram', 'message1')

@pytest.mark.asyncio
async def test_send_ownership_and_disabled_gate(channel_db, monkeypatch):
    bind(channel_db)
    target = channel_db.query(ChannelTarget).one()
    send = AsyncMock(return_value={'success': True})
    monkeypatch.setattr(qq, 'send_qq_message', send)
    assert not (await service.send_target(channel_db, 102, target.id, 'secret'))['success']
    send.assert_not_awaited()
    monkeypatch.setattr(settings, 'QQ_BOT_ENABLED', False)
    result = await service.send_target(channel_db, 101, target.id, 'hello')
    assert not result['success'] and '关闭' in result['error']
    send.assert_not_awaited()
    monkeypatch.setattr(settings, 'QQ_BOT_ENABLED', True)
    assert (await service.send_target(channel_db, 101, target.id, 'hello'))['success']
    send.assert_awaited_once_with('private:openid', 'hello')

@pytest.mark.asyncio
async def test_raw_unknown_target_rejected(channel_db):
    result = await service.send_configured(channel_db, 101, {'type': 'telegram', 'chat_id': 'victim'}, 'hello')
    assert not result['success']

def test_migration_preserves_owned_targets_and_feishu(channel_db):
    db = channel_db
    db.add(User(id=103, username='feishu_old', email='old@test', hashed_password='unused'))
    db.add(ScheduledTask(task_id='owned', task_type='skill_publish_job', params={'user_id': 101, 'notify_channel': {'type': 'telegram', 'chat_id': '100'}}))
    db.add(ScheduledTask(task_id='unknown', task_type='skill_publish_job', params={'notify_channel': {'type': 'telegram', 'chat_id': '200'}}))
    db.commit()
    migrate_channels(db)
    migrate_channels(db)
    assert service.resolve_user(db, 'feishu', 'old').id == 103
    assert db.query(ChannelTarget).count() == 1
    assert db.query(ScheduledTask).filter_by(task_id='owned').one().params['notify_channel']['target_id']
    assert 'target_id' not in db.query(ScheduledTask).filter_by(task_id='unknown').one().params['notify_channel']
    b = db.query(ChannelBinding).filter_by(channel='feishu').one()
    unbind(b.id, db, db.get(User, 103))
    assert service.resolve_user(db, 'feishu', 'old') is None

def test_personal_api_ownership_and_no_secrets(channel_db):
    bind(channel_db)
    app = FastAPI()
    app.include_router(router, prefix="/channels")
    app.dependency_overrides[get_db] = lambda: channel_db
    app.dependency_overrides[get_current_user] = lambda: channel_db.get(User, 102)
    client = TestClient(app)
    data = client.get('/channels').json()['data']
    assert data['targets'] == [] and data['bindings'] == []
    assert 'test-secret' not in str(data)
    target = channel_db.query(ChannelTarget).one()
    assert client.delete(f'/channels/targets/{target.id}').status_code == 404
    assert client.patch(f'/channels/targets/{target.id}', json={'name': 'steal'}).status_code == 400
    result = client.post(f'/channels/targets/{target.id}/test').json()['data']
    assert not result['success']

@pytest.mark.asyncio
async def test_qq_reply_vs_proactive(channel_db, monkeypatch):
    request = AsyncMock(return_value={'success': True, 'id': 'sent'})
    monkeypatch.setattr(qq, 'api_request', request)
    assert (await qq.send_qq_message('private:user1', 'hello'))['success']
    assert 'msg_id' not in request.call_args.args[2]
    assert request.call_args.args[1] == '/v2/users/user1/messages'
    await qq.send_qq_message('group:group1', 'reply', 'inbound1')
    assert request.call_args.args[2]['msg_id'] == 'inbound1'
    assert request.call_args.args[1] == '/v2/groups/group1/messages'

@pytest.mark.asyncio
async def test_qq_token_cache_and_business_error(channel_db, monkeypatch):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={'access_token': 'cached', 'expires_in': 7200})
    original = httpx.AsyncClient
    monkeypatch.setattr(qq.httpx, 'AsyncClient', lambda **kw: original(transport=httpx.MockTransport(handler), **kw))
    monkeypatch.setattr(qq, '_token', '')
    monkeypatch.setattr(qq, '_expires', 0)
    assert await qq.access_token() == 'cached'
    assert await qq.access_token() == 'cached'
    assert len(calls) == 1
    monkeypatch.setattr(qq, '_expires', 0)
    def failed(request):
        return httpx.Response(200, json={'code': 100016})
    monkeypatch.setattr(qq.httpx, 'AsyncClient', lambda **kw: original(transport=httpx.MockTransport(failed), **kw))
    with pytest.raises(ValueError, match='100016'):
        await qq.access_token()

@pytest.mark.asyncio
async def test_qq_401_refresh_and_rate_limit(channel_db, monkeypatch):
    statuses = [401, 429, 200]
    def handler(request):
        status = statuses.pop(0)
        return httpx.Response(status, json={'id': 'sent'} if status == 200 else {'code': status})
    original = httpx.AsyncClient
    monkeypatch.setattr(qq.httpx, 'AsyncClient', lambda **kw: original(transport=httpx.MockTransport(handler), **kw))
    monkeypatch.setattr(qq, 'access_token', AsyncMock(return_value='token'))
    monkeypatch.setattr(qq.asyncio, 'sleep', AsyncMock())
    assert (await qq.api_request('POST', '/v2/users/user/messages', {'content': 'hello'}))['success']
    assert not statuses

@pytest.mark.asyncio
async def test_webhook_rejects_private_addresses():
    from app.services.webhook_security import validate_webhook_url
    for url in ('http://example.com', 'https://127.0.0.1/hook', 'https://[::1]/hook', 'https://user:secret@example.com'):
        with pytest.raises(ValueError):
            await validate_webhook_url(url)

@pytest.mark.asyncio
async def test_unknown_inbound_never_calls_agent(channel_db, monkeypatch):
    from app.services.channel_inbound import process_inbound
    from app.services.agent_service import AgentService
    agent = AsyncMock()
    monkeypatch.setattr(AgentService, 'process_channel_message', agent)
    assert '绑定' in await process_inbound(channel_db, 'telegram', 'unknown', 'chat', 'private', 'hello')
    agent.assert_not_awaited()

@pytest.mark.asyncio
async def test_bound_inbound_uses_owner_and_target(channel_db, monkeypatch):
    from types import SimpleNamespace
    from app.services.channel_inbound import process_inbound
    from app.services.agent_service import AgentService
    bind(channel_db)
    agent = AsyncMock(return_value=SimpleNamespace(content='reply'))
    monkeypatch.setattr(AgentService, 'process_channel_message', agent)
    assert await process_inbound(channel_db, 'qq', 'openid', 'openid', 'private', 'hello') == 'reply'
    assert agent.call_args.kwargs['user'].id == 101
    message = agent.call_args.kwargs['message']
    assert message.metadata['notify_channel']['target_id'] == channel_db.query(ChannelTarget).one().id

@pytest.mark.asyncio
async def test_qq_gateway_identify_heartbeat_resume_and_shutdown(channel_db, monkeypatch, tmp_path):
    import asyncio
    import contextlib
    import json
    import websockets.asyncio.client
    monkeypatch.setattr(settings, 'QQ_BOT_LOCK_PATH', str(tmp_path / 'qq.lock'))
    monkeypatch.setattr(qq, 'api_request', AsyncMock(return_value={'success': True, 'url': 'wss://gateway.test'}))
    monkeypatch.setattr(qq, 'access_token', AsyncMock(return_value='fake-token'))
    monkeypatch.setattr(qq.random, 'random', lambda: 0)
    handled = AsyncMock()
    monkeypatch.setattr(qq, 'handle_event', handled)
    connections = []
    class Socket:
        def __init__(self):
            self.queue = asyncio.Queue()
            self.queue.put_nowait({'op': 10, 'd': {'heartbeat_interval': 1000}})
            self.sent = []
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def recv(self):
            return json.dumps(await self.queue.get())
        async def send(self, message):
            data = json.loads(message)
            self.sent.append(data)
            if data['op'] == 1:
                self.queue.put_nowait({'op': 11})
            elif data['op'] == 2:
                self.queue.put_nowait({'op': 0, 't': 'READY', 's': 1, 'd': {'session_id': 'session'}})
            elif data['op'] == 6:
                self.queue.put_nowait({'op': 0, 't': 'RESUMED', 's': 2, 'd': {}})
        async def close(self):
            pass
    def connect(*args, **kwargs):
        socket = Socket()
        connections.append(socket)
        return socket
    monkeypatch.setattr(websockets.asyncio.client, 'connect', connect)
    async def until(predicate):
        for _ in range(400):
            if predicate():
                return
            await asyncio.sleep(0.01)
        pytest.fail('gateway did not progress')
    task = asyncio.create_task(qq.run_qq_gateway())
    try:
        await until(lambda: connections and connections[0].sent)
        assert connections[0].sent[0]['op'] == 2
        assert connections[0].sent[0]['d']['intents'] == 1 << 25
        await until(lambda: any(m['op'] == 1 for m in connections[0].sent))
        connections[0].queue.put_nowait({'op': 0, 't': 'C2C_MESSAGE_CREATE', 's': 5, 'd': {'id': 'event'}})
        await until(lambda: handled.await_count == 1)
        connections[0].queue.put_nowait({'op': 7})
        await until(lambda: len(connections) == 2 and connections[1].sent)
        assert connections[1].sent[0]['op'] == 6
        assert connections[1].sent[0]['d']['seq'] == 5
        connections[1].queue.put_nowait({'op': 9, 'd': False})
        await until(lambda: len(connections) == 3 and connections[2].sent)
        assert connections[2].sent[0]['op'] == 2
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
    assert qq.connection_status() == '已停止'

@pytest.mark.asyncio
async def test_qq_http200_business_error(channel_db, monkeypatch):
    original = httpx.AsyncClient
    def handler(request):
        return httpx.Response(200, json={'err_code': 40034005, 'message': 'expired'})
    monkeypatch.setattr(qq.httpx, 'AsyncClient', lambda **kw: original(transport=httpx.MockTransport(handler), **kw))
    monkeypatch.setattr(qq, 'access_token', AsyncMock(return_value='token'))
    result = await qq.api_request('POST', '/v2/users/user/messages', {'content': 'hello'})
    assert not result['success'] and result['code'] == 40034005

@pytest.mark.asyncio
async def test_retry_notification_does_not_run_agent(channel_db, monkeypatch):
    from app.api.routes.tasks import retry_notification
    from app.services.scheduler_service import SchedulerService
    from types import SimpleNamespace
    bind(channel_db)
    target = channel_db.query(ChannelTarget).one()
    stored = {'params': {'user_id': 101, 'notify_channel': {'type': 'qq', 'target_id': target.id}}, 'result': {'notification_text': 'saved report'}}
    scheduler = SimpleNamespace(get_task=AsyncMock(return_value=stored), _tasks={'task': SimpleNamespace(last_result=None)}, _persist_task_state=lambda obj: None)
    monkeypatch.setattr('app.api.routes.tasks.SchedulerService', lambda: scheduler)
    sender = AsyncMock(return_value={'success': True})
    monkeypatch.setattr(qq, 'send_qq_message', sender)
    result = await retry_notification('task', channel_db, channel_db.get(User, 101))
    assert result['data']['success']
    sender.assert_awaited_once_with('private:openid', 'saved report')


def test_http_log_redacts_bot_credentials(channel_db):
    import logging
    from app.middleware.logging import ChannelCredentialFilter
    record = logging.LogRecord('httpx', logging.INFO, '', 0, 'POST %s', ('https://api.telegram.org/bot123:secret/sendMessage',), None)
    assert ChannelCredentialFilter().filter(record)
    assert '123:secret' not in record.getMessage()
    assert '[redacted]' in record.getMessage()


def test_deleted_destination_id_not_reused(channel_db):
    first = service.add_target(channel_db, 101, 'qq', 'private', 'first')
    channel_db.commit()
    old_id = first.id
    channel_db.delete(first)
    channel_db.commit()
    second = service.add_target(channel_db, 101, 'qq', 'private', 'second')
    channel_db.commit()
    assert second.id != old_id
    with pytest.raises(ValueError):
        service.owned_target(channel_db, 101, old_id)


@pytest.mark.asyncio
async def test_qq_error_details_survive_delivery_storage(channel_db, monkeypatch):
    bind(channel_db)
    target = channel_db.query(ChannelTarget).one()
    original = httpx.AsyncClient
    def handler(request):
        return httpx.Response(403, headers={'X-Tps-trace-ID': 'trace-123'}, json={
            'err_code': 11253, 'message': 'permission denied test-secret token-private'})
    monkeypatch.setattr(qq.httpx, 'AsyncClient', lambda **kw: original(transport=httpx.MockTransport(handler), **kw))
    monkeypatch.setattr(qq, '_token', 'token-private')
    monkeypatch.setattr(qq, 'access_token', AsyncMock(return_value='token-private'))
    result = await service.send_target(channel_db, 101, target.id, 'hello')
    assert not result['success']
    assert result['code'] == 11253 and result['http_status'] == 403
    assert result['trace_id'] == 'trace-123'
    assert 'permission denied' in result['error']
    assert 'test-secret' not in str(result) and 'token-private' not in str(result)
    assert 'trace-123' in target.last_result and '11253' in target.last_result


@pytest.mark.asyncio
async def test_qq_non_json_and_token_failure_details(channel_db, monkeypatch):
    original = httpx.AsyncClient
    def handler(request):
        if request.url.path.endswith('getAppAccessToken'):
            return httpx.Response(200, json={'code': 100016, 'message': 'invalid app secret', 'trace_id': 'auth-trace'})
        return httpx.Response(502, text='<html>bad gateway</html>', headers={'X-Tps-trace-ID': 'proxy-trace'})
    monkeypatch.setattr(qq.httpx, 'AsyncClient', lambda **kw: original(transport=httpx.MockTransport(handler), **kw))
    monkeypatch.setattr(qq, '_expires', 0)
    auth = await qq.send_qq_message('private:user', 'hello')
    assert auth['code'] == 100016 and auth['stage'] == '获取访问凭证'
    assert 'invalid app secret' in auth['error'] and auth['trace_id'] == 'auth-trace'
    monkeypatch.setattr(qq, 'access_token', AsyncMock(return_value='token'))
    network = await qq.send_qq_message('private:user', 'hello')
    assert network['http_status'] == 502 and network['trace_id'] == 'proxy-trace'
    assert 'HTTP 502' in network['error'] and '<html>' not in network['error']


def test_binding_status_owned_and_consumed(channel_db):
    app = FastAPI()
    app.include_router(router, prefix='/channels')
    app.dependency_overrides[get_db] = lambda: channel_db
    app.dependency_overrides[get_current_user] = lambda: channel_db.get(User, 101)
    client = TestClient(app)
    code = client.post('/channels/binding-codes', json={'channel': 'qq', 'kind': 'private'}).json()['data']
    path = f"/channels/binding-codes/{code['code_id']}"
    response = client.get(path).json()['data']
    assert response == {'status': 'pending'}
    service.bind_message(channel_db, 'qq', 'new-user', 'new-user', 'private', f"绑定 {code['code']}")
    assert client.get(path).json()['data'] == {'status': 'consumed'}
    app.dependency_overrides[get_current_user] = lambda: channel_db.get(User, 102)
    assert client.get(path).status_code == 404
    app.dependency_overrides[get_current_user] = lambda: channel_db.get(User, 101)
    expired = service.create_code(channel_db, 101, 'qq', 'private')
    channel_db.get(ChannelBindingCode, expired['code_id']).expires_at = datetime.utcnow() - timedelta(seconds=1)
    channel_db.commit()
    assert client.get(f"/channels/binding-codes/{expired['code_id']}").json()['data'] == {'status': 'expired'}
