import json
import asyncio
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import User
from dashboard.models import ChatRoom, ChatMessage
from django.utils import timezone

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.room_id = self.scope['url_route']['kwargs']['room_id']
        self.room_group_name = f'chat_{self.room_id}'
        
        if not self.scope["user"].is_authenticated:
            await self.close()
            return
            
        has_permission = await self.check_permission()
        if not has_permission:
            await self.close()
            return
            
        await self.channel_layer.group_add( 
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        await self.send_chat_history()
        await self.mark_messages_as_read()
        
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': f"{self.scope['user'].username} joined the chat",
                'sender': 'System',
                'sender_id': 0,
                'created_at': timezone.now().strftime('%I:%M %p'),
                'is_system': True
            }
        )

    async def disconnect(self, close_code):
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message': f"{self.scope['user'].username} left the chat",
                    'sender': 'System',
                    'sender_id': 0,
                    'created_at': timezone.now().strftime('%I:%M %p'),
                    'is_system': True
                }
            )

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            message = data.get('message', '').strip()
            
            if not message:
                return
                
            saved_message = await self.save_message(message)
            
            if saved_message:
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'chat_message',
                        'message': saved_message['message'],
                        'sender': saved_message['sender'],
                        'sender_id': saved_message['sender_id'],
                        'created_at': saved_message['created_at'],
                        'is_system': False
                    }
                )
                
        except json.JSONDecodeError:
            print("Invalid JSON received")
        except Exception as e:
            print(f"Error in receive: {e}")

    async def chat_message(self, event):
        await self.send(text_data=json.dumps({
            'type': 'message',
            'message': event['message'],
            'sender': event['sender'],
            'sender_id': event['sender_id'],
            'created_at': event['created_at'],
            'is_system': event.get('is_system', False)
        }))

    async def send_chat_history(self):
        messages = await self.get_chat_history()
        
        if messages:
            await self.send(text_data=json.dumps({
                'type': 'chat_history',
                'messages': messages
            }))

    @database_sync_to_async
    def check_permission(self):
        try:
            room = ChatRoom.objects.get(id=self.room_id)
            user = self.scope["user"]
            
            # Check based on chat types
            if room.chat_type == 'buyer_supplier':
                return user == room.supplier or user == room.buyer
            elif room.chat_type == 'supplier_admin':
                return user == room.supplier or user == room.admin
            
            return False
        except ChatRoom.DoesNotExist:
            return False

    @database_sync_to_async
    def save_message(self, message_text):
        try:
            room = ChatRoom.objects.get(id=self.room_id)
            sender = self.scope["user"]
            
            message = ChatMessage.objects.create(
                room=room,
                sender=sender,
                message=message_text
            )
            room.save()
            
            return {
                'message': message.message,
                'sender': message.sender.username,
                'sender_id': message.sender.id,
                'created_at': message.created_at.strftime('%I:%M %p')
            }
        except Exception as e:
            print(f"Error saving message: {e}")
            return None

    @database_sync_to_async
    def get_chat_history(self):
        try:
            messages = ChatMessage.objects.filter(room_id=self.room_id).order_by('created_at')
            
            return [
                {
                    'message': msg.message,
                    'sender': msg.sender.username,
                    'sender_id': msg.sender.id,
                    'created_at': msg.created_at.strftime('%I:%M %p'),
                    'is_read': msg.is_read
                }
                for msg in messages
            ]
        except Exception as e:
            print(f"Error getting chat history: {e}")
            return []

    @database_sync_to_async
    def mark_messages_as_read(self):
        try:
            room = ChatRoom.objects.get(id=self.room_id)
            user = self.scope["user"]
            
            unread_messages = ChatMessage.objects.filter(
                room=room,
                is_read=False
            ).exclude(sender=user)
            
            unread_messages.update(is_read=True)
            
            return True
        except Exception as e:
            print(f"Error marking messages as read: {e}")
            return False