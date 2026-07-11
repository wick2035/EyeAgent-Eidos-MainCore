from typing import Optional


class ConversationBusyError(ValueError):
    code = "CONVERSATION_BUSY"

    def __init__(self):
        super().__init__(self.code)


class ConversationActivityGuard:
    """在会话行已锁定时统一检查附件回合与旧纯文本流。"""

    def __init__(self, turn_repo, message_repo):
        self.turn_repo = turn_repo
        self.message_repo = message_repo

    def assert_idle_locked(
        self,
        conversation_id: str,
        ignore_request_id: Optional[str] = None,
    ) -> None:
        active_turn = self.turn_repo.get_active_for_conversation(
            conversation_id,
            ignore_request_id=ignore_request_id,
        )
        if active_turn is not None:
            raise ConversationBusyError()

        get_active = getattr(
            self.message_repo,
            "get_active_assistant_for_conversation",
            None,
        )
        if get_active is not None:
            active_assistant = get_active(conversation_id)
        else:
            active_assistant = next(
                (
                    message
                    for message in reversed(
                        self.message_repo.get_by_chat_id(conversation_id)
                    )
                    if message.message_type == "assistant"
                    and message.status in ("running", "streaming")
                    and not message.deleted
                ),
                None,
            )
        if active_assistant is not None:
            raise ConversationBusyError()
