"""Ask a model for a study card as JSON. Check its shape. Give one correction when the reply is wrong."""

import argparse
import sys

from pydantic import BaseModel, Field, ValidationError

from agent_lab import fakes, model, model_server, settings


class StudyCard(BaseModel):
    """Store a term, its meaning, and an example."""

    term: str
    meaning: str = Field(max_length=200)
    example: str


RESPONSE_FORMAT = {"type": "json_schema", "json_schema": {
    "name": "StudyCard", "schema": StudyCard.model_json_schema(), "strict": True}}


def describe(error: ValidationError) -> str:
    """Turn validation problems into short instructions for the model."""
    return "; ".join(f"{'.'.join(str(p) for p in e['loc']) or 'reply'}: {e['msg']}"
                     for e in error.errors())


def run(chat) -> int:
    """Check a study card and allow one corrected reply."""
    try:
        # Ask for a study card about tool calling.
        question = "Make a study card for the term 'tool calling'."
        messages = [
            {"role": "system", "content": "You make study cards. Reply with JSON only."},
            {"role": "user", "content": question},
        ]
        print(f"you> {question}")

        # Check each reply against the card's shape.
        for attempt in (1, 2):
            reply = chat(messages, response_format=RESPONSE_FORMAT)
            text = reply.text or ""
            print(f"agent> {text}")
            try:
                card = StudyCard.model_validate_json(text)
            except ValidationError as error:
                fixes = describe(error)
                print(f"[check] not valid: {fixes}")
            else:
                print("[check] valid study card")
                print(f"term: {card.term}")
                print(f"meaning: {card.meaning}")
                print(f"example: {card.example}")
                return 0

            # Show the model its bad reply and the exact problems once.
            if attempt == 1:
                messages.append({"role": "assistant", "content": text})
                messages.append({"role": "user", "content":
                                 "That reply was not a valid study card. "
                                 f"Fix these problems and reply with JSON only: {fixes}"})

        # Explain why the second reply ends the lesson.
        print(f"error: the reply was not a valid study card after 2 tries: {fixes}", file=sys.stderr)
        return 1
    except fakes.ScriptExhausted:
        print("error: the fake script has no more replies", file=sys.stderr)
        return 1
    except (model.ModelError, model_server.ModelServerError, settings.SettingsError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


def main(argv=None) -> int:
    """Choose a fake script or the local model, then run the lesson."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fake", nargs="?", const=fakes.builtin("03_structured_output"), default=None,
                        metavar="SCRIPT", help="Use the built-in or a given fake script.")
    args = parser.parse_args(argv)
    try:
        chat = fakes.FakeModel(args.fake).chat if args.fake is not None else model.chat
    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return run(chat)


if __name__ == "__main__":
    raise SystemExit(main())
