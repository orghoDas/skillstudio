"""
WebSocket consumers for live streaming signaling.
Handles WebRTC signaling for peer-to-peer video streaming.
"""

import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from live.models import LiveSession, SessionParticipant

User = get_user_model()


class LiveStreamConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for live streaming signaling.
    Handles WebRTC offer/answer/ICE candidate exchange between instructor and students.
    """
    
    async def connect(self):
        """Handle WebSocket connection."""
        self.session_id = self.scope['url_route']['kwargs']['session_id']
        self.room_group_name = f'live_session_{self.session_id}'
        
        # Authenticate user from token
        token = self.scope['query_string'].decode().split('token=')[-1] if b'token=' in self.scope['query_string'] else None
        if token:
            try:
                access_token = AccessToken(token)
                user_id = access_token['user_id']
                self.user = await self.get_user_by_id(user_id)
                self.scope['user'] = self.user
            except (InvalidToken, TokenError):
                self.user = None
        else:
            self.user = self.scope.get('user')
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Get user info
        user_info = await self.get_user_info()
        
        # Notify others that a user joined
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'user_joined',
                'user_id': user_info['id'],
                'user_name': user_info['name'],
                'is_instructor': user_info['is_instructor']
            }
        )
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        user_info = await self.get_user_info()
        
        # Notify others that a user left
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'user_left',
                'user_id': user_info['id'],
                'user_name': user_info['name']
            }
        )
        
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
    
    async def receive(self, text_data):
        """Receive message from WebSocket."""
        data = json.loads(text_data)
        message_type = data.get('type')
        
        # Handle different message types
        if message_type == 'offer':
            # Instructor sends offer to all students
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'webrtc_offer',
                    'offer': data.get('offer'),
                    'sender_id': data.get('sender_id')
                }
            )
        
        elif message_type == 'answer':
            # Student sends answer back to instructor
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'webrtc_answer',
                    'answer': data.get('answer'),
                    'sender_id': data.get('sender_id'),
                    'target_id': data.get('target_id')
                }
            )
        
        elif message_type == 'ice-candidate':
            # Exchange ICE candidates
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'ice_candidate',
                    'candidate': data.get('candidate'),
                    'sender_id': data.get('sender_id'),
                    'target_id': data.get('target_id')
                }
            )
        
        elif message_type == 'chat':
            # Handle chat messages
            user_info = await self.get_user_info()
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message': data.get('message'),
                    'user_id': user_info['id'],
                    'user_name': user_info['name'],
                    'timestamp': data.get('timestamp')
                }
            )
    
    # Message handlers
    async def user_joined(self, event):
        """Send user joined notification to WebSocket."""
        await self.send(text_data=json.dumps({
            'type': 'user_joined',
            'user_id': event['user_id'],
            'user_name': event['user_name'],
            'is_instructor': event['is_instructor']
        }))
    
    async def user_left(self, event):
        """Send user left notification to WebSocket."""
        await self.send(text_data=json.dumps({
            'type': 'user_left',
            'user_id': event['user_id'],
            'user_name': event['user_name']
        }))
    
    async def webrtc_offer(self, event):
        """Forward WebRTC offer to all clients."""
        await self.send(text_data=json.dumps({
            'type': 'offer',
            'offer': event['offer'],
            'sender_id': event['sender_id']
        }))
    
    async def webrtc_answer(self, event):
        """Forward WebRTC answer to target client."""
        user_info = await self.get_user_info()
        # Only send to the target
        if event.get('target_id') == user_info['id']:
            await self.send(text_data=json.dumps({
                'type': 'answer',
                'answer': event['answer'],
                'sender_id': event['sender_id']
            }))
    
    async def ice_candidate(self, event):
        """Forward ICE candidate to target client."""
        user_info = await self.get_user_info()
        # Send to all if no target, or only to target if specified
        if not event.get('target_id') or event.get('target_id') == user_info['id']:
            await self.send(text_data=json.dumps({
                'type': 'ice-candidate',
                'candidate': event['candidate'],
                'sender_id': event['sender_id']
            }))
    
    async def chat_message(self, event):
        """Forward chat message to all clients."""
        await self.send(text_data=json.dumps({
            'type': 'chat',
            'message': event['message'],
            'user_id': event['user_id'],
            'user_name': event['user_name'],
            'timestamp': event['timestamp']
        }))
    
    @database_sync_to_async
    def get_user_info(self):
        """Get user information from database."""
        if not self.user or not self.user.is_authenticated:
            return {'id': None, 'name': 'Anonymous', 'is_instructor': False}
        
        session = LiveSession.objects.get(id=self.session_id)
        is_instructor = session.instructor == self.user
        
        # Get user name
        name = self.user.email
        if hasattr(self.user, 'profile') and self.user.profile:
            profile = self.user.profile
            full_name = f"{profile.first_name or ''} {profile.last_name or ''}".strip()
            name = full_name or self.user.username or self.user.email
        elif self.user.username:
            name = self.user.username
        
        return {
            'id': self.user.id,
            'name': name,
            'is_instructor': is_instructor
        }
    
    @database_sync_to_async
    def get_user_by_id(self, user_id):
        """Get user by ID from database."""
        try:
            return User.objects.get(id=user_id)
        except User.DoesNotExist:
            return None
