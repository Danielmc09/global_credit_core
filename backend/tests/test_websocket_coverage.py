"""Tests for WebSocket endpoints and service to improve coverage.

Tests for WebSocket functionality including connection management,
subscriptions, and broadcasting.
"""

import asyncio
import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import WebSocket, WebSocketDisconnect

from app.api.v1.endpoints.websocket import websocket_endpoint
from app.services.websocket_service import (
    ConnectionManager,
    broadcast_application_update,
    redis_subscriber,
)
from app.services.application_service import ApplicationService
from app.schemas.application import ApplicationCreate
from decimal import Decimal


class TestWebSocketEndpoint:
    """Test suite for WebSocket endpoint"""

    @pytest.mark.asyncio
    async def test_websocket_connection(self):
        """Test WebSocket connection and welcome message"""
        mock_websocket = AsyncMock(spec=WebSocket)
        mock_websocket.accept = AsyncMock()
        mock_websocket.receive_json = AsyncMock(side_effect=WebSocketDisconnect())
        
        with patch('app.api.v1.endpoints.websocket.manager') as mock_manager:
            mock_manager.connect = AsyncMock()
            mock_manager.send_personal_message = AsyncMock()
            mock_manager.disconnect = MagicMock()
            
            await websocket_endpoint(mock_websocket)
            
            mock_manager.connect.assert_called_once()
            mock_manager.send_personal_message.assert_called_once()

    @pytest.mark.asyncio
    async def test_websocket_subscribe(self):
        """Test WebSocket subscription to application updates"""
        mock_websocket = AsyncMock(spec=WebSocket)
        mock_websocket.accept = AsyncMock()
        
        call_count = 0
        async def receive_json():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {"action": "subscribe", "application_id": "test-app-id"}
            else:
                raise WebSocketDisconnect()
        
        mock_websocket.receive_json = receive_json
        
        with patch('app.api.v1.endpoints.websocket.manager') as mock_manager:
            mock_manager.connect = AsyncMock()
            mock_manager.send_personal_message = AsyncMock()
            mock_manager.subscribe = MagicMock()
            mock_manager.disconnect = MagicMock()
            
            await websocket_endpoint(mock_websocket)
            
            mock_manager.subscribe.assert_called_once()
            assert mock_manager.send_personal_message.call_count >= 2  

    @pytest.mark.asyncio
    async def test_websocket_ping(self):
        """Test WebSocket ping/pong keepalive"""
        mock_websocket = AsyncMock(spec=WebSocket)
        mock_websocket.accept = AsyncMock()
        
        call_count = 0
        async def receive_json():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {"action": "ping"}
            else:
                raise WebSocketDisconnect()
        
        mock_websocket.receive_json = receive_json
        
        with patch('app.api.v1.endpoints.websocket.manager') as mock_manager:
            mock_manager.connect = AsyncMock()
            mock_manager.send_personal_message = AsyncMock()
            mock_manager.disconnect = MagicMock()
            
            await websocket_endpoint(mock_websocket)
            
            calls = [call[0][0] for call in mock_manager.send_personal_message.call_args_list]
            pong_calls = [call for call in calls if call.get("type") == "pong"]
            assert len(pong_calls) > 0

    @pytest.mark.asyncio
    async def test_websocket_error_handling(self):
        """Test WebSocket error handling"""
        mock_websocket = AsyncMock(spec=WebSocket)
        mock_websocket.accept = AsyncMock()
        mock_websocket.receive_json = AsyncMock(side_effect=Exception("Connection error"))
        
        with patch('app.api.v1.endpoints.websocket.manager') as mock_manager:
            mock_manager.connect = AsyncMock()
            mock_manager.disconnect = MagicMock()
            
            await websocket_endpoint(mock_websocket)
            mock_manager.disconnect.assert_called_once()


