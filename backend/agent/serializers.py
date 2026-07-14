from rest_framework import serializers

from agent.models import AgentSession, SessionMessage


class SessionMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = SessionMessage
        fields = ["id", "session", "role", "content", "metadata", "created_at"]
        read_only_fields = ["id", "created_at"]


class AgentSessionSerializer(serializers.ModelSerializer):
    message_count = serializers.SerializerMethodField()

    class Meta:
        model = AgentSession
        fields = ["id", "user_id", "title", "metadata", "is_archived", "created_at", "updated_at", "message_count"]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_message_count(self, obj):
        return obj.messages.count()


class AgentSessionDetailSerializer(serializers.ModelSerializer):
    messages = SessionMessageSerializer(many=True, read_only=True)

    class Meta:
        model = AgentSession
        fields = ["id", "user_id", "title", "metadata", "is_archived", "created_at", "updated_at", "messages"]
        read_only_fields = ["id", "created_at", "updated_at"]
