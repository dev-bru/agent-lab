# MCP basics

MCP means Model Context Protocol.
It lets a program offer tools, resources, and prompts to an AI client.
A tool does a task, such as looking up local notes.
A resource gives the client data it can read.
A prompt gives the client a prepared instruction.

The MCP server lists its tools for the client.
Each tool has a name and a description.
The list also includes input schemas for tool arguments.
The client calls a tool by name with JSON arguments.

With stdio transport, the client starts the server.
They talk through standard input and standard output.
The client reads the result after the server runs the tool.
A tool error returns as a result marked isError.
The model can read that error and retry with better arguments.
