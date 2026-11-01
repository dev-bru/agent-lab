"""See the messages sent to a local language model. See its reply and token counts. Use --fake to learn without a running model."""

import argparse
import sys

from agent_lab import fakes, model, model_server, settings


def main(argv=None) -> int:
    """Show one model call and its result."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fake", nargs="?", const=fakes.builtin("01_model_call"), default=None,
                        metavar="SCRIPT", help="Use the built-in or a given fake script.")
    args = parser.parse_args(argv)

    try:
        # Give the model a role and one question so it knows how to answer.
        messages = [
            {"role": "system", "content": "You are a patient teacher. Answer in one short sentence."},
            {"role": "user", "content": "What is a large language model?"},
        ]

        # Show both messages so the learner can see what the model receives.
        for message in messages:
            speaker = "you" if message["role"] == "user" else "system"
            print(f"{speaker}> {message['content']}")

        # Use scripted answers when --fake is given, so no model server is needed.
        chat = fakes.FakeModel(args.fake).chat if args.fake is not None else model.chat

        # Ask once so the reply matches the messages shown above.
        reply = chat(messages)

        # Show the answer so the learner can read what the model said.
        print(f"agent> {reply.text}")

        # Show the token counts so the learner can see the size of this call.
        usage = reply.usage
        print(f"[tokens] prompt={usage['prompt_tokens']} completion={usage['completion_tokens']} "
              f"total={usage['total_tokens']}")
    except fakes.ScriptExhausted:
        print("error: the fake script has no more replies", file=sys.stderr)
        return 1
    except (model.ModelError, model_server.ModelServerError, settings.SettingsError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
