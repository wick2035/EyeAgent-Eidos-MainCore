-- Development-only reset for 医问通 message tree testing.
-- Run manually against a disposable development database.
SET FOREIGN_KEY_CHECKS = 0;
DELETE FROM chat_message;
DELETE FROM chat_conversation;
SET FOREIGN_KEY_CHECKS = 1;

-- LangGraph checkpoint cleanup depends on the installed checkpointer table names.
-- Confirm table names in the development database before running these statements.
-- DELETE FROM langgraph_checkpoint_writes;
-- DELETE FROM langgraph_checkpoint;
-- DELETE FROM langgraph_thread_mapping;
-- DELETE FROM langgraph_thread_agent_history;
