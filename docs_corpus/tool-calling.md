# Tool calling

A program sends messages to a model.
The request also sends tool schemas with those messages.
Each schema tells the model a tool name and its arguments.
The model can answer with text when it needs no tool.

The model may answer with tool_calls instead of text.
Each call has an id, a name, and JSON arguments.
The program reads each call and runs the named tool.
It then sends a message with role set to tool.
That message uses the same tool_call_id as the call.
The message includes the tool result.
Then the model can answer with text.

A small model can choose the wrong arguments.
Clear tool errors help it correct its next call.