class TestWebSocketService:
    """Test suite for WebSocket service"""

    @pytest.mark.asyncio
    async def test_connection_manager_connect(self):
        """Test connecting a WebSocket client"""
        manager = ConnectionManager()
        mock_websocket = AsyncMock(spec=WebSocket)
        mock_websocket.accept = AsyncMock()
        
        await manager.connect(mock_websocket, "connection-1")
        
        assert "connection-1" in manager.active_connections
        mock_websocket.accept.assert_called_once()

    def test_connection_manager_disconnect(self):
        """Test disconnecting a WebSocket client"""
        manager = ConnectionManager()
        manager.active_connections["connection-1"] = MagicMock()
        manager.subscriptions["app-1"] = {"connection-1", "connection-2"}
        
        manager.disconnect("connection-1")
        
        assert "connection-1" not in manager.active_connections
        assert "connection-1" not in manager.subscriptions["app-1"]
        assert "connection-2" in manager.subscriptions["app-1"]

    def test_connection_manager_disconnect_removes_empty_subscriptions(self):
        """Test that disconnecting removes empty subscriptions"""
        manager = ConnectionManager()
        manager.active_connections["connection-1"] = MagicMock()
        manager.subscriptions["app-1"] = {"connection-1"}
        
        manager.disconnect("connection-1")
        
        assert "app-1" not in manager.subscriptions

    def test_connection_manager_subscribe(self):
        """Test subscribing to application updates"""
        manager = ConnectionManager()
        
        manager.subscribe("connection-1", "app-1")
        
        assert "app-1" in manager.subscriptions
        assert "connection-1" in manager.subscriptions["app-1"]

    @pytest.mark.asyncio
    async def test_connection_manager_send_personal_message(self):
        """Test sending a personal message"""
        manager = ConnectionManager()
        mock_websocket = AsyncMock(spec=WebSocket)
        mock_websocket.send_json = AsyncMock()
        manager.active_connections["connection-1"] = mock_websocket
        
        await manager.send_personal_message({"type": "test"}, "connection-1")
        
        mock_websocket.send_json.assert_called_once_with({"type": "test"})

    @pytest.mark.asyncio
    async def test_connection_manager_send_personal_message_not_found(self):
        """Test sending message to non-existent connection"""
        manager = ConnectionManager()
        
        await manager.send_personal_message({"type": "test"}, "non-existent")

    @pytest.mark.asyncio
    async def test_connection_manager_broadcast(self):
        """Test broadcasting to all connections"""
        manager = ConnectionManager()
        mock_websocket1 = AsyncMock(spec=WebSocket)
        mock_websocket1.send_json = AsyncMock()
        mock_websocket2 = AsyncMock(spec=WebSocket)
        mock_websocket2.send_json = AsyncMock()
        
        manager.active_connections["conn-1"] = mock_websocket1
        manager.active_connections["conn-2"] = mock_websocket2
        
        await manager.broadcast({"type": "broadcast"})
        
        assert mock_websocket1.send_json.call_count == 1
        assert mock_websocket2.send_json.call_count == 1

    @pytest.mark.asyncio
    async def test_connection_manager_broadcast_error_handling(self):
        """Test broadcast error handling when sending fails"""
        manager = ConnectionManager()
        mock_websocket1 = AsyncMock(spec=WebSocket)
        mock_websocket1.send_json = AsyncMock(side_effect=Exception("Send error"))
        mock_websocket2 = AsyncMock(spec=WebSocket)
        mock_websocket2.send_json = AsyncMock()
        
        manager.active_connections["conn-1"] = mock_websocket1
        manager.active_connections["conn-2"] = mock_websocket2
        
        await manager.broadcast({"type": "broadcast"})
        
        assert "conn-1" not in manager.active_connections
        assert "conn-2" in manager.active_connections

    @pytest.mark.asyncio
    async def test_connection_manager_broadcast_to_application(self):
        """Test broadcasting to application subscribers"""
        manager = ConnectionManager()
        mock_websocket1 = AsyncMock(spec=WebSocket)
        mock_websocket1.send_json = AsyncMock()
        mock_websocket2 = AsyncMock(spec=WebSocket)
        mock_websocket2.send_json = AsyncMock()
        
        manager.subscriptions["app-1"] = {"conn-1", "conn-2"}
        manager.active_connections["conn-1"] = mock_websocket1
        manager.active_connections["conn-2"] = mock_websocket2
        
        await manager.broadcast_to_application("app-1", {"type": "update"})
        
        assert mock_websocket1.send_json.call_count == 1
        assert mock_websocket2.send_json.call_count == 1

    @pytest.mark.asyncio
    async def test_connection_manager_broadcast_to_application_no_subscribers(self):
        """Test broadcasting to application with no subscribers"""
        manager = ConnectionManager()
        
        await manager.broadcast_to_application("app-none", {"type": "update"})

    @pytest.mark.asyncio
    async def test_connection_manager_broadcast_to_application_error_handling(self):
        """Test broadcast to application error handling"""
        manager = ConnectionManager()
        mock_websocket = AsyncMock(spec=WebSocket)
        mock_websocket.send_json = AsyncMock(side_effect=Exception("Send error"))
        
        manager.subscriptions["app-1"] = {"conn-1"}
        manager.active_connections["conn-1"] = mock_websocket
        
        await manager.broadcast_to_application("app-1", {"type": "update"})
        
        assert "conn-1" not in manager.active_connections

    @pytest.mark.asyncio
    async def test_broadcast_application_update(self, test_db):
        """Test broadcasting application update via Redis"""
        async with test_db() as db:
            service = ApplicationService(db)
            app_data = ApplicationCreate(
                country="ES",
                full_name="Test User",
                identity_document="12345678Z",
                requested_amount=Decimal("10000.00"),
                monthly_income=Decimal("3000.00"),
                currency="EUR"
            )
            application = await service.create_application(app_data)
            db.expire(application)
            await db.commit()
            await db.refresh(application)
            application_id_str = str(application.id)

            with patch('app.services.websocket_service.get_redis') as mock_get_redis:
                mock_redis = AsyncMock()
                mock_redis.publish = AsyncMock()
                mock_get_redis.return_value = mock_redis

                await broadcast_application_update(application)

                mock_redis.publish.assert_called_once()
                call_args = mock_redis.publish.call_args
                assert call_args[0][0] == 'websocket:broadcast'
                message = json.loads(call_args[0][1])
                assert message["type"] == "application_update"
                assert message["data"]["id"] == application_id_str

    @pytest.mark.asyncio
    async def test_broadcast_application_update_redis_error(self, test_db):
        """Test broadcast when Redis publish fails"""
        async with test_db() as db:
            service = ApplicationService(db)
            app_data = ApplicationCreate(
                country="ES",
                full_name="Test User",
                identity_document="12345678Z",
                requested_amount=Decimal("10000.00"),
                monthly_income=Decimal("3000.00"),
                currency="EUR"
            )
            application = await service.create_application(app_data)
            db.expire(application)
            await db.commit()
            await db.refresh(application)
            application_id_str = str(application.id)
            with patch('app.services.websocket_service.get_redis') as mock_get_redis:
                mock_redis = AsyncMock()
                mock_redis.publish = AsyncMock(side_effect=Exception("Redis error"))
                mock_get_redis.return_value = mock_redis

                await broadcast_application_update(application)

    @pytest.mark.asyncio
    async def test_redis_subscriber_success(self, monkeypatch):
        """Test Redis subscriber successfully processing messages"""
        mock_redis = AsyncMock()
        mock_pubsub = AsyncMock()
        mock_redis.pubsub.return_value = mock_pubsub
        
        messages = [
            {'type': 'subscribe', 'channel': b'websocket:broadcast'},
            {'type': 'message', 'data': json.dumps({"type": "test", "broadcast": True})},
        ]
        
        async def listen():
            for msg in messages:
                yield msg
                if msg['type'] == 'message':
                    break
        
        mock_pubsub.subscribe = AsyncMock()
        mock_pubsub.listen = listen
        
        with patch('app.services.websocket_service.get_redis', return_value=mock_redis):
            with patch('app.services.websocket_service.manager') as mock_manager:
                mock_manager.broadcast = AsyncMock()

                task = asyncio.create_task(redis_subscriber())
                await asyncio.sleep(0.1)  
                task.cancel()
                
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    @pytest.mark.asyncio
    async def test_redis_subscriber_json_decode_error(self, monkeypatch):
        """Test Redis subscriber handling JSON decode errors"""
        mock_redis = AsyncMock()
        mock_pubsub = AsyncMock()
        mock_redis.pubsub.return_value = mock_pubsub
        
        messages = [
            {'type': 'subscribe', 'channel': b'websocket:broadcast'},
            {'type': 'message', 'data': 'invalid json'},
        ]
        
        async def listen():
            for msg in messages:
                yield msg
                if msg['type'] == 'message':
                    break
        
        mock_pubsub.subscribe = AsyncMock()
        mock_pubsub.listen = listen
        
        with patch('app.services.websocket_service.get_redis', return_value=mock_redis):
            task = asyncio.create_task(redis_subscriber())
            await asyncio.sleep(0.1)
            task.cancel()
            
            try:
                await task
            except asyncio.CancelledError:
                pass

    @pytest.mark.asyncio
    async def test_redis_subscriber_retry_logic(self, monkeypatch):
        """Test Redis subscriber retry logic on connection failure"""
        call_count = 0
        
        async def failing_get_redis():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("Connection failed")
            mock_redis = AsyncMock()
            mock_pubsub = AsyncMock()
            mock_redis.pubsub.return_value = mock_pubsub
            mock_pubsub.subscribe = AsyncMock()
            
            async def listen():
                yield {'type': 'subscribe', 'channel': b'websocket:broadcast'}
                await asyncio.sleep(0.1)
            
            mock_pubsub.listen = listen
            return mock_redis
        
        with patch('app.services.websocket_service.get_redis', side_effect=failing_get_redis):
            task = asyncio.create_task(redis_subscriber())
            await asyncio.sleep(0.2)  
            task.cancel()
            
            try:
                await task
            except asyncio.CancelledError:
                pass
