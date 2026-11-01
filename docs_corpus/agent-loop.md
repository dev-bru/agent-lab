# The agent loop

An agent repeats a small set of actions.
One step is one model call.
The loop calls the model with the current messages.
If the model asks for tools, the program runs them.
The program adds each tool result to the messages.
Then the loop calls the model again.

The loop stops when the model gives a text answer.
It also stops at the step limit max_steps.
Settings use 6 as the default max_steps value.
The limit prevents an endless run.

A trace records each step.
It shows what the model asked and what happened.
The record helps a learner inspect the loop.
