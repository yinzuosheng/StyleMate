"""Owner/conversation-bound write-action facade kept separate from graph closures."""

from dataclasses import dataclass
from typing import Any

from stylemate.agent.tools.write_actions import (
    cancel_action,
    confirm_action,
    prepare_add_garment,
    prepare_delete_garment,
    prepare_update_garment,
)


@dataclass
class WriteActionToolkit:
    owner_id: str
    conversation_id: str
    agent_repository: Any
    wardrobe_repository: Any
    wardrobe_service: Any

    def prepare_add_garment(self, metadata: dict):
        return prepare_add_garment(owner_id=self.owner_id, conversation_id=self.conversation_id, metadata=metadata, agent_repository=self.agent_repository)

    def prepare_update_garment(self, garment_id: str, changes: dict):
        return prepare_update_garment(owner_id=self.owner_id, conversation_id=self.conversation_id, garment_id=garment_id, changes=changes, agent_repository=self.agent_repository, wardrobe_repository=self.wardrobe_repository)

    def prepare_delete_garment(self, garment_id: str):
        return prepare_delete_garment(owner_id=self.owner_id, conversation_id=self.conversation_id, garment_id=garment_id, agent_repository=self.agent_repository, wardrobe_repository=self.wardrobe_repository)

    def confirm_action(self, action_id: str):
        return confirm_action(action_id=action_id, owner_id=self.owner_id, conversation_id=self.conversation_id, agent_repository=self.agent_repository, wardrobe_repository=self.wardrobe_repository, wardrobe_service=self.wardrobe_service)

    def cancel_action(self, action_id: str):
        return cancel_action(action_id=action_id, owner_id=self.owner_id, conversation_id=self.conversation_id, agent_repository=self.agent_repository)


def build_write_action_toolkit(**kwargs) -> WriteActionToolkit:
    return WriteActionToolkit(**kwargs)

